# PTX Assembly: What You Need to Know

This document introduces PTX (Parallel Thread Execution), NVIDIA's virtual instruction set architecture, using TextureWorks kernels as concrete examples.

## PTX in the NVIDIA Compilation Pipeline

NVIDIA GPUs do not execute PTX directly. The compilation chain looks like this:

```
CUDA C/C++ source
       |
       v  (nvcc front-end)
PTX (virtual ISA)
       |
       v  (ptxas / JIT compiler)
SASS (device machine code)
```

PTX is an intermediate representation. It resembles assembly but targets a virtual machine with unlimited registers and a simplified memory model. The actual hardware instruction set (SASS) is generated from PTX by the driver's JIT compiler at load time.

TextureWorks skips the CUDA C step entirely. The `.ptx` files are hand-written and loaded at runtime via `cupy.cuda.function.Module`. This approach provides direct control over GPU instructions while preserving Python's development workflow.

## The Virtual Register Model

PTX registers are typed and unlimited. You declare them in the kernel body:

```
.reg .f32   grad_x, grad_y;       // 32-bit floats
.reg .u32   px_x, px_y;           // 32-bit unsigned integers
.reg .s32   cx, cy;               // 32-bit signed integers
.reg .u64   ptr_in, addr;         // 64-bit unsigned (pointers)
.reg .pred  p_oob;                // 1-bit predicate (boolean)
```

Common types used in TextureWorks:

| Type | Size | Use |
|------|------|-----|
| `.f32` | 32 bits | Pixel values, gradients, parameters |
| `.u32` | 32 bits | Dimensions, pixel coordinates, loop counters |
| `.s32` | 32 bits | Signed coordinates (for neighbor offsets) |
| `.u64` | 64 bits | Pointers to GPU memory |
| `.pred` | 1 bit | Conditional predicates for branching |

The PTX JIT compiler maps virtual registers to physical hardware registers. Using meaningful names (like `grad_x` instead of `r12`) costs nothing at runtime and improves readability.

## Memory Spaces

PTX defines several memory spaces. TextureWorks kernels use three:

**`.param`** (parameter memory): Read-only. Kernel arguments arrive here. Every kernel begins by loading parameters into registers:

```
ld.param.u64    ptr_in, [param_input];
ld.param.u32    width, [param_width];
ld.param.f32    strength, [param_strength];
```

**`.global`** (global memory): Read-write. The main GPU memory (VRAM). Input textures and output maps live here. Accessed via `ld.global` and `st.global`:

```
ld.global.f32   val, [addr];       // load float from GPU memory
st.global.f32   [addr], result;    // store float to GPU memory
```

**`.shared`** (shared memory): Read-write. Fast on-chip memory shared within a thread block. TextureWorks kernels currently do not use shared memory (`shared_mem=0` in all launch calls), but tile-based convolution optimizations could leverage it.

## Thread Model: From Thread IDs to Pixel Coordinates

Every PTX kernel runs across thousands of threads organized in a 2D grid of blocks. Three special registers identify each thread:

| Register | Meaning |
|----------|---------|
| `%tid.x`, `%tid.y` | Thread index within the block (0 to blockDim-1) |
| `%ctaid.x`, `%ctaid.y` | Block index within the grid (0 to gridDim-1) |
| `%ntid.x`, `%ntid.y` | Block dimensions (threads per block) |

The standard pattern for computing global pixel coordinates:

```
// px_x = blockIdx.x * blockDim.x + threadIdx.x
mov.u32         px_x, %tid.x;
mov.u32         tmp, %ctaid.x;
mov.u32         blk, %ntid.x;
mad.lo.u32      px_x, tmp, blk, px_x;   // px_x = tmp * blk + px_x
```

`mad.lo.u32` is multiply-add: `result = a * b + c`. This single instruction replaces a multiply and an add.

With 16x16 blocks on a 1024x1024 image, the grid is 64x64 blocks = 4096 blocks. Each block has 256 threads. Total: 1,048,576 threads, one per pixel.

## Worked Example: The Normal Map Kernel

Here is a trace through `sobel_normal_kernel` in `ptx/kernels/normal.ptx`, explaining each phase.

### Phase 1: Parameter Loading

```
ld.param.u64    ptr_in, [param_input];      // input grayscale array pointer
ld.param.u64    ptr_out, [param_output];     // output RGB array pointer
ld.param.u32    width, [param_width];        // image width
ld.param.u32    height, [param_height];      // image height
ld.param.f32    strength, [param_strength];  // exaggeration factor
```

Each `ld.param` copies a kernel argument from parameter memory into a register.

### Phase 2: Coordinate Computation

```
mov.u32         px_x, %tid.x;
mov.u32         tmp_u32, %ctaid.x;
mov.u32         blk_u32, %ntid.x;
mad.lo.u32      px_x, tmp_u32, blk_u32, px_x;
```

Computes `px_x = blockIdx.x * blockDim.x + threadIdx.x`. Same pattern for `px_y`.

### Phase 3: Boundary Check

```
setp.ge.u32     p_oob_x, px_x, width;       // p_oob_x = (px_x >= width)
setp.ge.u32     p_oob_y, px_y, height;       // p_oob_y = (px_y >= height)
or.pred         p_oob, p_oob_x, p_oob_y;    // p_oob = either out of bounds
@p_oob bra      EXIT;                        // skip to exit if out of bounds
```

