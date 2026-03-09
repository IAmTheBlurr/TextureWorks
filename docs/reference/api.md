# Python API Reference

Complete reference for every public function in TextureWorks, organized by module.

## textureworks.core.io

Image loading, saving, and format conversion utilities.

### `load_texture`

```python
def load_texture(path: str | Path) -> cp.ndarray
```

Load an image file and return a float32 GPU array in [0, 1] range.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str \| Path` | (required) | Path to PNG, JPG, or other Pillow-supported image |

**Returns:** `cupy.ndarray` with shape (H, W, 3) for RGB or (H, W) for grayscale, dtype float32, values in [0.0, 1.0].

RGBA images are automatically converted to RGB by dropping the alpha channel.

**Example:**

```python
from textureworks.core.io import load_texture

texture = load_texture("textures/test_texture3.png")
print(texture.shape)   # (1024, 1024, 3)
print(texture.dtype)   # float32
```

### `save_map`

```python
def save_map(data: cp.ndarray, path: str | Path) -> None
```

Save a GPU array as an 8-bit PNG. Creates parent directories automatically.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `data` | `cp.ndarray` | (required) | GPU array with values in [0.0, 1.0]. Shape (H, W) for grayscale or (H, W, 3) for RGB |
| `path` | `str \| Path` | (required) | Output file path |

**Returns:** None

Values are clipped to [0, 255] and converted to uint8 before saving.

**Example:**

```python
from textureworks.core.io import save_map

save_map(normal_map, "output/test_texture3_normal.png")
```

### `to_grayscale`

```python
def to_grayscale(rgb: cp.ndarray) -> cp.ndarray
```

Convert an RGB float32 array to grayscale using BT.709 luminance weights: `0.2126 * R + 0.7152 * G + 0.0722 * B`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `rgb` | `cp.ndarray` | (required) | (H, W, 3) float32 GPU array |

**Returns:** `cupy.ndarray` with shape (H, W), dtype float32. Returns the input unchanged if already 2D.

**Example:**

```python
from textureworks.core.io import load_texture, to_grayscale

texture = load_texture("textures/test_texture3.png")
gray = to_grayscale(texture)
print(gray.shape)  # (1024, 1024)
```

### `rgb_to_hsv`

```python
def rgb_to_hsv(rgb: cp.ndarray) -> tuple[cp.ndarray, cp.ndarray, cp.ndarray]
```

Convert an RGB float32 array to separate H, S, V channels.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `rgb` | `cp.ndarray` | (required) | (H, W, 3) float32 GPU array, values in [0, 1] |

**Returns:** Tuple of (H, S, V), each with shape (H, W), dtype float32. H is in [0, 1] (normalized from 0-360). S and V are in [0, 1].

**Example:**

```python
from textureworks.core.io import load_texture, rgb_to_hsv

texture = load_texture("textures/test_texture3.png")
hue, saturation, value = rgb_to_hsv(texture)
```

---

## textureworks.core.gpu

GPU device detection, selection, and capability reporting.

### `get_device_info`

```python
def get_device_info(device_id: int = 0) -> dict
```

Report GPU capabilities for the specified device.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `device_id` | `int` | `0` | GPU device index |

**Returns:** Dict with keys: `name` (str), `compute_capability` (str), `total_memory_mb` (float), `free_memory_mb` (float), `sm_count` (int), `max_threads_per_block` (int).

**Example:**

```python
from textureworks.core.gpu import get_device_info

