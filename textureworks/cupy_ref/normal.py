"""CuPy reference implementation for normal map generation."""

import cupy as cp

from textureworks.core.io import to_grayscale


def generate_normal(texture: cp.ndarray, strength: float = 2.0) -> cp.ndarray:
    """Generate a normal map from an RGB texture using Sobel gradients.

    Args:
        texture: (H, W, 3) float32 cupy array, values in [0, 1].
        strength: Depth exaggeration factor, default 2.0.

    Returns:
        (H, W, 3) float32 cupy array (RGB normal map), values in [0, 1].
    """
    gray = to_grayscale(texture)

    # Pad with edge replication for 3x3 Sobel kernel
    p = cp.pad(gray, 1, mode='edge')

    # Sobel Gx: [-1 0 1; -2 0 2; -1 0 1]
    gx = (-1.0 * p[0:-2, 0:-2] + 1.0 * p[0:-2, 2:]
          - 2.0 * p[1:-1, 0:-2] + 2.0 * p[1:-1, 2:]
          - 1.0 * p[2:, 0:-2] + 1.0 * p[2:, 2:])

    # Sobel Gy: [-1 -2 -1; 0 0 0; 1 2 1]
    gy = (-1.0 * p[0:-2, 0:-2] - 2.0 * p[0:-2, 1:-1] - 1.0 * p[0:-2, 2:]
          + 1.0 * p[2:, 0:-2] + 2.0 * p[2:, 1:-1] + 1.0 * p[2:, 2:])

    # Construct normal vector: N = normalize(-Gx*strength, -Gy*strength, 1.0)
    nx = -gx * strength
    ny = -gy * strength
    nz = cp.ones_like(nx)

    length = cp.sqrt(nx * nx + ny * ny + nz * nz)
    length = cp.maximum(length, 1e-8)
    nx /= length
    ny /= length
    nz /= length

    # Encode to [0, 1]: (n * 0.5) + 0.5
    r = nx * 0.5 + 0.5
    g = ny * 0.5 + 0.5
    b = nz * 0.5 + 0.5

    return cp.stack([r, g, b], axis=2)
