"""Image loading, saving, and format conversion utilities."""

from pathlib import Path

import cupy as cp
import numpy as np
from PIL import Image


def load_texture(path: str | Path) -> cp.ndarray:
    """Load an image file and return a float32 GPU array in [0, 1] range.

    Args:
        path: Path to PNG, JPG, or other Pillow-supported image.

    Returns:
        cupy.ndarray with shape (H, W, 3) for RGB or (H, W) for grayscale,
        dtype float32, values in [0.0, 1.0].
    """
    img = Image.open(path)
    if img.mode == "RGBA":
        img = img.convert("RGB")
    elif img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    arr = np.asarray(img, dtype=np.float32) / 255.0
    return cp.asarray(arr)


def save_map(data: cp.ndarray, path: str | Path) -> None:
    """Save a GPU array as an 8-bit PNG.

    Args:
        data: cupy.ndarray with values in [0.0, 1.0]. Shape (H, W) for
              grayscale or (H, W, 3) for RGB.
        path: Output file path.
    """
    arr = cp.asnumpy(data)
    arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
    if arr.ndim == 2:
        img = Image.fromarray(arr, mode="L")
    else:
        img = Image.fromarray(arr, mode="RGB")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def to_grayscale(rgb: cp.ndarray) -> cp.ndarray:
    """Convert RGB float32 array to grayscale using BT.709 weights.

    Args:
        rgb: cupy.ndarray with shape (H, W, 3), dtype float32.

    Returns:
        cupy.ndarray with shape (H, W), dtype float32.
    """
    if rgb.ndim == 2:
        return rgb
    return 0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1] + 0.0722 * rgb[:, :, 2]


def rgb_to_hsv(rgb: cp.ndarray) -> tuple[cp.ndarray, cp.ndarray, cp.ndarray]:
    """Convert RGB float32 array to separate H, S, V channels.

    Args:
        rgb: cupy.ndarray with shape (H, W, 3), values in [0, 1].

    Returns:
        Tuple of (H, S, V) each with shape (H, W), dtype float32.
        H in [0, 1] (normalized from 0-360), S in [0, 1], V in [0, 1].
    """
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    cmax = cp.maximum(cp.maximum(r, g), b)
    cmin = cp.minimum(cp.minimum(r, g), b)
    delta = cmax - cmin

    # Hue
    hue = cp.zeros_like(cmax)
    mask_r = (cmax == r) & (delta > 0)
    mask_g = (cmax == g) & (delta > 0)
    mask_b = (cmax == b) & (delta > 0)
    hue[mask_r] = ((g[mask_r] - b[mask_r]) / delta[mask_r]) % 6
    hue[mask_g] = ((b[mask_g] - r[mask_g]) / delta[mask_g]) + 2
    hue[mask_b] = ((r[mask_b] - g[mask_b]) / delta[mask_b]) + 4
    hue = hue / 6.0

    # Saturation
    sat = cp.where(cmax > 0, delta / cmax, 0.0)

    return hue, sat, cmax
