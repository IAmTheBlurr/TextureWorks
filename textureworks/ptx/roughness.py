"""PTX-accelerated roughness map generation."""

from pathlib import Path

import cupy as cp
import numpy as np

from textureworks.core.blur import gaussian_blur, gaussian_kernel_1d
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


def generate_roughness(
    texture: cp.ndarray,
    radius: int = 4,
    alpha: float = 0.6,
    blur: float = 1.0,
    contrast: float = 1.5,
) -> cp.ndarray:
    """Generate a roughness map using hand-written PTX kernels.

    Args:
        texture: (H, W, 3) float32 cupy array, values in [0, 1].
        radius: Analysis window half-size, default 4.
        alpha: Variance vs edge weight, default 0.6.
        blur: Output smoothing sigma, default 1.0.
        contrast: Output contrast multiplier, default 1.5.

    Returns:
        (H, W) float32 cupy array, values in [0, 1].
    """
    gray = to_grayscale(texture)
    h, w = gray.shape

    mod = _get_module("roughness")
    block = recommended_block_size()
    grid = grid_size(w, h, block)
    grid3 = (grid[0], grid[1], 1)
    block3 = (block[0], block[1], 1)

    # Step 1: Compute local variance
    var_buf = cp.empty_like(gray)
    var_kernel = mod.get_function("roughness_variance_kernel")
    var_kernel(
        grid=grid3, block=block3,
        args=(gray.data.ptr, var_buf.data.ptr,
              np.int32(w), np.int32(h), np.int32(radius)),
        shared_mem=0,
    )

    # Step 2: Compute Sobel edge magnitude
    edge_buf = cp.empty_like(gray)
    sobel_kernel = mod.get_function("roughness_sobel_kernel")
    sobel_kernel(
        grid=grid3, block=block3,
        args=(gray.data.ptr, edge_buf.data.ptr,
              np.int32(w), np.int32(h)),
        shared_mem=0,
    )

    # Step 3: Normalize min/max (computed on GPU via CuPy)
    var_min = float(cp.min(var_buf))
    var_range = float(cp.max(var_buf)) - var_min + 1e-8
    edge_min = float(cp.min(edge_buf))
    edge_range = float(cp.max(edge_buf)) - edge_min + 1e-8

    # Step 4: Blend (no contrast yet -- contrast must follow blur to match CuPy)
    output = cp.empty_like(gray)
    blend_kernel = mod.get_function("roughness_blend_kernel")
    blend_kernel(
        grid=grid3, block=block3,
        args=(var_buf.data.ptr, edge_buf.data.ptr, output.data.ptr,
              np.int32(w), np.int32(h), np.float32(alpha),
              np.float32(var_min), np.float32(var_range),
              np.float32(edge_min), np.float32(edge_range),
              np.float32(1.0)),  # contrast=1.0 (identity) in kernel
        shared_mem=0,
    )

    # Step 5: Gaussian blur then contrast (same order as CuPy reference)
    if blur > 0:
        output = gaussian_blur(output, blur)
    output = cp.clip((output - 0.5) * contrast + 0.5, 0.0, 1.0)

    return output
