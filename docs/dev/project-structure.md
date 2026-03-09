# Project Structure

Directory layout, file naming conventions, and module dependency graph for TextureWorks.

## Directory Layout

```
TextureWorks/
  textureworks/               # Main package
    __init__.py               # Version (0.1.0)
    pipeline.py               # CLI entry point and generate_maps orchestrator
    core/                     # Shared utilities
      __init__.py
      io.py                   # load_texture, save_map, to_grayscale, rgb_to_hsv
      gpu.py                  # get_device_info, recommended_block_size, grid_size
      blur.py                 # gaussian_kernel_1d, gaussian_blur
      compare.py              # compare_outputs, compare_and_report, comparison CLI
    cupy_ref/                 # CuPy reference implementations (correctness oracles)
      __init__.py
      normal.py               # generate_normal
      height.py               # generate_height
      ao.py                   # generate_ao
      roughness.py            # generate_roughness
      metallic.py             # generate_metallic
      specular.py             # generate_specular
    ptx/                      # PTX implementations (performance targets)
      __init__.py
      normal.py               # Python wrapper for normal.ptx
      height.py               # Python wrapper for height.ptx
      ao.py                   # Python wrapper for ao.ptx
      roughness.py            # Python wrapper for roughness.ptx
      metallic.py             # Python wrapper for metallic.ptx
      specular.py             # Python wrapper for specular.ptx
      kernels/                # Raw PTX assembly source files
        normal.ptx            # 1 kernel: sobel_normal_kernel
        height.ptx            # 4 kernels: normalize, blur_h, blur_v, contrast
        ao.ptx                # 1 kernel: ao_kernel
        roughness.ptx         # 3 kernels: variance, sobel, blend
        metallic.ptx          # 1 kernel: metallic_classify_kernel
        specular.ptx          # 1 kernel: specular_kernel
  tests/                      # pytest test suite
    __init__.py
    conftest.py               # Shared fixtures (test_texture, small_texture)
    test_normal.py
    test_height.py
    test_ao.py
    test_roughness.py
    test_metallic.py
    test_specular.py
  benchmarks/
    bench.py                  # CuPy vs PTX performance benchmarks
  textures/
    test_texture3.png         # Primary test asset (sci-fi metallic panel)
  docs/
    algorithms.md             # Mathematical specifications for all map types
    index.md                  # Documentation landing page
    tutorials/                # Learning-oriented guides
    how-to/                   # Task-oriented guides
    reference/                # Lookup documentation
    explanation/              # Understanding-oriented articles
    dev/                      # Developer and contributor guides
  pyproject.toml              # Package metadata, Python >=3.10
  requirements.txt            # Dependencies with CuPy install notes
  CLAUDE.md                   # Project conventions and AI context
  README.md
```

## File Naming Conventions

| Directory | Pattern | Example |
|-----------|---------|---------|
| `cupy_ref/` | `<map_type>.py` | `cupy_ref/metallic.py` |
| `ptx/` | `<map_type>.py` | `ptx/metallic.py` |
| `ptx/kernels/` | `<map_type>.ptx` | `ptx/kernels/metallic.ptx` |
| `tests/` | `test_<map_type>.py` | `tests/test_metallic.py` |
| Output files | `<stem>_<map_type>.png` | `test_texture3_metallic.png` |

Every map type uses the same name across all directories. The function name is always `generate_<map_type>`.

## Module Dependency Graph

```
pipeline.py
  <- core.io (load_texture, save_map)
  <- cupy_ref.* or ptx.* (generate_<map_type>, via lazy import)

core.io
  <- cupy, numpy, Pillow

core.gpu
  <- cupy

core.blur
  <- cupy, cupyx.scipy.ndimage

core.compare
  <- cupy, numpy

cupy_ref.normal
  <- core.io (to_grayscale)
  <- cupyx.scipy.ndimage (convolve)

cupy_ref.height
  <- core.io (to_grayscale)
  <- core.blur (gaussian_blur)

cupy_ref.ao
  <- cupy_ref.height (generate_height, for auto height map)

cupy_ref.roughness
  <- core.io (to_grayscale)
  <- core.blur (gaussian_blur)
  <- cupyx.scipy.ndimage (convolve)

cupy_ref.metallic
  <- core.io (rgb_to_hsv)
  <- core.blur (gaussian_blur)

cupy_ref.specular
  <- core.io (to_grayscale, rgb_to_hsv)
  <- core.blur (gaussian_blur)

ptx.normal
  <- core.io (to_grayscale)
  <- core.gpu (grid_size, recommended_block_size)

ptx.height
  <- core.io (to_grayscale)
  <- core.gpu (grid_size, recommended_block_size)
  <- core.blur (gaussian_kernel_1d)

ptx.ao
  <- core.io (to_grayscale)
  <- core.gpu (grid_size, recommended_block_size)
  <- cupy_ref.height (generate_height, for auto height map)

ptx.roughness
  <- core.io (to_grayscale)
  <- core.gpu (grid_size, recommended_block_size)
  <- core.blur (gaussian_blur)

ptx.metallic
  <- core.io (rgb_to_hsv)
  <- core.gpu (grid_size, recommended_block_size)
  <- core.blur (gaussian_blur)

ptx.specular
  <- core.io (to_grayscale, rgb_to_hsv)
  <- core.gpu (grid_size, recommended_block_size)
  <- core.blur (gaussian_blur)

tests/test_*.py
  <- core.compare (compare_outputs)
  <- cupy_ref.* (CuPy generators)
  <- ptx.* (PTX generators)
  <- tests/conftest.py (fixtures)

benchmarks/bench.py
  <- cupy_ref.* (CuPy generators)
  <- ptx.* (PTX generators)
```

## Key Patterns

### Dual Implementation

Every map type exists in two places:
- `cupy_ref/<map_type>.py` -- CuPy reference (correctness oracle)
- `ptx/<map_type>.py` -- PTX wrapper (performance target)

Both expose `generate_<map_type>` with identical signatures. The pipeline selects between them via the `backend` parameter.

### PTX Module Caching

All PTX wrappers cache loaded modules to avoid repeated file I/O:

```python
_kernel_cache = {}

def _get_kernel(name, entry):
    if name not in _kernel_cache:
        # Load and cache
    return _kernel_cache[name].get_function(entry)
```

Single-kernel files (normal, ao, metallic, specular) use `_get_kernel`. Multi-kernel files (height, roughness) use `_get_module` and call `.get_function()` per entry point.

### Lazy Import in Pipeline

`pipeline.py` uses `__import__` for lazy loading of generator modules. This avoids importing all backends at startup and allows the pipeline to load only the requested backend.

### Shared Gaussian Blur

Several PTX wrappers (`roughness`, `metallic`, `specular`) use CuPy's `gaussian_blur` from `core.blur` for post-processing. The blur step runs on the GPU through CuPy's optimized `convolve1d`, not through a custom PTX kernel.

## External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| cupy | (matches CUDA) | GPU arrays, PTX kernel loading |
| numpy | >=1.24 | CPU arrays, test comparisons |
| Pillow | >=10.0 | Image I/O |
| click | >=8.1 | CLI interface |
| pytest | (dev) | Test framework |

## Further Reading

- [Architecture](../explanation/architecture.md) for design philosophy
- [Contributing](contributing.md) for adding new map types
- [API Reference](../reference/api.md) for function signatures
