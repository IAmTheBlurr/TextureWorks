# PTX Kernel Reference

Technical reference for each PTX kernel file in `textureworks/ptx/kernels/`. All kernels target `sm_75` (Turing+) and use PTX ISA version 7.0 with 64-bit addressing.

All kernels use 16x16 thread blocks (256 threads). Grid dimensions are computed as `ceil(width / 16)` by `ceil(height / 16)`.

## normal.ptx

**Kernel:** `sobel_normal_kernel`

**Purpose:** Compute per-pixel surface normals from a grayscale height field using 3x3 Sobel convolution, then encode as RGB.

### Parameter Layout

| Position | Name | PTX Type | Size | Description |
|----------|------|----------|------|-------------|
| 0 | `param_input` | `.u64` | 8 bytes | Pointer to (H*W) row-major grayscale float32 array |
| 1 | `param_output` | `.u64` | 8 bytes | Pointer to (H*W*3) row-major interleaved RGB float32 array |
| 2 | `param_width` | `.u32` | 4 bytes | Image width in pixels |
| 3 | `param_height` | `.u32` | 4 bytes | Image height in pixels |
| 4 | `param_strength` | `.f32` | 4 bytes | Depth exaggeration factor |

### Register Naming

| Prefix | Purpose | Examples |
|--------|---------|---------|
| `px_` | Pixel coordinates | `px_x`, `px_y` |
| `s_` | 3x3 neighborhood samples | `s_tl`, `s_tc`, `s_tr`, `s_ml`, `s_mc`, `s_mr`, `s_bl`, `s_bc`, `s_br` |
| `grad_` | Sobel gradient values | `grad_x`, `grad_y` |
| `norm_` | Normal vector components | `norm_x`, `norm_y`, `norm_z`, `norm_len` |
| `enc_` | Encoded RGB output | `enc_r`, `enc_g`, `enc_b` |

### Memory Access Pattern

Global memory only. Each thread loads a 3x3 neighborhood (9 float32 values) with clamp-to-edge boundary handling, then stores 3 interleaved float32 values (RGB).

### Boundary Handling

Threads outside image dimensions exit early via predicated branch. Neighbor coordinates are clamped to [0, width-1] and [0, height-1] using `max`/`min` instructions.

### Optimization Notes

Uses `rsqrt.approx.f32` for fast reciprocal square root during vector normalization. This instruction provides approximately 23-bit accuracy, more than sufficient for 8-bit output.

---

## height.ptx

Contains four kernels launched sequentially by the Python wrapper.

### Kernel 1: `height_normalize_kernel`

**Purpose:** Normalize grayscale values to [0, 1] using pre-computed min and range.

| Position | Name | PTX Type | Description |
|----------|------|----------|-------------|
| 0 | `param_input` | `.u64` | Input grayscale array pointer |
| 1 | `param_output` | `.u64` | Output normalized array pointer |
| 2 | `param_width` | `.u32` | Image width |
| 3 | `param_height` | `.u32` | Image height |
| 4 | `param_lmin` | `.f32` | Pre-computed minimum luminance |
| 5 | `param_lrange` | `.f32` | Pre-computed range (lmax - lmin) |

Formula: `output = (input - lmin) / lrange`

### Kernel 2: `height_blur_h_kernel`

**Purpose:** Horizontal Gaussian blur pass.

| Position | Name | PTX Type | Description |
|----------|------|----------|-------------|
| 0 | `param_input` | `.u64` | Input array pointer |
| 1 | `param_output` | `.u64` | Output array pointer |
| 2 | `param_weights` | `.u64` | Gaussian weight array pointer |
| 3 | `param_radius` | `.s32` | Kernel half-width (weights length = 2*radius+1) |
| 4 | `param_width` | `.u32` | Image width |
| 5 | `param_height` | `.u32` | Image height |

Iterates `i` from `-radius` to `+radius`. Samples `input[y, clamp(x+i, 0, width-1)]` and accumulates `sample * weights[i + radius]`.

### Kernel 3: `height_blur_v_kernel`

**Purpose:** Vertical Gaussian blur pass. Identical structure to the horizontal kernel but iterates along the y-axis.

Same parameter layout as `height_blur_h_kernel`.

### Kernel 4: `height_contrast_kernel`

**Purpose:** Contrast adjustment and optional invert (in-place).

| Position | Name | PTX Type | Description |
|----------|------|----------|-------------|
| 0 | `param_data` | `.u64` | Array pointer (modified in-place) |
| 1 | `param_width` | `.u32` | Image width |
| 2 | `param_height` | `.u32` | Image height |
| 3 | `param_contrast` | `.f32` | Contrast multiplier |
| 4 | `param_invert` | `.u32` | 0 = no invert, 1 = invert |

