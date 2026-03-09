"""CuPy reference implementation for metallic map generation."""

import cupy as cp

from textureworks.core.blur import gaussian_blur
from textureworks.core.io import rgb_to_hsv


def generate_metallic(
    texture: cp.ndarray,
    sat_threshold: float = 0.35,
    val_threshold: float = 0.10,
    val_range: float = 0.3,
    blur: float = 2.0,
    hard_edges: bool = False,
) -> cp.ndarray:
    """Generate a metallic map from an RGB texture.

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

    # Soft classification
    sat_score = 1.0 - cp.clip(sat / sat_threshold, 0.0, 1.0)
    val_score = cp.clip((val - val_threshold) / (val_range + 1e-8), 0.0, 1.0)
    metallic = sat_score * val_score

    # Smooth transitions
    metallic = gaussian_blur(metallic, blur)

    # Optional binary threshold
    if hard_edges:
        metallic = cp.where(metallic > 0.5, 1.0, 0.0).astype(cp.float32)

    return metallic
