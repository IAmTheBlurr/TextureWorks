"""PTX-accelerated metallic map generation."""

from pathlib import Path

import cupy as cp
import numpy as np

from textureworks.core.blur import gaussian_blur
from textureworks.core.gpu import grid_size, recommended_block_size
from textureworks.core.io import rgb_to_hsv

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


def generate_metallic(
    texture: cp.ndarray,
    sat_threshold: float = 0.35,
    val_threshold: float = 0.10,
    val_range: float = 0.3,
    blur: float = 2.0,
    hard_edges: bool = False,
) -> cp.ndarray:
    """Generate a metallic map using hand-written PTX kernel.

    Args:
        texture: (H, W, 3) float32 cupy array, values in [0, 1].
        sat_threshold: Max saturation for metal classification, default 0.35.
        val_threshold: Min value for metal classification, default 0.10.
        val_range: Soft transition width above val_threshold, default 0.3.
        blur: Output smoothing sigma, default 2.0.
        hard_edges: If True, apply binary threshold, default False.

    Returns:
        (H, W) float32 cupy array, values in [0, 1].
    """
    _, sat, val = rgb_to_hsv(texture)
    h, w = sat.shape

    output = cp.empty((h, w), dtype=cp.float32)

    mod = _get_module("metallic")
    kernel = mod.get_function("metallic_classify_kernel")
    block = recommended_block_size()
    grid = grid_size(w, h, block)

    kernel(
        grid=(grid[0], grid[1], 1),
        block=(block[0], block[1], 1),
        args=(
            sat.data.ptr, val.data.ptr, output.data.ptr,
            np.int32(w), np.int32(h),
            np.float32(sat_threshold), np.float32(val_threshold),
            np.float32(val_range),
            np.uint32(1 if hard_edges else 0),
        ),
        shared_mem=0,
    )

    # Gaussian blur for smooth transitions
    if blur > 0:
        output = gaussian_blur(output, blur)

    return output
