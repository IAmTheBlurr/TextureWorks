# Algorithm Specifications — TextureWorks

This document defines the mathematical operations for each texture map type.
Implementations in both CuPy and PTX must conform to these specifications.
The CuPy implementation is the correctness oracle; the PTX implementation
must produce output matching the CuPy version within the stated tolerance.

The consuming shader's [Parallax Occlusion Mapping contract](reference/parallax-algorithm.md)
specifies ray traversal through the generated height field. It uses the existing
height implementations and optional 16-bit export.

---

## 1. Normal Map

### Purpose
Encode per-pixel surface orientation as an RGB normal vector. Game engines
use normal maps to simulate geometric detail without additional polygons.

### Algorithm: Sobel Gradient → Normal Encoding

**Step 1: Convert to grayscale (if RGB input)**

```
L(x,y) = 0.2126 * R + 0.7152 * G + 0.0722 * B
```

Standard ITU-R BT.709 luminance weights.

**Step 2: Compute horizontal and vertical gradients**

Sobel kernels:

```
Kx = [-1  0  1]    Ky = [-1 -2 -1]
     [-2  0  2]         [ 0  0  0]
     [ 1  0  1]         [ 1  2  1]
```

```
Gx(x,y) = sum over (i,j) in [-1,1]: Kx(i,j) * L(x+i, y+j)
Gy(x,y) = sum over (i,j) in [-1,1]: Ky(i,j) * L(x+i, y+j)
```

Boundary handling: clamp (replicate edge pixels).

**Step 3: Construct and normalize the normal vector**

```
strength = user parameter (default 2.0, range [0.1, 20.0])

N = normalize( -Gx * strength, -Gy * strength, 1.0 )
```

The `strength` parameter controls the perceived depth of surface detail.
Higher values exaggerate the relief.

**Step 4: Encode to RGB [0, 255]**

```
R = (N.x * 0.5 + 0.5) * 255
G = (N.y * 0.5 + 0.5) * 255
B = (N.z * 0.5 + 0.5) * 255
```

A flat surface produces (128, 128, 255).

### Parameters
| Name     | Type  | Default | Range       | Effect                    |
|----------|-------|---------|-------------|---------------------------|
| strength | float | 2.0     | [0.1, 20.0] | Depth exaggeration factor |

### Tolerance
Max absolute per-channel difference between CuPy and PTX: **1** (rounding).

---

## 2. Height Map

### Purpose
Encode perceived surface elevation as a grayscale image. White represents
high points, black represents low points.

### Algorithm: Luminance Extraction with Contrast Enhancement

**Step 1: Convert to grayscale**

Same BT.709 luminance formula as the normal map.

```
L(x,y) = 0.2126 * R + 0.7152 * G + 0.0722 * B
```

**Step 2: Normalize to full range**

```
L_min = min(L)
L_max = max(L)
H(x,y) = (L(x,y) - L_min) / (L_max - L_min)
```

**Step 3: Optional Gaussian blur for smoothing**

Gaussian kernel with configurable sigma. This removes high-frequency
noise and produces smoother displacement.

```
G(x,y) = (1 / (2 * pi * sigma^2)) * exp(-(x^2 + y^2) / (2 * sigma^2))
H_smooth = H * G  (convolution)
```

**Step 4: Contrast adjustment**

```
H_final = clamp( ((H_smooth - 0.5) * contrast + 0.5), 0.0, 1.0 )
```

**Step 5: Encode to grayscale [0, 255]**

```
output(x,y) = round(H_final(x,y) * 255)
```

### Parameters
| Name       | Type  | Default | Range      | Effect                     |
|------------|-------|---------|------------|----------------------------|
| blur_sigma | float | 1.0     | [0.0, 10.0]| Smoothing radius          |
| contrast   | float | 1.2     | [0.5, 3.0] | Contrast multiplier       |
| invert     | bool  | false   |            | Flip height interpretation |