info = get_device_info()
print(info["name"])            # "NVIDIA GeForce RTX 3080"
print(info["free_memory_mb"])  # 8192.0
```

### `print_device_info`

```python
def print_device_info(device_id: int = 0) -> None
```

Print GPU info to stdout in a human-readable format.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `device_id` | `int` | `0` | GPU device index |

**Returns:** None

### `recommended_block_size`

```python
def recommended_block_size() -> tuple[int, int]
```

Return a reasonable 2D block size for image processing kernels.

**Returns:** `(16, 16)` (256 threads per block).

### `grid_size`

```python
def grid_size(width: int, height: int, block: tuple[int, int] = (16, 16)) -> tuple[int, int]
```

Compute grid dimensions to cover an image of the given size.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `width` | `int` | (required) | Image width in pixels |
| `height` | `int` | (required) | Image height in pixels |
| `block` | `tuple[int, int]` | `(16, 16)` | Block dimensions (threads_x, threads_y) |

**Returns:** Tuple of (grid_x, grid_y) where `grid_x = ceil(width / block_x)` and `grid_y = ceil(height / block_y)`.

**Example:**

```python
from textureworks.core.gpu import grid_size

gx, gy = grid_size(1024, 768)
print(gx, gy)  # 64 48
```

---

## textureworks.core.blur

Separable Gaussian blur for float32 GPU arrays.

### `gaussian_kernel_1d`

```python
def gaussian_kernel_1d(sigma: float) -> cp.ndarray
```

Generate a normalized 1D Gaussian kernel on GPU.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sigma` | `float` | (required) | Standard deviation. If <= 0, returns identity kernel `[1.0]` |

**Returns:** 1D `cupy.ndarray` of float32 weights, length = `2 * ceil(3 * sigma) + 1`.

### `gaussian_blur`

```python
def gaussian_blur(image: cp.ndarray, sigma: float) -> cp.ndarray
```

Apply separable Gaussian blur to a 2D float32 GPU array. Uses clamp-to-edge boundary handling (nearest pixel replication).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `image` | `cp.ndarray` | (required) | (H, W) float32 GPU array |
| `sigma` | `float` | (required) | Blur sigma. If <= 0, returns a copy of the input |

**Returns:** Blurred (H, W) float32 `cupy.ndarray`.

Uses `cupyx.scipy.ndimage.convolve1d` internally for the separable two-pass convolution.

---

## textureworks.core.compare

Pixel-wise comparison between CuPy and PTX implementations.

### `compare_outputs`

```python
def compare_outputs(
    cupy_result: cp.ndarray,
    ptx_result: cp.ndarray,
    tolerance: int = 2,
) -> dict
```

Compare two GPU arrays and report agreement metrics. Both arrays are scaled to the uint8 range [0, 255] for comparison.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cupy_result` | `cp.ndarray` | (required) | Reference output from CuPy implementation |
| `ptx_result` | `cp.ndarray` | (required) | Output from PTX implementation |
| `tolerance` | `int` | `2` | Maximum acceptable per-pixel absolute difference on uint8 scale |

**Returns:** Dict with keys:
- `matches` (bool): True if max_diff <= tolerance
- `max_diff` (float): Maximum pixel-wise absolute difference
- `mean_diff` (float): Mean pixel-wise absolute difference
- `pct_within_tolerance` (float): Percentage of pixels within tolerance

**Example:**

```python
from textureworks.core.compare import compare_outputs

result = compare_outputs(cupy_normal, ptx_normal, tolerance=1)
print(result["matches"])    # True
print(result["max_diff"])   # 0.8
```

### `compare_and_report`

```python
def compare_and_report(
    cupy_result: cp.ndarray,
    ptx_result: cp.ndarray,
    map_name: str,
    tolerance: int = 2,
) -> bool
```

Compare outputs and print a human-readable report with PASS/FAIL status.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cupy_result` | `cp.ndarray` | (required) | Reference output |
| `ptx_result` | `cp.ndarray` | (required) | PTX output |
| `map_name` | `str` | (required) | Name of the map type (for display) |
| `tolerance` | `int` | `2` | Maximum acceptable difference |

**Returns:** `bool`. True if outputs match within tolerance.

**CLI usage:**

```bash
python -m textureworks.core.compare cupy_ref.normal ptx.normal textures/test_texture3.png
```

---

## textureworks.cupy_ref

CuPy reference implementations for all map types. These serve as the correctness oracle.

### `cupy_ref.normal.generate_normal`

```python
def generate_normal(texture: cp.ndarray, strength: float = 2.0) -> cp.ndarray
```

