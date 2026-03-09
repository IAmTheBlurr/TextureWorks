"""CuPy reference implementation for roughness map generation."""

import cupy as cp
from cupyx.scipy.ndimage import uniform_filter

from textureworks.core.blur import gaussian_blur
from textureworks.core.io import to_grayscale


def generate_roughness(
    texture: cp.ndarray,
    radius: int = 4,
    alpha: float = 0.6,
    blur: float = 1.0,
    contrast: float = 1.5,
) -> cp.ndarray:
    """Generate a roughness map from an RGB texture.

    Args:
        texture: (H, W, 3) float32 cupy array, values in [0, 1].
        radius: Analysis window half-size, default 4.
        alpha: Variance vs edge weight (1.0 = all variance), default 0.6.
        blur: Output smoothing sigma, default 1.0.
        contrast: Output contrast multiplier, default 1.5.

    Returns:
        (H, W) float32 cupy array, values in [0, 1].
    """
    gray = to_grayscale(texture)
    window = 2 * radius + 1

    # Local mean and variance via box filter
    local_mean = uniform_filter(gray, size=window, mode="nearest")
    local_sq_mean = uniform_filter(gray * gray, size=window, mode="nearest")
    local_var = local_sq_mean - local_mean * local_mean
    local_var = cp.maximum(local_var, 0.0)  # Numerical safety

    # Sobel edge magnitude
    p = cp.pad(gray, 1, mode="edge")
    gx = (-1.0 * p[0:-2, 0:-2] + 1.0 * p[0:-2, 2:]
          - 2.0 * p[1:-1, 0:-2] + 2.0 * p[1:-1, 2:]
          - 1.0 * p[2:, 0:-2] + 1.0 * p[2:, 2:])
    gy = (-1.0 * p[0:-2, 0:-2] - 2.0 * p[0:-2, 1:-1] - 1.0 * p[0:-2, 2:]
          + 1.0 * p[2:, 0:-2] + 2.0 * p[2:, 1:-1] + 1.0 * p[2:, 2:])
    edge = cp.sqrt(gx * gx + gy * gy)

    # Normalize both signals to [0, 1]
    def _normalize(arr):
        amin = float(cp.min(arr))
        amax = float(cp.max(arr))
        return (arr - amin) / (amax - amin + 1e-8)

    norm_var = _normalize(local_var)
    norm_edge = _normalize(edge)

    # Blend
    raw = alpha * norm_var + (1.0 - alpha) * norm_edge

    # Smooth and contrast
    result = gaussian_blur(raw, blur)
    result = cp.clip((result - 0.5) * contrast + 0.5, 0.0, 1.0)

    return result