### Tolerance
Max absolute difference: **2** (blur floating point variance).

---

## 3. Ambient Occlusion

### Purpose
Approximate how much ambient light reaches each surface point. Concavities
and crevices appear darker. Exposed surfaces remain bright.

### Algorithm: Screen-Space Horizon Mapping from Height Field

**Prerequisites:** Requires a height map (Algorithm 2 output).

**Step 1: For each pixel, cast rays in N directions**

Default: 16 directions, evenly spaced around 360 degrees.

```
angles = [i * (2 * pi / num_directions) for i in range(num_directions)]
```

**Step 2: Along each ray, march steps and compute horizon angle**

```
for each direction d:
    max_elevation = 0
    for step s in [1, max_steps]:
        sample_x = x + cos(angles[d]) * s * step_scale
        sample_y = y + sin(angles[d]) * s * step_scale
        delta_h = H(sample_x, sample_y) - H(x, y)
        distance = s * step_scale
        elevation = atan2(delta_h * height_scale, distance)
        max_elevation = max(max_elevation, elevation)
    occlusion[d] = max_elevation
```

**Step 3: Average occlusion across all directions**

```
avg_occlusion = mean(occlusion)
ao(x,y) = 1.0 - (avg_occlusion / (pi / 2))
```

**Step 4: Power curve for artistic control**

```
ao_final(x,y) = pow(ao(x,y), power)
```

**Step 5: Encode to grayscale [0, 255]**

### Parameters
| Name           | Type  | Default | Range      | Effect                     |
|----------------|-------|---------|------------|----------------------------|
| num_directions | int   | 16      | [4, 64]   | Angular sampling density    |
| max_steps      | int   | 20      | [4, 64]   | Ray march distance          |
| step_scale     | float | 1.0     | [0.5, 4.0]| Pixel distance per step     |
| height_scale   | float | 10.0    | [0.1, 50.0]| Height map influence       |
| power          | float | 1.5     | [0.5, 4.0] | Contrast power curve       |

### Tolerance
Max absolute difference: **3** (trigonometric and sampling variance).

---

## 4. Roughness Map

### Purpose
Encode surface micro-roughness. Rough areas scatter light diffusely;
smooth areas produce sharp reflections.

### Algorithm: Local Variance Analysis

**Step 1: Convert to grayscale**

Same BT.709 luminance formula.

**Step 2: Compute local mean in a window**

```
window_size = radius * 2 + 1
mean(x,y) = (1/N) * sum of L(x+i, y+j) for (i,j) in [-radius, radius]
```

**Step 3: Compute local variance**

```
var(x,y) = (1/N) * sum of (L(x+i, y+j) - mean(x,y))^2
```

**Step 4: Compute edge density (Sobel magnitude)**

```
edge(x,y) = sqrt(Gx(x,y)^2 + Gy(x,y)^2)
```

**Step 5: Blend variance and edge signals**

```
raw_roughness = alpha * normalize(var) + (1 - alpha) * normalize(edge)
```

Where `normalize` maps each signal to [0, 1] range.

**Step 6: Apply smoothing and contrast**

Gaussian blur with small sigma to reduce noise, then contrast stretch.

### Parameters
| Name      | Type  | Default | Range      | Effect                     |
|-----------|-------|---------|------------|----------------------------|
| radius    | int   | 4       | [1, 16]   | Analysis window half-size   |
| alpha     | float | 0.6     | [0.0, 1.0]| Variance vs edge weight    |
| blur      | float | 1.0     | [0.0, 5.0]| Output smoothing           |
| contrast  | float | 1.5     | [0.5, 3.0]| Output contrast            |

### Tolerance
Max absolute difference: **3**.

---

## 5. Metallic Map

### Purpose
Classify each pixel as metallic (1.0/white) or dielectric (0.0/black).
PBR workflows typically use binary or near-binary metallic maps.

### Algorithm: HSV Saturation and Value Thresholding

**Step 1: Convert RGB to HSV**

