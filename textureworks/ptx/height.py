"""PTX-accelerated height map generation."""

from pathlib import Path

import cupy as cp
import numpy as np

from textureworks.core.blur import gaussian_kernel_1d
from textureworks.core.gpu import grid_size, recommended_block_size
from textureworks.core.io import to_grayscale

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


def generate_height(
    texture: cp.ndarray,
    blur_sigma: float = 1.0,
    contrast: float = 1.2,
    invert: bool = False,
) -> cp.ndarray:
    """Generate a height map using hand-written PTX kernels.

    Args:
        texture: (H, W, 3) float32 cupy array, values in [0, 1].
        blur_sigma: Gaussian smoothing sigma, default 1.0.
        contrast: Contrast multiplier, default 1.2.
        invert: If True, flip height interpretation.

    Returns:
        (H, W) float32 cupy array, values in [0, 1].
    """
    gray = to_grayscale(texture)
    h, w = gray.shape

    mod = _get_module("height")
    block = recommended_block_size()
    grid = grid_size(w, h, block)
    grid3 = (grid[0], grid[1], 1)
    block3 = (block[0], block[1], 1)

    # Step 1: Normalize to [0,1] using pre-computed min/max
    lmin = float(cp.min(gray))
    lmax = float(cp.max(gray))
    lrange = lmax - lmin + 1e-8
    normalized = cp.empty_like(gray)

    norm_kernel = mod.get_function("height_normalize_kernel")
    norm_kernel(
        grid=grid3, block=block3,
        args=(gray.data.ptr, normalized.data.ptr,
              np.int32(w), np.int32(h),
              np.float32(lmin), np.float32(lrange)),
        shared_mem=0,
    )

    # Step 2-3: Separable Gaussian blur (horizontal then vertical)
    if blur_sigma > 0:
        weights = gaussian_kernel_1d(blur_sigma)
        radius = len(weights) // 2
        temp = cp.empty_like(normalized)

        blur_h = mod.get_function("height_blur_h_kernel")
        blur_h(
            grid=grid3, block=block3,
            args=(normalized.data.ptr, temp.data.ptr, weights.data.ptr,
                  np.int32(radius), np.int32(w), np.int32(h)),
            shared_mem=0,
        )

        blur_v = mod.get_function("height_blur_v_kernel")
        blur_v(
            grid=grid3, block=block3,
            args=(temp.data.ptr, normalized.data.ptr, weights.data.ptr,
                  np.int32(radius), np.int32(w), np.int32(h)),
            shared_mem=0,
        )

    # Step 4: Contrast adjustment and optional invert (in-place)
    contrast_kernel = mod.get_function("height_contrast_kernel")
    contrast_kernel(
        grid=grid3, block=block3,
        args=(normalized.data.ptr,
              np.int32(w), np.int32(h),
              np.float32(contrast), np.uint32(1 if invert else 0)),
        shared_mem=0,
    )

    return normalized
