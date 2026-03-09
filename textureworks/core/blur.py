"""Separable Gaussian blur for float32 GPU arrays."""

import cupy as cp
import numpy as np


def gaussian_kernel_1d(sigma: float) -> cp.ndarray:
    """Generate a normalized 1D Gaussian kernel on GPU.

    Args:
        sigma: Standard deviation. If <= 0, returns identity kernel [1.0].

    Returns:
        1D cupy.ndarray of float32 weights, length = 2*radius+1.
    """
    if sigma <= 0:
        return cp.array([1.0], dtype=cp.float32)
    radius = int(np.ceil(3.0 * sigma))
    x = np.arange(-radius, radius + 1, dtype=np.float32)
    weights = np.exp(-x * x / (2.0 * sigma * sigma))
    weights /= weights.sum()
    return cp.asarray(weights)


def gaussian_blur(image: cp.ndarray, sigma: float) -> cp.ndarray:
    """Apply separable Gaussian blur to a 2D float32 GPU array.

    Uses clamp-to-edge boundary handling (nearest pixel replication).

    Args:
        image: (H, W) float32 cupy array.
        sigma: Blur sigma. If <= 0, returns input unchanged.

    Returns:
        Blurred (H, W) float32 cupy array.
    """
    if sigma <= 0:
        return image.copy()
    kernel = gaussian_kernel_1d(sigma)
    from cupyx.scipy.ndimage import convolve1d
    temp = convolve1d(image, kernel, axis=1, mode='nearest')
    result = convolve1d(temp, kernel, axis=0, mode='nearest')
    return result
