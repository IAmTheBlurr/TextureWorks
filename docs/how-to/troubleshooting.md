# Troubleshooting

Common issues and solutions when using TextureWorks.

## Installation and Environment

### CUDA Not Detected

**Symptom:** `ImportError` or `ModuleNotFoundError` when importing CuPy.

**Cause:** CuPy must be installed for the specific CUDA version on your system.

**Fix:** Install the CuPy package matching your CUDA toolkit version:

```bash
# For CUDA 11.x
pip install cupy-cuda11x

# For CUDA 12.x
pip install cupy-cuda12x
```

Check your CUDA version with:

```bash
nvcc --version
```

### Wrong CuPy Version

**Symptom:** `cupy.cuda.driver.CUDADriverError` at runtime.

**Cause:** The installed CuPy binary does not match the system CUDA driver.

**Fix:** Uninstall CuPy and reinstall the correct variant:

```bash
pip uninstall cupy cupy-cuda11x cupy-cuda12x
pip install cupy-cuda12x  # match your CUDA version
```

## GPU Memory

### Out of Memory

**Symptom:** `cupy.cuda.memory.OutOfMemoryError` during map generation.

**Cause:** The texture is too large for available GPU VRAM. A 4096x4096 RGB float32 texture uses approximately 192 MB. Map generation creates temporary buffers, so total usage is 2-3x the input size.

**Fix:** Check available memory first:

```python
from textureworks.core.gpu import get_device_info
info = get_device_info()
print(f"Free VRAM: {info['free_memory_mb']:.0f} MB")
```

Options:
- Close other GPU-consuming applications
- Reduce input texture resolution
- Process one map type at a time instead of all at once

### Memory Not Freed After Processing

**Symptom:** VRAM usage stays high after map generation completes.

**Cause:** CuPy maintains a memory pool for performance. Allocated blocks are cached, not immediately returned to the driver.

**Fix:** Explicitly free the memory pool:

```python
import cupy as cp
cp._default_memory_pool.free_all_blocks()
```

## PTX Kernel Issues

### Kernel Launch Failure

**Symptom:** `cupy.cuda.driver.CUDADriverError` when launching a PTX kernel.

**Common causes:**
- PTX file not found (check the path in `ptx/kernels/`)
- Kernel entry point name mismatch between the `.ptx` file and the Python wrapper
- Parameter type mismatch (e.g., passing `int` where `float32` is expected)

**Fix:** Verify the PTX file exists and the entry point matches:

```python
from pathlib import Path
ptx_dir = Path("textureworks/ptx/kernels")
print(list(ptx_dir.glob("*.ptx")))
```

Ensure kernel arguments use explicit NumPy types:

```python
import numpy as np
# Correct
args=(array.data.ptr, np.int32(width), np.float32(strength))
# Wrong - Python int/float will cause issues
args=(array.data.ptr, width, strength)
```

### Incorrect Output (Garbage Pixels)

**Symptom:** Output image contains random noise or solid colors.

**Common causes:**
- Missing boundary check in the kernel (threads beyond image dimensions wrote to invalid memory)
- Wrong byte offset calculation (forgot to multiply by 4 for float32)
- Grid/block dimensions swapped (width/height mismatch)

**Fix:** Verify the grid configuration covers the image correctly:

```python
from textureworks.core.gpu import grid_size, recommended_block_size
block = recommended_block_size()  # (16, 16)
grid = grid_size(width, height, block)
print(f"Grid: {grid}, Block: {block}, Coverage: {grid[0]*16}x{grid[1]*16}")
```

The grid coverage should be >= the image dimensions.

## Output Quality

### Normal Map Looks Flat

**Cause:** The `strength` parameter is too low for the input texture.

**Fix:** Increase `strength` from the default 2.0:

```python
from textureworks.ptx.normal import generate_normal
result = generate_normal(texture, strength=8.0)  # Range: [0.1, 20.0]
```

Stylized or hand-painted textures often benefit from strength values of 5.0-15.0.

### Normal Map Looks Too Extreme

**Cause:** The `strength` parameter is too high, or the input has sharp high-contrast edges.

**Fix:** Reduce `strength`:

```python
result = generate_normal(texture, strength=0.5)
```

### Height Map Has No Contrast

**Cause:** The input texture has low dynamic range or the `contrast` parameter needs adjustment.

**Fix:** Increase the contrast multiplier:

```python
from textureworks.ptx.height import generate_height
result = generate_height(texture, contrast=2.5)  # Range: [0.5, 3.0]
```

### AO Map Is Too Bright (No Visible Occlusion)

**Cause:** The `height_scale` parameter is too low for the input texture. The algorithm uses height differences to compute occlusion, and low height scale means small elevation angles.

**Fix:** Increase `height_scale`:

```python
from textureworks.ptx.ao import generate_ao
result = generate_ao(texture, height_scale=25.0)  # Range: [0.1, 50.0]
```

For stylized textures with subtle height variation, try values of 20.0-40.0.

### AO Map Is Too Dark

**Cause:** The `power` parameter amplifies occlusion contrast.

**Fix:** Reduce `power` toward 1.0:

```python
result = generate_ao(texture, power=1.0)  # Range: [0.5, 4.0]
```

### Metallic Map Seems Inverted

**Cause:** The saturation/value thresholds do not match the input texture's color profile. Textured metals with high saturation will be classified as dielectric.

**Fix:** Adjust thresholds based on the input:

```python
from textureworks.ptx.metallic import generate_metallic
# For textures where metals have higher saturation
result = generate_metallic(texture, sat_threshold=0.5)  # Range: [0.05, 0.5]
# For textures where metals are darker
result = generate_metallic(texture, val_threshold=0.05)  # Range: [0.01, 0.8]
```

### Roughness Map Looks Uniform

**Cause:** The analysis window is too small to capture meaningful variation, or the blend parameter over-weights one signal.

**Fix:** Increase the radius and adjust alpha:

```python
from textureworks.ptx.roughness import generate_roughness
result = generate_roughness(texture, radius=8, alpha=0.5, contrast=2.0)
```

`radius` (range [1, 16]) controls the neighborhood size. `alpha` (range [0.0, 1.0]) blends variance (high alpha) vs edge signals (low alpha).

## CuPy vs PTX Comparison Failures

### Max Difference Exceeds Tolerance

**Symptom:** Test reports `max_diff > tolerance` for a map type.

**Common causes:**
- Floating-point ordering differences between CuPy's vectorized operations and PTX's per-thread computation
- Approximate math functions in PTX (e.g., `rsqrt.approx.f32`, `cos.approx.f32`) differ slightly from CuPy's full-precision versions
- Post-processing step ordering (blur before contrast vs contrast before blur)

**Expected tolerances:** Normal=1, Height=2, AO=3, Roughness=3, Metallic=2, Specular=2.

If the max difference is only slightly above the tolerance, it likely indicates an edge case in the approximation. If the difference is large (>10), it suggests a logic error in the kernel.

## Further Reading

- [Map Type Reference](../reference/map-types.md) for all parameter defaults and valid ranges
- [CLI Reference](cli-reference.md) for command syntax
- [Architecture](../explanation/architecture.md) for the dual-implementation and tolerance design
