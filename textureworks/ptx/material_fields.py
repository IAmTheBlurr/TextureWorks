"""Handwritten PTX material fields with the reference API and physical units."""

from pathlib import Path

import cupy as cp
import numpy as np

from textureworks.core.gpu import grid_size, recommended_block_size
from textureworks.core.material_fields import boundary_mode, field, geometry, matching, number, weights

_modules: dict[str, cp.cuda.function.Module] = {}


def _launch(entry: str, shape: tuple[int, ...], args: tuple) -> None:
    if "fields" not in _modules:
        module = cp.cuda.function.Module()
        module.load((Path(__file__).parent / "kernels/material_fields.ptx").read_bytes())
        _modules["fields"] = module
    block = recommended_block_size()
    grid = grid_size(shape[1], shape[0], block)
    _modules["fields"].get_function(entry)(
        grid=(*grid,1), block=(*block,1),
        args=tuple(a.data.ptr if isinstance(a, cp.ndarray) else a for a in args), shared_mem=0)


def generate_detail(color: cp.ndarray, radius: int = 4, boundary: str = "wrap") -> cp.ndarray:
    """Encode a linear RGB Gaussian residual around neutral 0.5."""
    color = field(color, 3, "linear color")
    wrap = boundary_mode(boundary)
    kernel = weights(radius)
    h,w = color.shape[:2]
    temp, low, out = (cp.empty_like(color) for _ in range(3))
    for source, target, axis in ((color,temp,0),(temp,low,1)):
        _launch("detail_blur", color.shape, (source,target,kernel,np.int32(w),np.int32(h),
                                           np.int32(radius),np.int32(axis),np.int32(wrap)))
    _launch("detail_residual", color.shape, (color,low,out,np.int32(w),np.int32(h)))
    return out


def _surface(height: cp.ndarray, texel_size: tuple[float,float], relief_depth: float,
             curvature_range: float, boundary: str) -> tuple[cp.ndarray, cp.ndarray]:
    height = field(height)
    dx,dy,depth = geometry(texel_size, relief_depth, boundary)
    limit = number(curvature_range, "curvature_range", 1e-6, 1e6)
    h,w = height.shape
    normal, curvature = cp.empty((h,w,3), cp.float32), cp.empty_like(height)
    _launch("surface_geometry", height.shape, (height,normal,curvature,np.int32(w),np.int32(h),
        np.float32(dx),np.float32(dy),np.float32(depth),np.float32(limit),np.int32(boundary_mode(boundary))))
    return normal,curvature


def generate_surface_normal(height: cp.ndarray, texel_size: tuple[float, float] = (1,1),
                            relief_depth: float = 1, boundary: str = "clamp") -> cp.ndarray:
    """Return OpenGL tangent normals from height and physical sample spacing."""
    return _surface(height, texel_size, relief_depth, 1, boundary)[0]


def generate_curvature(height: cp.ndarray, texel_size: tuple[float, float] = (1,1),
                       relief_depth: float = 1, curvature_range: float = 1,
                       boundary: str = "clamp") -> cp.ndarray:
    """Encode signed graph mean curvature, positive on bumps, neutral 0.5."""
    return _surface(height, texel_size, relief_depth, curvature_range, boundary)[1]


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
    edge = curvature if edge_mask is None else field(edge_mask)
    cavity = curvature if cavity_mask is None else field(cavity_mask)
    matching(curvature,edge,cavity)
    h,w = curvature.shape
    out = cp.empty((h,w,3), cp.float32)
    _launch("wear_masks", curvature.shape, (curvature,edge,cavity,out,np.int32(w),np.int32(h),
        np.float32(edge_amount),np.float32(cavity_amount),np.float32(threshold),np.float32(variation),
        np.uint32(seed),np.int32(edge_mask is not None),np.int32(cavity_mask is not None)))
    return out


def generate_layer_weight(height_a: cp.ndarray, height_b: cp.ndarray, mask: cp.ndarray,
                          coverage: float = 0.5, blend_width: float = 0.2,
                          height_bias: float = 0.5) -> cp.ndarray:
    """Return the common B weight for runtime or baked height and channels."""
    a,b,mask = field(height_a),field(height_b),field(mask)
    matching(a,b,mask)
    coverage = number(coverage, "coverage", 0, 1)
    width = number(blend_width, "blend_width", 0, 1)
    bias = number(height_bias, "height_bias", 0, 1)
    h,w = a.shape
    out = cp.empty_like(a)
    _launch("layer_weight", a.shape, (a,b,mask,out,np.int32(w),np.int32(h),
        np.float32(coverage),np.float32(width),np.float32(bias)))
    return out