Generate a normal map from an RGB texture using Sobel gradients.

| Parameter | Type | Default | Valid Range | Description |
|-----------|------|---------|-------------|-------------|
| `texture` | `cp.ndarray` | (required) | (H, W, 3) float32, [0, 1] | Input RGB texture |
| `strength` | `float` | `2.0` | [0.1, 20.0] | Depth exaggeration factor. Higher values produce more pronounced surface bumps |

**Returns:** (H, W, 3) float32 `cupy.ndarray`, values in [0, 1]. RGB-encoded normal map where R=X, G=Y, B=Z. A flat surface encodes as (0.5, 0.5, 1.0).

**Example:**

```python
from textureworks.core.io import load_texture
from textureworks.cupy_ref.normal import generate_normal

texture = load_texture("textures/test_texture3.png")
normal_map = generate_normal(texture, strength=2.0)
```

### `cupy_ref.height.generate_height`

```python
def generate_height(
    texture: cp.ndarray,
    blur_sigma: float = 1.0,
    contrast: float = 1.2,
    invert: bool = False,
) -> cp.ndarray
```

Generate a height map from an RGB texture via luminance extraction with contrast enhancement.

| Parameter | Type | Default | Valid Range | Description |
|-----------|------|---------|-------------|-------------|
| `texture` | `cp.ndarray` | (required) | (H, W, 3) float32, [0, 1] | Input RGB texture |
| `blur_sigma` | `float` | `1.0` | [0.0, 10.0] | Gaussian smoothing sigma. 0 disables blur |
| `contrast` | `float` | `1.2` | [0.5, 3.0] | Contrast multiplier around midpoint |
| `invert` | `bool` | `False` | True/False | Flip height interpretation (white becomes low) |

**Returns:** (H, W) float32 `cupy.ndarray`, values in [0, 1]. White = high, black = low (unless inverted).

### `cupy_ref.ao.generate_ao`

```python
def generate_ao(
    texture: cp.ndarray,
    height_map: cp.ndarray | None = None,
    num_directions: int = 16,
    max_steps: int = 20,
    step_scale: float = 1.0,
    height_scale: float = 10.0,
    power: float = 1.5,
) -> cp.ndarray
```

Generate an ambient occlusion map via screen-space horizon mapping.

| Parameter | Type | Default | Valid Range | Description |
|-----------|------|---------|-------------|-------------|
| `texture` | `cp.ndarray` | (required) | (H, W, 3) float32, [0, 1] | Input RGB texture (used to generate height map if none provided) |
| `height_map` | `cp.ndarray \| None` | `None` | (H, W) float32, [0, 1] | Pre-computed height map. Generated from texture if None |
| `num_directions` | `int` | `16` | [4, 64] | Number of ray directions to sample |
| `max_steps` | `int` | `20` | [4, 64] | Steps per ray for horizon detection |
| `step_scale` | `float` | `1.0` | [0.5, 4.0] | Pixel distance per step |
| `height_scale` | `float` | `10.0` | [0.1, 50.0] | Height map influence on elevation angle |
| `power` | `float` | `1.5` | [0.5, 4.0] | Contrast power curve. >1 darkens shadows |

**Returns:** (H, W) float32 `cupy.ndarray`, values in [0, 1]. White = unoccluded, black = fully occluded.

### `cupy_ref.roughness.generate_roughness`

```python
def generate_roughness(
    texture: cp.ndarray,
    radius: int = 4,
    alpha: float = 0.6,
    blur: float = 1.0,
    contrast: float = 1.5,
) -> cp.ndarray
```

Generate a roughness map from an RGB texture via local variance analysis.

| Parameter | Type | Default | Valid Range | Description |
|-----------|------|---------|-------------|-------------|
| `texture` | `cp.ndarray` | (required) | (H, W, 3) float32, [0, 1] | Input RGB texture |
| `radius` | `int` | `4` | [1, 16] | Analysis window half-size. Window = 2*radius+1 |
| `alpha` | `float` | `0.6` | [0.0, 1.0] | Blend weight: 1.0 = all variance, 0.0 = all edge |
| `blur` | `float` | `1.0` | [0.0, 5.0] | Output smoothing sigma |
| `contrast` | `float` | `1.5` | [0.5, 3.0] | Output contrast multiplier |

