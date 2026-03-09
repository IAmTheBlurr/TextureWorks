# Python API Integration

How to use TextureWorks programmatically for asset pipelines, batch processing, and custom parameter tuning.

## Basic Usage: generate_maps()

The simplest way to generate maps from Python code:

```python
from textureworks.core.io import load_texture, save_map
from textureworks.pipeline import generate_maps

texture = load_texture("textures/test_texture3.png")
results = generate_maps(texture)

for name, data in results.items():
    save_map(data, f"output/test_texture3_{name}.png")
```

`generate_maps` returns a dictionary mapping map type names to CuPy arrays. Each array contains float32 values in [0.0, 1.0].

### Selecting Map Types and Backend

```python
# Generate only normal and height maps
results = generate_maps(texture, map_types=("normal", "height"))

# Use the CuPy reference backend
results = generate_maps(texture, map_types=("normal",), backend="cupy")
```

Available map types: `"normal"`, `"height"`, `"ao"`, `"roughness"`, `"metallic"`, `"specular"`.

Available backends: `"cupy"`, `"ptx"`.

## Direct Generator Access

For custom parameters, import generators directly. The CLI does not expose per-map parameters, so direct imports are required for parameter tuning.

### Normal Map with Custom Strength

```python
from textureworks.core.io import load_texture, save_map
from textureworks.ptx.normal import generate_normal

texture = load_texture("textures/test_texture3.png")
result = generate_normal(texture, strength=10.0)
save_map(result, "output/test_texture3_normal_strong.png")
```

### Height Map with Custom Blur and Contrast

```python
from textureworks.ptx.height import generate_height

height = generate_height(texture, blur_sigma=3.0, contrast=2.0, invert=False)
save_map(height, "output/test_texture3_height_smooth.png")
```

### AO with Pre-computed Height Map

The AO generator accepts an optional `height_map` parameter. Passing a pre-computed height map avoids regenerating it internally:

```python
from textureworks.ptx.height import generate_height
from textureworks.ptx.ao import generate_ao

height = generate_height(texture, blur_sigma=2.0)
ao = generate_ao(texture, height_map=height, height_scale=20.0, power=2.0)
save_map(ao, "output/test_texture3_ao_deep.png")
```

### Roughness with Custom Analysis Window

```python
from textureworks.ptx.roughness import generate_roughness

roughness = generate_roughness(texture, radius=8, alpha=0.8, blur=2.0, contrast=2.0)
save_map(roughness, "output/test_texture3_roughness_detailed.png")
```

### Metallic with Hard Edges

```python
from textureworks.ptx.metallic import generate_metallic

metallic = generate_metallic(texture, sat_threshold=0.3, hard_edges=True)
save_map(metallic, "output/test_texture3_metallic_binary.png")
```

### Specular with Adjusted Saturation Weight

```python
from textureworks.ptx.specular import generate_specular

specular = generate_specular(texture, sat_weight=0.8, contrast=1.5, power=1.5)
save_map(specular, "output/test_texture3_specular_bright.png")
```

## Batch Processing

Process all textures in a directory:

```python
from pathlib import Path
from textureworks.core.io import load_texture, save_map
from textureworks.pipeline import generate_maps

input_dir = Path("textures/")
output_dir = Path("output/")

for img_path in input_dir.glob("*.png"):
    texture = load_texture(str(img_path))
    results = generate_maps(texture)
    for name, data in results.items():
        save_map(data, output_dir / f"{img_path.stem}_{name}.png")
```

### Batch with Custom Parameters

When default parameters do not produce good results for a specific texture set, combine `generate_maps` for most maps with direct generators for the ones needing adjustment:

```python
from textureworks.core.io import load_texture, save_map
from textureworks.pipeline import generate_maps
from textureworks.ptx.normal import generate_normal

texture = load_texture("textures/stylized_wall.png")

# Use defaults for most maps
results = generate_maps(texture, map_types=("height", "ao", "roughness", "metallic", "specular"))

# Override normal with higher strength for stylized textures
results["normal"] = generate_normal(texture, strength=8.0)

for name, data in results.items():
    save_map(data, f"output/stylized_wall_{name}.png")
```

## Working with CuPy Arrays

All generators accept and return CuPy arrays on the GPU. Keep data on the GPU when chaining operations:

```python
import cupy as cp

texture = load_texture("textures/test_texture3.png")  # Returns CuPy array on GPU
height = generate_height(texture)                       # Still on GPU
ao = generate_ao(texture, height_map=height)            # Still on GPU

# Move to CPU only when saving
save_map(ao, "output/ao.png")  # save_map handles GPU->CPU transfer internally
```

To access raw pixel values on the CPU:

```python
ao_cpu = ao.get()    # CuPy array -> NumPy array
print(ao_cpu.shape)  # (H, W)
print(ao_cpu.dtype)  # float32
print(ao_cpu.min(), ao_cpu.max())  # Values in [0.0, 1.0]
```

To create a CuPy array from a NumPy array:

```python
import numpy as np

cpu_data = np.random.rand(512, 512, 3).astype(np.float32)
gpu_data = cp.asarray(cpu_data)
result = generate_normal(gpu_data, strength=2.0)
```

## Checking GPU Resources

Before processing large textures, verify available VRAM:

```python
from textureworks.core.gpu import get_device_info

info = get_device_info()
print(f"Free VRAM: {info['free_memory_mb']:.0f} MB")
```

A 4096x4096 RGB float32 texture requires approximately 192 MB of VRAM. Map generation creates temporary buffers, so plan for 2-3x the input size in total GPU memory usage.

## Further Reading

- [Map Type Reference](../reference/map-types.md) for all parameter defaults and valid ranges
- [API Reference](../reference/api.md) for complete function signatures
- [CLI Reference](cli-reference.md) for command-line usage
- [Custom Parameters Tutorial](../tutorials/tutorial-custom-params.md) for parameter tuning guidance