Formula: `val = clamp((val - 0.5) * contrast + 0.5, 0.0, 1.0)`. If `invert == 1`: `val = 1.0 - val`. Uses `setp.eq.u32` and predicated `mov.f32` for branchless invert.

---

## ao.ptx

**Kernel:** `ao_kernel`

**Purpose:** Compute per-pixel ambient occlusion by casting rays in multiple directions over a height field and measuring horizon angles.

### Parameter Layout

| Position | Name | PTX Type | Size | Description |
|----------|------|----------|------|-------------|
| 0 | `param_hmap` | `.u64` | 8 bytes | Height map array pointer, (H*W) float32 |
| 1 | `param_output` | `.u64` | 8 bytes | Output AO array pointer |
| 2 | `param_width` | `.u32` | 4 bytes | Image width |
| 3 | `param_height` | `.u32` | 4 bytes | Image height |
| 4 | `param_num_dirs` | `.u32` | 4 bytes | Number of ray directions |
| 5 | `param_max_steps` | `.u32` | 4 bytes | Maximum steps per ray |
| 6 | `param_step_scale` | `.f32` | 4 bytes | Pixel distance per step |
| 7 | `param_height_scale` | `.f32` | 4 bytes | Height influence on elevation angle |
| 8 | `param_power` | `.f32` | 4 bytes | Contrast power curve exponent |

### Register Naming

| Prefix | Purpose |
|--------|---------|
| `px_` | Pixel coordinates |
| `center_h` | Height at the current pixel |
| `occ_sum` | Accumulated occlusion across all directions |
| `dir_i`, `step_i` | Loop counters |
| `cos_val`, `sin_val` | Direction trigonometry |
| `max_elev` | Maximum elevation angle for the current direction |
| `fx`, `fy` | Float sample coordinates |
| `sxi`, `syi` | Integer (clamped) sample coordinates |
| `delta_h`, `dist`, `elev` | Height difference, distance, elevation angle |
| `at_*` | atan2 approximation temporaries |
| `pow_*` | Power function temporaries |

### Memory Access Pattern

Global memory with irregular access patterns due to ray marching. Each thread reads the center pixel once, then accesses height values along rays in multiple directions. Relies on L2 cache for repeated height map lookups.

### Boundary Handling

Out-of-bounds threads exit early. Sample coordinates along rays are rounded to nearest integer (`cvt.rni.s32.f32`) and clamped to [0, width-1] and [0, height-1].

### Optimization Notes

**atan2 approximation:** PTX has no native atan2 instruction. The kernel uses a polynomial approximation: `atan(t) ~ t * (1.0 - 0.2447 * t^2)` for `t` in [0, 1], with the identity `atan(t) = pi/2 - atan(1/t)` for `t > 1`. Quadrant correction applies the sign of the numerator.

**Power function:** Computed as `pow(x, p) = exp2(p * log2(x))` using `lg2.approx.f32` and `ex2.approx.f32`. The base is clamped to 0.000001 to guard against `log2(0)`.

**Trigonometry:** Direction angles use `cos.approx.f32` and `sin.approx.f32` for fast approximate trig.

---

## roughness.ptx

Contains three kernels launched sequentially by the Python wrapper.

### Kernel 1: `roughness_variance_kernel`

**Purpose:** Compute local variance in a (2*radius+1)^2 window using the formula `var = E[X^2] - E[X]^2`.

| Position | Name | PTX Type | Description |
|----------|------|----------|-------------|
| 0 | `param_input` | `.u64` | Input grayscale array pointer |
| 1 | `param_output` | `.u64` | Output variance array pointer |
| 2 | `param_width` | `.u32` | Image width |
| 3 | `param_height` | `.u32` | Image height |
| 4 | `param_radius` | `.s32` | Window half-size |

Uses nested loops: `loop_dy` from `-radius` to `+radius`, `loop_dx` from `-radius` to `+radius`. Accumulates `sum_val` and `sum_sq`, then computes `var = sum_sq/N - (sum_val/N)^2`. Clamps variance to >= 0 for numerical safety.

### Kernel 2: `roughness_sobel_kernel`

**Purpose:** Compute Sobel edge magnitude `sqrt(Gx^2 + Gy^2)`.

| Position | Name | PTX Type | Description |
|----------|------|----------|-------------|
| 0 | `param_input` | `.u64` | Input grayscale array pointer |
| 1 | `param_output` | `.u64` | Output edge magnitude array pointer |
| 2 | `param_width` | `.u32` | Image width |
| 3 | `param_height` | `.u32` | Image height |

Same 3x3 Sobel implementation as `normal.ptx` but outputs magnitude instead of encoded normals. Uses `sqrt.rn.f32` for the final magnitude.

### Kernel 3: `roughness_blend_kernel`

