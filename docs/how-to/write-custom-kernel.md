# Writing a Custom PTX Kernel

Step-by-step guide for adding a new map type to TextureWorks, from algorithm design through PTX kernel implementation to pipeline integration.

## Overview of the Process

Adding a new map type follows a fixed sequence:

1. Write the algorithm specification in `docs/algorithms.md`
2. Implement the CuPy reference in `cupy_ref/<map_type>.py`
3. Write the PTX kernel in `ptx/kernels/<map_type>.ptx`
4. Create the Python wrapper in `ptx/<map_type>.py`
5. Add tests in `tests/test_<map_type>.py`
6. Register the map type in `pipeline.py`

This guide focuses on steps 3 and 4 (PTX kernel and Python wrapper), using the normal map kernel as the primary example.

## Anatomy of a PTX Kernel

Every TextureWorks PTX kernel follows the same structure. Here is the normal map kernel broken into its components.

### Header Comment

```
// =============================================================================
// Normal Map Kernel: Sobel Gradient -> Normal Vector Encoding
// =============================================================================
// Purpose:     Compute per-pixel surface normals from grayscale input
// Grid/Block:  2D grid, 16x16 blocks. One thread per pixel.
// Parameters:
//   param 0: float* input       -- (H*W) grayscale texture
//   param 1: float* output      -- (H*W*3) RGB normal map
//   param 2: int    width
//   param 3: int    height
//   param 4: float  strength    -- exaggeration factor
// =============================================================================
```

Every kernel file begins with a block comment documenting purpose, grid/block configuration, and parameter layout. This is required by the project coding standards.

### Version and Target

```
.version 7.0
.target sm_75
.address_size 64
```

- `.version 7.0`: PTX ISA version 7.0 or higher
- `.target sm_75`: Turing architecture (RTX 20-series) or higher
- `.address_size 64`: 64-bit pointers for GPU memory addressing

### Entry Point and Parameters

```
.visible .entry sobel_normal_kernel(
    .param .u64 param_input,
    .param .u64 param_output,
    .param .u32 param_width,
    .param .u32 param_height,
    .param .f32 param_strength
)
```

`.visible .entry` declares the kernel as externally callable. Parameters use `.param` memory space with typed declarations: `.u64` for pointers, `.u32` for integers, `.f32` for floats.

### Register Declarations

```
.reg .u32   px_x, px_y, tmp, blk;
.reg .u64   ptr_in, ptr_out, addr;
.reg .f32   grad_x, grad_y, strength;
.reg .pred  p_oob;
```

Follow the naming convention:
- `px_` prefix for pixel coordinates
- `ptr_` prefix for memory pointers
- `grad_` prefix for gradient values
- `norm_` prefix for normalized results
- `enc_` prefix for encoded output values
- `p_` prefix for predicate registers

### Phase 1: Parameter Loading

```
ld.param.u64    ptr_in, [param_input];
ld.param.u64    ptr_out, [param_output];
ld.param.u32    width, [param_width];
ld.param.u32    height, [param_height];
ld.param.f32    strength, [param_strength];
```

Copy each kernel argument from parameter memory into a register. This is always the first phase.

### Phase 2: Coordinate Computation

```
mov.u32         px_x, %tid.x;
mov.u32         tmp, %ctaid.x;
mov.u32         blk, %ntid.x;
mad.lo.u32      px_x, tmp, blk, px_x;    // px_x = blockIdx.x * blockDim.x + threadIdx.x
```

Same pattern for `px_y` using the `.y` components. This maps each thread to a unique pixel.

### Phase 3: Boundary Check

```
setp.ge.u32     p_oob, px_x, width;
@p_oob bra      EXIT;
setp.ge.u32     p_oob, px_y, height;
@p_oob bra      EXIT;
```

Threads beyond image dimensions must exit without accessing memory. The grid may be larger than the image (grid = ceil(dim/16) * 16). This check is mandatory in every kernel.

### Phase 4: Algorithm Implementation

This is the core computation, unique to each map type. For the normal map, it involves loading a 3x3 neighborhood, computing Sobel gradients, normalizing the normal vector, and encoding to RGB.

### Phase 5: Store Output and Exit

```
st.global.f32   [addr], result;

EXIT:
    ret;
```

Write the result to global memory and return. The `EXIT` label provides a target for the boundary check branch.

## Memory Access Patterns

### Computing a Linear Pixel Address

For a 2D pixel at `(px_x, px_y)` in a buffer with `width` columns:

```
// Single-channel buffer
mad.lo.u32      idx, px_y, width, px_x;       // idx = py * width + px
mul.wide.u32    byte_off, idx, 4;              // byte offset (4 bytes per float32)
add.u64         addr, ptr_buf, byte_off;       // absolute address

// Three-channel (RGB) buffer
mad.lo.u32      idx, px_y, width, px_x;
mul.lo.u32      idx3, idx, 3;                  // 3 floats per pixel
mul.wide.u32    byte_off, idx3, 4;
add.u64         addr, ptr_buf, byte_off;
```

`mul.wide.u32` widens a 32-bit multiply to produce a 64-bit result. This is necessary because GPU memory pointers are 64-bit.

### Clamped Neighbor Access

For convolution kernels reading neighbor pixels with clamp-to-edge boundary handling:

```
add.s32     cx, px_x, -1;              // neighbor at x-1
max.s32     cx, cx, 0;                 // clamp to 0
min.s32     cx, cx, width_m1;          // clamp to width-1
```

