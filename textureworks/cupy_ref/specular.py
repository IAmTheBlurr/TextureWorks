"""CuPy reference implementation for specular map generation."""

import cupy as cp

from textureworks.core.blur import gaussian_blur
from textureworks.core.io import rgb_to_hsv, to_grayscale


def generate_specular(
    texture: cp.ndarray,
    sat_weight: float = 0.5,
    contrast: float = 1.3,
    power: float = 1.2,
    blur: float = 0.5,
) -> cp.ndarray:
    """Generate a specular map from an RGB texture.

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

    # Base specular: high luminance + low saturation -> high specularity
    spec = lum * (1.0 - sat * sat_weight)

    # Normalize to [0, 1]
    smin = float(cp.min(spec))
    smax = float(cp.max(spec))
    spec = (spec - smin) / (smax - smin + 1e-8)

    # Contrast and power curve
    spec = cp.clip(spec * contrast, 0.0, 1.0)
    spec = cp.power(spec, power)

    # Smooth
    spec = gaussian_blur(spec, blur)
    spec = cp.clip(spec, 0.0, 1.0)

    return spec
