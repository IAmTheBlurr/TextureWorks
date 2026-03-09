"""CuPy reference implementation for ambient occlusion map generation."""

import cupy as cp
import numpy as np


def generate_ao(
    texture: cp.ndarray,
    height_map: cp.ndarray | None = None,
    num_directions: int = 16,
    max_steps: int = 20,
    step_scale: float = 1.0,
    height_scale: float = 10.0,
    power: float = 1.5,
) -> cp.ndarray:
    """Generate an ambient occlusion map via screen-space horizon mapping.

    Args:
        texture: (H, W, 3) RGB input for height map generation if needed.
        height_map: Optional pre-computed (H, W) height map. Generated if None.
        num_directions: Number of ray directions, default 16.
        max_steps: Steps per ray, default 20.
        step_scale: Pixel distance per step, default 1.0.
        height_scale: Height map influence, default 10.0.
        power: Contrast power curve, default 1.5.

    Returns:
        (H, W) float32 cupy array, values in [0, 1].
    """
    if height_map is None:
        from textureworks.cupy_ref.height import generate_height
        height_map = generate_height(texture)

    h, w = height_map.shape

    # Pre-compute direction angles and trig values
    angles = cp.arange(num_directions, dtype=cp.float32) * (2.0 * np.pi / num_directions)
    cos_a = cp.cos(angles)
    sin_a = cp.sin(angles)

    # Coordinate grids for vectorized sampling
    y_coords, x_coords = cp.meshgrid(
        cp.arange(h, dtype=cp.float32),
        cp.arange(w, dtype=cp.float32),
        indexing="ij",
    )

    occlusion_sum = cp.zeros((h, w), dtype=cp.float32)

    for d in range(num_directions):
        max_elev = cp.zeros((h, w), dtype=cp.float32)

        for s in range(1, max_steps + 1):
            # Sample coordinates along the ray
            sx = x_coords + cos_a[d] * s * step_scale
            sy = y_coords + sin_a[d] * s * step_scale

            # Nearest-neighbor sampling with clamp-to-edge
            sxi = cp.clip(cp.round(sx).astype(cp.int32), 0, w - 1)
            syi = cp.clip(cp.round(sy).astype(cp.int32), 0, h - 1)

            sampled_h = height_map[syi, sxi]
            delta_h = (sampled_h - height_map) * height_scale
            distance = float(s * step_scale)
            elevation = cp.arctan2(delta_h, distance)
            max_elev = cp.maximum(max_elev, elevation)

        occlusion_sum += max_elev

    # Average across directions
    avg_occlusion = occlusion_sum / num_directions

    # Convert to AO: 1.0 - normalized occlusion
    ao = 1.0 - (avg_occlusion / (np.pi / 2.0))
    ao = cp.clip(ao, 0.0, 1.0)

    # Power curve for artistic control
    ao = cp.power(ao, power)

    return ao
