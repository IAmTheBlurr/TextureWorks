"""CuPy reference implementation for height map generation."""

import cupy as cp

from textureworks.core.blur import gaussian_blur
from textureworks.core.io import to_grayscale


def generate_height(
    texture: cp.ndarray,
    blur_sigma: float = 1.0,
    contrast: float = 1.2,
    invert: bool = False,
) -> cp.ndarray:
    """Generate a height map from an RGB texture.

    Args:
        texture: (H, W, 3) float32 cupy array, values in [0, 1].
        blur_sigma: Gaussian smoothing sigma, default 1.0.
        contrast: Contrast multiplier, default 1.2.
        invert: If True, flip height interpretation (white=low).

    Returns:
        (H, W) float32 cupy array, values in [0, 1].
    """
    gray = to_grayscale(texture)

    # Normalize to full [0, 1] range
    lmin = float(cp.min(gray))
    lmax = float(cp.max(gray))
    h = (gray - lmin) / (lmax - lmin + 1e-8)

    # Gaussian blur for smoothing
    h = gaussian_blur(h, blur_sigma)

    # Contrast adjustment around midpoint
    h = cp.clip((h - 0.5) * contrast + 0.5, 0.0, 1.0)

    if invert:
        h = 1.0 - h

    return h
