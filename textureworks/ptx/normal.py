"""PTX-accelerated normal map generation."""

from pathlib import Path

import cupy as cp
import numpy as np

from textureworks.core.gpu import grid_size, recommended_block_size
from textureworks.core.io import to_grayscale

_PTX_DIR = Path(__file__).parent / "kernels"
_kernel_cache = {}


def _get_kernel(name: str, entry: str):
    """Load and cache a PTX kernel via the CUDA driver API."""
    if name not in _kernel_cache:
        ptx_source = (_PTX_DIR / f"{name}.ptx").read_text()
        mod = cp.cuda.function.Module()
        mod.load(ptx_source.encode("utf-8"))
        _kernel_cache[name] = mod
    return _kernel_cache[name].get_function(entry)


def generate_normal(texture: cp.ndarray, strength: float = 2.0) -> cp.ndarray:
    """Generate a normal map using hand-written PTX kernel.

    Args:
        texture: (H, W, 3) float32 cupy array, values in [0, 1].
        strength: Depth exaggeration factor, default 2.0.

    Returns:
        (H, W, 3) float32 cupy array (RGB normal map), values in [0, 1].
    """
    gray = to_grayscale(texture)
    h, w = gray.shape
    output = cp.zeros((h, w, 3), dtype=cp.float32)

    kernel = _get_kernel("normal", "sobel_normal_kernel")

    block = recommended_block_size()
    grid = grid_size(w, h, block)
    kernel(
        grid=(grid[0], grid[1], 1),
        block=(block[0], block[1], 1),
        args=(gray.data.ptr, output.data.ptr,
              np.int32(w), np.int32(h), np.float32(strength)),
        shared_mem=0,
    )
    return output