The grid may be larger than the image (grid = ceil(dim/16) * 16). Threads beyond image boundaries must not read or write memory. `setp` sets a predicate register, and `@p_oob bra` is a predicated branch.

### Phase 4: Loading the 3x3 Neighborhood

For each of the 9 neighbors (top-left through bottom-right):

```
add.s32 cx, sx, -1;                          // cx = x - 1
max.s32 cx, cx, 0;                           // clamp to 0
min.s32 cx, cx, width_m1;                    // clamp to width-1
add.s32 cy, sy, -1;                          // cy = y - 1
max.s32 cy, cy, 0;
min.s32 cy, cy, height_m1;
mad.lo.u32 offset_u32, cy, width, cx;        // linear index = cy * width + cx
mul.wide.u32 offset_u64, offset_u32, 4;      // byte offset (4 bytes per float32)
add.u64 addr, ptr_in, offset_u64;            // absolute address
ld.global.f32 s_tl, [addr];                  // load the pixel value
```

`mul.wide.u32` widens a 32-bit multiply to produce a 64-bit result, needed because GPU memory pointers are 64-bit.

### Phase 5: Sobel Gradient Computation

```
neg.f32     grad_x, s_tl;                    // grad_x = -s_tl
add.f32     grad_x, grad_x, s_tr;            // grad_x += s_tr
fma.rn.f32  grad_x, s_ml, -2.0, grad_x;     // grad_x += s_ml * (-2.0)
fma.rn.f32  grad_x, s_mr, 2.0, grad_x;      // grad_x += s_mr * 2.0
sub.f32     grad_x, grad_x, s_bl;            // grad_x -= s_bl
add.f32     grad_x, grad_x, s_br;            // grad_x += s_br
```

`fma.rn.f32` is fused multiply-add with round-to-nearest: `result = a * b + c` in a single instruction with no intermediate rounding.

### Phase 6: Normalization

```
mul.f32         norm_len, norm_x, norm_x;         // len = nx^2
fma.rn.f32      norm_len, norm_y, norm_y, norm_len; // len += ny^2
fma.rn.f32      norm_len, norm_z, norm_z, norm_len; // len += nz^2
rsqrt.approx.f32 inv_len, norm_len;               // inv_len = 1/sqrt(len)
mul.f32         norm_x, norm_x, inv_len;           // normalize
```

`rsqrt.approx.f32` computes the reciprocal square root in a single hardware instruction. The `.approx` suffix allows reduced precision for speed. For 8-bit output, 23-bit accuracy is more than sufficient.

### Phase 7: Encoding and Storage

```
fma.rn.f32      enc_r, norm_x, 0.5, 0.5;     // R = nx * 0.5 + 0.5
fma.rn.f32      enc_g, norm_y, 0.5, 0.5;     // G = ny * 0.5 + 0.5
fma.rn.f32      enc_b, norm_z, 0.5, 0.5;     // B = nz * 0.5 + 0.5

mad.lo.u32      offset_u32, px_y, width, px_x;  // pixel index
mul.lo.u32      stride3, offset_u32, 3;          // RGB index = pixel * 3
mul.wide.u32    offset_u64, stride3, 4;          // byte offset
add.u64         addr, ptr_out, offset_u64;
st.global.f32   [addr], enc_r;                   // store R
add.u64         addr, addr, 4;
st.global.f32   [addr], enc_g;                   // store G
add.u64         addr, addr, 4;
st.global.f32   [addr], enc_b;                   // store B
```

Output is interleaved RGB: three consecutive float32 values per pixel.

## Key PTX Instructions in TextureWorks

| Instruction | Purpose | Used In |
|-------------|---------|---------|
| `ld.global.f32` | Load float from GPU memory | All kernels |
| `st.global.f32` | Store float to GPU memory | All kernels |
| `mad.lo.u32` | Multiply-add (index computation) | All kernels |
| `mul.wide.u32` | 32-bit multiply with 64-bit result (byte offsets) | All kernels |
| `fma.rn.f32` | Fused multiply-add | Sobel, normalization, blending |
| `rsqrt.approx.f32` | Fast reciprocal square root | Normal map |
| `cos.approx.f32` | Approximate cosine | AO kernel |
| `sin.approx.f32` | Approximate sine | AO kernel |
| `lg2.approx.f32` | Approximate log base 2 | AO, specular (power function) |
| `ex2.approx.f32` | Approximate 2^x | AO, specular (power function) |
| `setp.*` | Set predicate (comparison) | All kernels (boundary checks) |
| `@pred bra` | Predicated branch | All kernels (early exit, loops) |
| `selp.f32` | Select based on predicate | Metallic (hard edge threshold) |

## Further PTX Learning

- [PTX ISA Reference](https://docs.nvidia.com/cuda/parallel-thread-execution/): NVIDIA's official specification
- [CUDA C Programming Guide](https://docs.nvidia.com/cuda/cuda-c-programming-guide/): Higher-level context for the GPU execution model
- Read the TextureWorks `.ptx` files in order of complexity: `metallic.ptx` (simplest, one kernel, no loops) -> `normal.ptx` (convolution) -> `height.ptx` (multi-kernel pipeline) -> `roughness.ptx` (multi-kernel with windowed operations) -> `ao.ptx` (nested loops, trig approximation)
