"""Validation and sampling conventions shared by material field backends."""

import math

import cupy as cp
import numpy as np


def field(value: cp.ndarray, channels: int = 1, name: str = "field") -> cp.ndarray:
    """Validate a normalized GPU field without changing its precision or range."""
    if not isinstance(value, cp.ndarray) or value.dtype != cp.float32:
        raise ValueError(f"{name} must be a float32 CuPy array")
    shape_ok = value.ndim == 2 if channels == 1 else value.ndim == 3 and value.shape[2] == channels
    if not shape_ok or min(value.shape[:2]) < 2:
        raise ValueError(f"{name} must have shape (H,W){' with '+str(channels)+' channels' if channels != 1 else ''}, H,W >= 2")
    if not bool(cp.all(cp.isfinite(value) & (value >= 0) & (value <= 1))):
        raise ValueError(f"{name} values must be finite and in [0,1]")
    return cp.ascontiguousarray(value)


def number(value: float, name: str, low: float, high: float) -> float:
    """Require a finite scalar within the documented inclusive interval."""
    if isinstance(value, bool) or not isinstance(value, (int, float, np.number)):
        raise ValueError(f"{name} must be numeric")
    value = float(value)
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be finite and in [{low},{high}]")
    return value


def boundary_mode(boundary: str) -> int:
    """Map the two explicit edge conventions to the kernel flag."""
    if boundary not in ("clamp", "wrap"):
        raise ValueError("boundary must be clamp or wrap")
    return int(boundary == "wrap")


def geometry(texel_size: tuple[float, float], relief_depth: float, boundary: str) -> tuple[float, float, float]:
    """Validate physical spacing, depth and boundary convention."""
    if len(texel_size) != 2:
        raise ValueError("texel_size must contain x and y spacing in meters")
    dx, dy = (number(v, "texel_size", 1e-6, 1e6) for v in texel_size)
    depth = number(relief_depth, "relief_depth", 0, 100)
    boundary_mode(boundary)
    return dx, dy, depth


def weights(radius: int) -> cp.ndarray:
    """Gaussian support is exactly radius texels; sigma is radius/3."""
    if isinstance(radius, bool) or not isinstance(radius, int) or not 1 <= radius <= 64:
        raise ValueError("radius must be an integer in [1,64] texels")
    x = np.arange(-radius, radius + 1, dtype=np.float32)
    w = np.exp(-x*x / np.float32(2*(radius/3)**2))
    return cp.asarray(w / w.sum())


def matching(*arrays: cp.ndarray) -> None:
    """Reject fields on incompatible sample grids."""
    if any(a.shape[:2] != arrays[0].shape[:2] for a in arrays[1:]):
        raise ValueError("material fields must have matching dimensions")