**Returns:** (H, W) float32 `cupy.ndarray`, values in [0, 1]. White = rough, black = smooth.

### `cupy_ref.metallic.generate_metallic`

```python
def generate_metallic(
    texture: cp.ndarray,
    sat_threshold: float = 0.35,
    val_threshold: float = 0.10,
    val_range: float = 0.3,
    blur: float = 2.0,
    hard_edges: bool = False,
) -> cp.ndarray
```

Generate a metallic map from an RGB texture via HSV saturation and value thresholding.

| Parameter | Type | Default | Valid Range | Description |
|-----------|------|---------|-------------|-------------|
| `texture` | `cp.ndarray` | (required) | (H, W, 3) float32, [0, 1] | Input RGB texture |
| `sat_threshold` | `float` | `0.35` | [0.05, 0.5] | Maximum saturation for metal classification. Lower = stricter |
| `val_threshold` | `float` | `0.10` | [0.01, 0.8] | Minimum brightness for metal classification |
| `val_range` | `float` | `0.3` | [0.1, 1.0] | Soft transition width above val_threshold |
| `blur` | `float` | `2.0` | [0.0, 5.0] | Output smoothing sigma |
| `hard_edges` | `bool` | `False` | True/False | Apply binary threshold at 0.5 for crisp boundaries |

**Returns:** (H, W) float32 `cupy.ndarray`, values in [0, 1]. White = metallic, black = dielectric.

### `cupy_ref.specular.generate_specular`

```python
def generate_specular(
    texture: cp.ndarray,
    sat_weight: float = 0.5,
    contrast: float = 1.3,
    power: float = 1.2,
    blur: float = 0.5,
) -> cp.ndarray
```

Generate a specular map from an RGB texture via luminance-weighted saturation inversion.

| Parameter | Type | Default | Valid Range | Description |
|-----------|------|---------|-------------|-------------|
| `texture` | `cp.ndarray` | (required) | (H, W, 3) float32, [0, 1] | Input RGB texture |
| `sat_weight` | `float` | `0.5` | [0.0, 1.0] | Saturation reduction factor. Higher = saturation suppresses specularity more |
| `contrast` | `float` | `1.3` | [0.5, 3.0] | Output contrast multiplier |
| `power` | `float` | `1.2` | [0.5, 3.0] | Specular falloff exponent. Higher = darker non-specular areas |
| `blur` | `float` | `0.5` | [0.0, 5.0] | Output smoothing sigma |

**Returns:** (H, W) float32 `cupy.ndarray`, values in [0, 1]. White = high specularity, black = low specularity.

---

## textureworks.ptx

PTX (GPU assembly) implementations loaded via `cupy.cuda.function.Module`. Signatures and parameters mirror the CuPy reference implementations exactly.

### `ptx.normal.generate_normal`

```python
def generate_normal(texture: cp.ndarray, strength: float = 2.0) -> cp.ndarray
```

Generate a normal map using the hand-written PTX kernel `sobel_normal_kernel`.