**Purpose:** Normalize variance and edge signals, blend them, and apply contrast.

| Position | Name | PTX Type | Description |
|----------|------|----------|-------------|
| 0 | `param_var` | `.u64` | Variance array pointer |
| 1 | `param_edge` | `.u64` | Edge magnitude array pointer |
| 2 | `param_output` | `.u64` | Output array pointer |
| 3 | `param_width` | `.u32` | Image width |
| 4 | `param_height` | `.u32` | Image height |
| 5 | `param_alpha` | `.f32` | Blend weight (variance vs edge) |
| 6 | `param_var_min` | `.f32` | Variance minimum (for normalization) |
| 7 | `param_var_range` | `.f32` | Variance range (for normalization) |
| 8 | `param_edge_min` | `.f32` | Edge minimum (for normalization) |
| 9 | `param_edge_range` | `.f32` | Edge range (for normalization) |
| 10 | `param_contrast` | `.f32` | Contrast multiplier |

Formula: `result = alpha * norm_var + (1-alpha) * norm_edge`, followed by contrast `result = clamp((result - 0.5) * contrast + 0.5, 0.0, 1.0)`.

The Python wrapper passes `contrast=1.0` (identity) to this kernel and applies the actual contrast after Gaussian blur, matching the CuPy reference computation order.

---

## metallic.ptx

**Kernel:** `metallic_classify_kernel`

**Purpose:** Classify pixels as metallic or dielectric based on pre-computed HSV saturation and value channels.

### Parameter Layout

| Position | Name | PTX Type | Size | Description |
|----------|------|----------|------|-------------|
| 0 | `param_sat` | `.u64` | 8 bytes | Saturation channel array pointer |
| 1 | `param_val` | `.u64` | 8 bytes | Value channel array pointer |
| 2 | `param_output` | `.u64` | 8 bytes | Output metallic score array pointer |
| 3 | `param_width` | `.u32` | 4 bytes | Image width |
| 4 | `param_height` | `.u32` | 4 bytes | Image height |
| 5 | `param_sat_thresh` | `.f32` | 4 bytes | Maximum saturation for metal |
| 6 | `param_val_thresh` | `.f32` | 4 bytes | Minimum value for metal |
| 7 | `param_val_range` | `.f32` | 4 bytes | Soft transition width |
| 8 | `param_hard_edges` | `.u32` | 4 bytes | 0 = soft scoring, 1 = binary threshold |

### Memory Access Pattern

Simple paired loads at the same pixel offset from saturation and value arrays. Stores one float32 per pixel.

### Boundary Handling

Out-of-bounds threads exit early. Division-by-zero guard on `val_range` (`max val_range, 0.000001`).

### Hard Edge Implementation

Uses PTX predicated execution: `setp.eq.u32` checks the flag, then `setp.gt.f32` tests if metallic > 0.5, and `selp.f32` selects 1.0 or 0.0 based on the predicate.

---

## specular.ptx

**Kernel:** `specular_kernel`

**Purpose:** Compute per-pixel specular reflectance from pre-computed luminance and saturation. Applies normalization, contrast, and power curve.

### Parameter Layout

| Position | Name | PTX Type | Size | Description |
|----------|------|----------|------|-------------|
| 0 | `param_lum` | `.u64` | 8 bytes | Luminance array pointer |
| 1 | `param_sat` | `.u64` | 8 bytes | Saturation array pointer |
| 2 | `param_output` | `.u64` | 8 bytes | Output specular array pointer |
| 3 | `param_width` | `.u32` | 4 bytes | Image width |
| 4 | `param_height` | `.u32` | 4 bytes | Image height |
| 5 | `param_sat_weight` | `.f32` | 4 bytes | Saturation reduction factor |
| 6 | `param_contrast` | `.f32` | 4 bytes | Output contrast multiplier |
| 7 | `param_power` | `.f32` | 4 bytes | Specular falloff exponent |
| 8 | `param_spec_min` | `.f32` | 4 bytes | Pre-computed min of raw specular |
| 9 | `param_spec_range` | `.f32` | 4 bytes | Pre-computed range of raw specular |

### Memory Access Pattern

Paired loads from luminance and saturation at the same pixel offset. Single float32 store per pixel.

### Optimization Notes

Power function uses the same `exp2(power * log2(x))` approximation as `ao.ptx` with the same `log2(0)` guard (clamping base to 0.000001).
## Material field kernels

`material_fields.ptx` contains `detail_blur`, `detail_residual`, `surface_geometry`,
`wear_masks` and `layer_weight`. The wrappers in `textureworks/ptx/material_fields.py`
cache the module and launch 16x16 blocks. A shared `read_field` device function
implements clamp/wrap sampling. See the [field specification](material-fields.md)
for physical units, signs and tolerances; each entry documents parameter order.