Use `.s32` (signed) for coordinates involved in neighbor offsets. The `max`/`min` pair implements clamping.

## Key PTX Instructions

| Instruction | Purpose |
|-------------|---------|
| `ld.global.f32 dst, [addr]` | Load float32 from global memory |
| `st.global.f32 [addr], src` | Store float32 to global memory |
| `mad.lo.u32 d, a, b, c` | `d = a * b + c` (multiply-add, low 32 bits) |
| `mul.wide.u32 d, a, b` | `d = a * b` (32-bit inputs, 64-bit result) |
| `fma.rn.f32 d, a, b, c` | `d = a * b + c` (fused, round-to-nearest) |
| `rsqrt.approx.f32 d, a` | `d = 1/sqrt(a)` (fast approximate) |
| `setp.ge.u32 p, a, b` | Set predicate `p = (a >= b)` |
| `@p bra LABEL` | Branch to LABEL if predicate p is true |
| `selp.f32 d, a, b, p` | `d = p ? a : b` (predicated select) |

See [PTX Primer](../explanation/ptx-primer.md) for detailed explanations.

## The Python Wrapper Pattern

Every PTX kernel needs a Python wrapper in `ptx/<map_type>.py`. The wrapper handles:

1. PTX module loading and caching
2. Input preprocessing (grayscale conversion, etc.)
3. Output buffer allocation
4. Grid/block configuration
5. Kernel launch
6. Post-processing (Gaussian blur, contrast, etc.)

### Template

```python
"""PTX-accelerated <map_type> map generation."""

from pathlib import Path

import cupy as cp
import numpy as np

from textureworks.core.gpu import grid_size, recommended_block_size
from textureworks.core.io import to_grayscale

_PTX_DIR = Path(__file__).parent / "kernels"
_kernel_cache = {}


def _get_kernel(name: str, entry: str):
    """Load and cache a PTX kernel via the CUDA driver API."""
    if name not in _kernel_cache:
        ptx_source = (_PTX_DIR / f"{name}.ptx").read_text()
        mod = cp.cuda.function.Module()
        mod.load(ptx_source.encode("utf-8"))
        _kernel_cache[name] = mod
    return _kernel_cache[name].get_function(entry)


def generate_<map_type>(texture: cp.ndarray, ...) -> cp.ndarray:
    """Generate a <map_type> map using hand-written PTX kernel."""
    gray = to_grayscale(texture)
    h, w = gray.shape
    output = cp.empty((h, w), dtype=cp.float32)

    kernel = _get_kernel("<map_type>", "<kernel_entry_name>")
    block = recommended_block_size()
    grid = grid_size(w, h, block)

    kernel(
        grid=(grid[0], grid[1], 1),
        block=(block[0], block[1], 1),
        args=(gray.data.ptr, output.data.ptr,
              np.int32(w), np.int32(h), ...),
        shared_mem=0,
    )
    return output
```

Key details:
- `_get_kernel` caches loaded PTX modules to avoid repeated file I/O
- `recommended_block_size()` returns `(16, 16)` for all kernels
- `grid_size()` computes `ceil(dim / 16)` for both dimensions
- Kernel arguments pass as `np.int32`, `np.float32`, or `.data.ptr` (for CuPy array pointers)
- `shared_mem=0` for kernels not using shared memory

### Multi-Kernel Pipelines

For map types requiring multiple kernel passes (height uses 4, roughness uses 3), use `_get_module` to load the PTX module once and call `mod.get_function()` for each kernel:

```python
def _get_module(name: str):
    """Load and cache a PTX module."""
    if name not in _module_cache:
        ptx_source = (_PTX_DIR / f"{name}.ptx").read_text()
        mod = cp.cuda.function.Module()
        mod.load(ptx_source.encode("utf-8"))
        _module_cache[name] = mod
    return _module_cache[name]

# Usage
mod = _get_module("roughness")
var_kernel = mod.get_function("roughness_variance_kernel")
sobel_kernel = mod.get_function("roughness_sobel_kernel")
blend_kernel = mod.get_function("roughness_blend_kernel")
```

## Pipeline Integration

Register the new map type in `textureworks/pipeline.py`:

1. Add the type name to the `MAP_TYPES` tuple
2. The lazy import in `_get_generator` handles the rest automatically, as long as the module follows the naming convention: `textureworks.cupy_ref.<map_type>` and `textureworks.ptx.<map_type>` with a `generate_<map_type>` function

## Checklist

- [ ] Algorithm spec added to `docs/algorithms.md`
- [ ] CuPy reference implementation in `cupy_ref/<map_type>.py`
- [ ] PTX kernel in `ptx/kernels/<map_type>.ptx` with header comment
- [ ] Python wrapper in `ptx/<map_type>.py` using `_get_kernel` or `_get_module`
- [ ] Test file in `tests/test_<map_type>.py` comparing CuPy vs PTX output
- [ ] Map type registered in `pipeline.py` `MAP_TYPES` tuple
- [ ] Documentation updated

## Further Reading

- [PTX Primer](../explanation/ptx-primer.md) for PTX language fundamentals
- [PTX Kernel Reference](../reference/ptx-kernels.md) for existing kernel documentation
- [Architecture](../explanation/architecture.md) for the dual-implementation design
- [Contributing](../dev/contributing.md) for the full contributor workflow