Standard RGB→HSV conversion.

**Step 2: Classify based on saturation and value**

Metallic surfaces tend to be desaturated with moderate-to-high value.

```
is_metallic(x,y) = (S(x,y) < sat_threshold) AND (V(x,y) > val_threshold)
```

**Step 3: Soft classification (optional)**

For smoother results, compute a metallic score:

```
sat_score = 1.0 - clamp(S(x,y) / sat_threshold, 0, 1)
val_score = clamp((V(x,y) - val_threshold) / val_range, 0, 1)
metallic(x,y) = sat_score * val_score
```

The `val_range` parameter controls the soft transition width above `val_threshold`.
Pixels with value at or above `val_threshold + val_range` receive full val_score of 1.0.
This avoids penalizing dark metallic surfaces where V is moderate (e.g. 0.3-0.5).

**Step 4: Apply Gaussian blur for smooth transitions**

**Step 5: Optional binary threshold**

```
if hard_edges:
    metallic(x,y) = 1.0 if metallic(x,y) > 0.5 else 0.0
```

### Parameters
| Name          | Type  | Default | Range      | Effect                        |
|---------------|-------|---------|------------|-------------------------------|
| sat_threshold | float | 0.35    | [0.05, 0.5]| Max saturation for metal     |
| val_threshold | float | 0.10    | [0.01, 0.8]| Min value for metal          |
| val_range     | float | 0.3     | [0.1, 1.0] | Soft transition width for V  |
| blur          | float | 2.0     | [0.0, 5.0] | Output smoothing             |
| hard_edges    | bool  | false   |            | Binary classification         |

### Tolerance
Max absolute difference: **2**.

---

## 6. Specular Map

### Purpose
Encode per-pixel specular reflectance intensity. Bright areas reflect
more light. Used in non-PBR or legacy rendering pipelines; also useful
as a supplementary map in PBR workflows.

### Algorithm: Luminance-Weighted Saturation Inversion

**Step 1: Compute luminance and saturation**

```
L(x,y) = 0.2126 * R + 0.7152 * G + 0.0722 * B   (BT.709)
S(x,y) = HSV saturation
```

**Step 2: Compute base specular**

High luminance and low saturation both increase specularity.

```
spec(x,y) = L(x,y) * (1.0 - S(x,y) * sat_weight)
```

**Step 3: Normalize to [0, 1]**

```
spec_norm = (spec - min(spec)) / (max(spec) - min(spec))
```

**Step 4: Contrast and power curve**

```
spec_final = pow(spec_norm * contrast, power)
```

**Step 5: Gaussian blur and encode to [0, 255]**

### Parameters
| Name       | Type  | Default | Range      | Effect                     |
|------------|-------|---------|------------|----------------------------|
| sat_weight | float | 0.5     | [0.0, 1.0]| Saturation reduction factor|
| contrast   | float | 1.3     | [0.5, 3.0]| Output contrast            |
| power      | float | 1.2     | [0.5, 3.0]| Specular falloff curve     |
| blur       | float | 0.5     | [0.0, 5.0]| Output smoothing           |

### Tolerance
Max absolute difference: **2**.

---

## Implementation Notes

### Gaussian Blur (Shared Utility)

Used by multiple algorithms. Implement once in `core/`, expose to both
CuPy and PTX paths.

Separable implementation: apply 1D horizontal pass, then 1D vertical pass.
This reduces O(N * k^2) to O(N * 2k) where k is the kernel radius.

Kernel generation:

```
weights[i] = exp(-i^2 / (2 * sigma^2))
normalize so sum(weights) = 1.0
```

### Boundary Handling

All convolutions use clamp-to-edge: pixels outside the image boundary
sample the nearest edge pixel. In PTX, implement via `min(max(coord, 0), dim-1)`.

### Float Precision

Internal computation uses float32 throughout. Quantization to uint8
happens only at the final encoding step. This prevents accumulated
rounding errors in multi-step algorithms.