Parameters, return type, and behavior are identical to [`cupy_ref.normal.generate_normal`](#cupy_refnormalgenerate_normal).

### `ptx.height.generate_height`

```python
def generate_height(
    texture: cp.ndarray,
    blur_sigma: float = 1.0,
    contrast: float = 1.2,
    invert: bool = False,
) -> cp.ndarray
```

Generate a height map using hand-written PTX kernels: `height_normalize_kernel`, `height_blur_h_kernel`, `height_blur_v_kernel`, and `height_contrast_kernel`.

Parameters, return type, and behavior are identical to [`cupy_ref.height.generate_height`](#cupy_refheightgenerate_height).

### `ptx.ao.generate_ao`

```python
def generate_ao(
    texture: cp.ndarray,
    height_map: cp.ndarray | None = None,
    num_directions: int = 16,
    max_steps: int = 20,
    step_scale: float = 1.0,
    height_scale: float = 10.0,
    power: float = 1.5,
) -> cp.ndarray
```

Generate an ambient occlusion map using the hand-written PTX kernel `ao_kernel`.

Parameters, return type, and behavior are identical to [`cupy_ref.ao.generate_ao`](#cupy_refaogenerate_ao). When `height_map` is None, the PTX height implementation (not CuPy) generates the height map.

### `ptx.roughness.generate_roughness`

```python
def generate_roughness(
    texture: cp.ndarray,
    radius: int = 4,
    alpha: float = 0.6,
    blur: float = 1.0,
    contrast: float = 1.5,
) -> cp.ndarray
```

Generate a roughness map using hand-written PTX kernels: `roughness_variance_kernel`, `roughness_sobel_kernel`, and `roughness_blend_kernel`. Gaussian blur uses the CuPy `gaussian_blur` utility.

Parameters, return type, and behavior are identical to [`cupy_ref.roughness.generate_roughness`](#cupy_refroughnessgenerate_roughness).

### `ptx.metallic.generate_metallic`

```python
def generate_metallic(
    texture: cp.ndarray,
    sat_threshold: float = 0.35,
    val_threshold: float = 0.10,
    val_range: float = 0.3,
    blur: float = 2.0,
    hard_edges: bool = False,
) -> cp.ndarray
```

Generate a metallic map using the hand-written PTX kernel `metallic_classify_kernel`. Gaussian blur uses the CuPy `gaussian_blur` utility.

Parameters, return type, and behavior are identical to [`cupy_ref.metallic.generate_metallic`](#cupy_refmetallicgenerate_metallic).

### `ptx.specular.generate_specular`

```python
def generate_specular(
    texture: cp.ndarray,
    sat_weight: float = 0.5,
    contrast: float = 1.3,
    power: float = 1.2,
    blur: float = 0.5,
) -> cp.ndarray
```

Generate a specular map using the hand-written PTX kernel `specular_kernel`. Gaussian blur uses the CuPy `gaussian_blur` utility.

Parameters, return type, and behavior are identical to [`cupy_ref.specular.generate_specular`](#cupy_refspeculargenerate_specular).

---

## textureworks.pipeline

Orchestrates full map generation from a single input image.

### `generate_maps`

```python
def generate_maps(
    texture: cp.ndarray,
    map_types: tuple[str, ...] = ("normal", "height", "ao", "roughness", "metallic", "specular"),
    backend: str = "ptx",
) -> dict[str, cp.ndarray]
```

Generate PBR maps from a loaded texture.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `texture` | `cp.ndarray` | (required) | (H, W, 3) float32 GPU array |
| `map_types` | `tuple[str, ...]` | All six types | Subset of map types to generate |
| `backend` | `str` | `"ptx"` | `"cupy"` or `"ptx"` |

**Returns:** Dict mapping map type name (str) to output array (`cp.ndarray`).

When both `"height"` and `"ao"` appear in `map_types`, the height map is automatically passed to the AO generator to avoid redundant computation.

**Example:**

```python
from textureworks.core.io import load_texture, save_map
from textureworks.pipeline import generate_maps

texture = load_texture("textures/test_texture3.png")
results = generate_maps(texture, backend="ptx")

for name, data in results.items():
    save_map(data, f"output/test_texture3_{name}.png")
```

### `main` (CLI entry point)

```bash
python -m textureworks.pipeline INPUT_PATH [OPTIONS]
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `INPUT_PATH` | path (required) | | Input image file (must exist) |
| `--output`, `-o` | string | `"output"` | Output directory |
| `--map`, `-m` | string | `"all"` | Map type: normal, height, ao, roughness, metallic, specular, or all |
| `--backend`, `-b` | choice | `"ptx"` | Backend: `cupy` or `ptx` |

See [CLI Quick Reference](../how-to/cli-reference.md) for detailed usage examples.
