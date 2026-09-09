"""Reference material fields. See docs/reference/material-fields.md for units."""

import cupy as cp
from cupyx.scipy.ndimage import convolve1d

from textureworks.core.material_fields import boundary_mode, field, geometry, matching, number, weights


def generate_detail(color: cp.ndarray, radius: int = 4, boundary: str = "wrap") -> cp.ndarray:
    """Encode a linear RGB Gaussian residual around neutral 0.5."""
    color = field(color, 3, "linear color")
    mode = "wrap" if boundary_mode(boundary) else "nearest"
    w = weights(radius)
    low = convolve1d(convolve1d(color, w, axis=1, mode=mode), w, axis=0, mode=mode)
    return cp.clip(0.5 + 0.5*(color-low), 0, 1).astype(cp.float32)


def _derivatives(height: cp.ndarray, dx: float, dy: float, depth: float, boundary: str) -> tuple[cp.ndarray, ...]:
    p = cp.pad(height, 1, mode="wrap" if boundary == "wrap" else "edge")
    c, l, r, u, d = p[1:-1,1:-1], p[1:-1,:-2], p[1:-1,2:], p[:-2,1:-1], p[2:,1:-1]
    hx, hy = (r-l)*(depth/(2*dx)), (d-u)*(depth/(2*dy))
    hxx, hyy = ((r-c)+(l-c))*(depth/dx**2), ((d-c)+(u-c))*(depth/dy**2)
    hxy = ((p[2:,2:]-p[2:,:-2])-(p[:-2,2:]-p[:-2,:-2]))*(depth/(4*dx*dy))
    return hx, hy, hxx, hyy, hxy


def generate_surface_normal(height: cp.ndarray, texel_size: tuple[float, float] = (1,1),
                            relief_depth: float = 1, boundary: str = "clamp") -> cp.ndarray:
    """Return OpenGL tangent normals from height and physical sample spacing."""
    height = field(height)
    dx, dy, depth = geometry(texel_size, relief_depth, boundary)
    hx, hy, *_ = _derivatives(height, dx, dy, depth, boundary)
    n = cp.stack((-hx, hy, cp.ones_like(hx)), axis=2)
    n /= cp.sqrt(cp.sum(n*n, axis=2, keepdims=True))
    return (n*0.5+0.5).astype(cp.float32)


def generate_curvature(height: cp.ndarray, texel_size: tuple[float, float] = (1,1),
                       relief_depth: float = 1, curvature_range: float = 1,
                       boundary: str = "clamp") -> cp.ndarray:
    """Encode signed graph mean curvature, positive on bumps, neutral 0.5."""
    height = field(height)
    dx, dy, depth = geometry(texel_size, relief_depth, boundary)
    limit = number(curvature_range, "curvature_range", 1e-6, 1e6)
    hx, hy, hxx, hyy, hxy = _derivatives(height, dx, dy, depth, boundary)
    base = 1+hx*hx+hy*hy
    k = -((1+hy*hy)*hxx-2*hx*hy*hxy+(1+hx*hx)*hyy)/(2*base*cp.sqrt(base))
    return (0.5+0.5*cp.clip(k/limit, -1, 1)).astype(cp.float32)


def generate_wear(curvature: cp.ndarray, edge_amount: float = 0.35, cavity_amount: float = 0.5,
                  threshold: float = 0.1, variation: float = 0.35, seed: int = 0,
                  edge_mask: cp.ndarray | None = None, cavity_mask: cp.ndarray | None = None) -> cp.ndarray:
    """Return linear RGB edge/cavity/combined masks with repeatable variation."""
    curvature = field(curvature)
    edge_amount = number(edge_amount, "edge_amount", 0, 1)
    cavity_amount = number(cavity_amount, "cavity_amount", 0, 1)
    threshold = number(threshold, "threshold", 0, 0.999)
    variation = number(variation, "variation", 0, 1)
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 0xffffffff:
        raise ValueError("seed must be a uint32 integer")
    s = 2*curvature-1
    edge = cp.clip((s-threshold)/(1-threshold), 0, 1) if edge_mask is None else field(edge_mask)
    cavity = cp.clip((-s-threshold)/(1-threshold), 0, 1) if cavity_mask is None else field(cavity_mask)
    matching(curvature, edge, cavity)
    h = cp.arange(curvature.size, dtype=cp.uint32).reshape(curvature.shape) ^ cp.uint32(seed)
    h = (h ^ (h >> 16)) * cp.uint32(0x7feb352d)
    h = (h ^ (h >> 15)) * cp.uint32(0x846ca68b)
    h = h ^ (h >> 16)
    noise = (h & cp.uint32(0xffffff)).astype(cp.float32)/cp.float32(16777215)
    modulation = 1-variation+variation*noise
    e, c = edge*edge_amount*modulation, cavity*cavity_amount*modulation
    return cp.stack((e,c,cp.maximum(e,c)), axis=2).astype(cp.float32)


def generate_layer_weight(height_a: cp.ndarray, height_b: cp.ndarray, mask: cp.ndarray,
                          coverage: float = 0.5, blend_width: float = 0.2,
                          height_bias: float = 0.5) -> cp.ndarray:
    """Return the common B weight for runtime or baked height and channels."""
    a, b, mask = field(height_a), field(height_b), field(mask)
    matching(a,b,mask)
    coverage = number(coverage, "coverage", 0, 1)
    width = number(blend_width, "blend_width", 0, 1)
    bias = number(height_bias, "height_bias", 0, 1)
    m = cp.clip(mask+2*coverage-1, 0, 1)
    score = m+bias*(b-a)*m*(1-m)
    if width == 0:
        return (score >= 0.5).astype(cp.float32)
    t = cp.clip((score-(0.5-width/2))/width, 0, 1)
    return (t*t*(3-2*t)).astype(cp.float32)
