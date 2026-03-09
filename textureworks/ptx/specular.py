"""PTX-accelerated specular map generation."""

from pathlib import Path

import cupy as cp
import numpy as np

from textureworks.core.blur import gaussian_blur
from textureworks.core.gpu import grid_size, recommended_block_size
from textureworks.core.io import rgb_to_hsv, to_grayscale

_PTX_DIR = Path(__file__).parent / "kernels"
_module_cache = {}


def _get_module(name: str):
    """Load and cache a PTX module."""
    if name not in _module_cache:
        ptx_source = (_PTX_DIR / f"{name}.ptx").read_text()
        mod = cp.cuda.function.Module()
        mod.load(ptx_source.encode("utf-8"))
        _module_cache[name] = mod
    return _module_cache[name]


def generate_specular(
    texture: cp.ndarray,
    sat_weight: float = 0.5,
    contrast: float = 1.3,
    power: float = 1.2,
    blur: float = 0.5,
) -> cp.ndarray:
    """Generate a specular map using hand-written PTX kernel.

    Args:
        texture: (H, W, 3) float32 cupy array, values in [0, 1].
        sat_weight: Saturation reduction factor, default 0.5.
        contrast: Output contrast, default 1.3.
        power: Specular falloff curve, default 1.2.
        blur: Output smoothing sigma, default 0.5.

    Returns:
        (H, W) float32 cupy array, values in [0, 1].
    """
    lum = to_grayscale(texture)
    _, sat, _ = rgb_to_hsv(texture)

    # Compute raw specular for min/max normalization
    raw_spec = lum * (1.0 - sat * sat_weight)
    spec_min = float(cp.min(raw_spec))
    spec_max = float(cp.max(raw_spec))
    spec_range = spec_max - spec_min + 1e-8

    h, w = lum.shape
    output = cp.empty((h, w), dtype=cp.float32)

    mod = _get_module("specular")
    kernel = mod.get_function("specular_kernel")
    block = recommended_block_size()
    grid = grid_size(w, h, block)

    kernel(
        grid=(grid[0], grid[1], 1),
        block=(block[0], block[1], 1),
        args=(
            lum.data.ptr, sat.data.ptr, output.data.ptr,
            np.int32(w), np.int32(h),
            np.float32(sat_weight), np.float32(contrast),
            np.float32(power), np.float32(spec_min),
            np.float32(spec_range),
        ),
        shared_mem=0,
    )

    # Gaussian blur for smooth output
    if blur > 0:
        output = gaussian_blur(output, blur)
        output = cp.clip(output, 0.0, 1.0)

    return output
