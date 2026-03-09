"""PTX-accelerated ambient occlusion map generation."""

from pathlib import Path

import cupy as cp
import numpy as np

from textureworks.core.gpu import grid_size, recommended_block_size

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


def generate_ao(
    texture: cp.ndarray,
    height_map: cp.ndarray | None = None,
    num_directions: int = 16,
    max_steps: int = 20,
    step_scale: float = 1.0,
    height_scale: float = 10.0,
    power: float = 1.5,
) -> cp.ndarray:
    """Generate an ambient occlusion map using hand-written PTX kernel.

    Args:
        texture: (H, W, 3) RGB input for height map generation if needed.
        height_map: Optional pre-computed (H, W) height map.
        num_directions: Number of ray directions, default 16.
        max_steps: Steps per ray, default 20.
        step_scale: Pixel distance per step, default 1.0.
        height_scale: Height map influence, default 10.0.
        power: Contrast power curve, default 1.5.

    Returns:
        (H, W) float32 cupy array, values in [0, 1].
    """
    if height_map is None:
        from textureworks.ptx.height import generate_height
        height_map = generate_height(texture)

    h, w = height_map.shape
    output = cp.zeros((h, w), dtype=cp.float32)

    mod = _get_module("ao")
    kernel = mod.get_function("ao_kernel")

    block = recommended_block_size()
    grid = grid_size(w, h, block)

    kernel(
        grid=(grid[0], grid[1], 1),
        block=(block[0], block[1], 1),
        args=(
            height_map.data.ptr, output.data.ptr,
            np.int32(w), np.int32(h),
            np.int32(num_directions), np.int32(max_steps),
            np.float32(step_scale), np.float32(height_scale),
            np.float32(power),
        ),
        shared_mem=0,
    )
    return output
