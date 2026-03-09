# Contributing: Adding a New Map Type

Step-by-step checklist for adding a new PBR map type to TextureWorks.

## Checklist

1. [ ] Algorithm specification in `docs/algorithms.md`
2. [ ] CuPy reference implementation in `cupy_ref/<map_type>.py`
3. [ ] PTX kernel in `ptx/kernels/<map_type>.ptx`
4. [ ] Python wrapper in `ptx/<map_type>.py`
5. [ ] Tests in `tests/test_<map_type>.py`
6. [ ] Register in `pipeline.py`
7. [ ] Update documentation

## Step 1: Algorithm Specification

Add a new section to `docs/algorithms.md` following the existing format:

- Purpose statement explaining the map's role in PBR rendering
- Step-by-step algorithm with mathematical notation
- Parameter table with name, type, default, valid range, and effect
- Tolerance value for CuPy vs PTX comparison
- Boundary handling notes

The algorithm spec is the contract both implementations must follow.

## Step 2: CuPy Reference Implementation

Create `textureworks/cupy_ref/<map_type>.py` with a single public function:

```python
def generate_<map_type>(texture: cp.ndarray, ...) -> cp.ndarray:
```

Requirements:
- Accept `(H, W, 3)` float32 CuPy array as the first argument
- Return `(H, W)` float32 CuPy array with values in [0.0, 1.0] (or `(H, W, 3)` for multi-channel maps)
- Use CuPy array operations exclusively (no Python loops over pixels)
- Include type hints and a docstring with Args/Returns

The CuPy version is the correctness oracle. Prioritize clarity over performance.

## Step 3: PTX Kernel

Create `textureworks/ptx/kernels/<map_type>.ptx`.

Required elements:
- Header comment with purpose, grid/block configuration, parameter layout
- `.version 7.0` and `.target sm_75` declarations
- `.address_size 64`
- Boundary check before any memory access
- Clear register naming (`px_`, `grad_`, `norm_`, `enc_` prefixes)
- Comments on non-obvious instructions

See [Writing a Custom PTX Kernel](../how-to/write-custom-kernel.md) for a detailed guide with the full kernel anatomy.

## Step 4: Python Wrapper

Create `textureworks/ptx/<map_type>.py`.

Follow the caching pattern used by existing wrappers:

```python
_PTX_DIR = Path(__file__).parent / "kernels"
_kernel_cache = {}

def _get_kernel(name: str, entry: str):
    if name not in _kernel_cache:
        ptx_source = (_PTX_DIR / f"{name}.ptx").read_text()
        mod = cp.cuda.function.Module()
        mod.load(ptx_source.encode("utf-8"))
        _kernel_cache[name] = mod
    return _kernel_cache[name].get_function(entry)
```

For multi-kernel PTX files, use `_get_module` instead (returns the module, call `.get_function()` for each kernel entry point).

The wrapper function signature must match the CuPy reference: same function name, same parameters, same return type.

## Step 5: Tests

Create `tests/test_<map_type>.py` with the following test cases:

### Required Tests

**CuPy vs PTX comparison** (both test_texture and small_texture fixtures):

```python
TOLERANCE = N  # from algorithm spec

class TestNewMap:
    def test_cupy_vs_ptx_match(self, test_texture):
        cupy_out = cupy_generate(test_texture)
        ptx_out = ptx_generate(test_texture)
        result = compare_outputs(cupy_out, ptx_out, tolerance=TOLERANCE)
        assert result["matches"], (
            f"Max diff {result['max_diff']} exceeds tolerance {TOLERANCE}"
        )

    def test_cupy_vs_ptx_small(self, small_texture):
        cupy_out = cupy_generate(small_texture)
        ptx_out = ptx_generate(small_texture)
        result = compare_outputs(cupy_out, ptx_out, tolerance=TOLERANCE)
        assert result["matches"]
```

**Shape check:**

```python
    def test_output_shape(self, test_texture):
        out = cupy_generate(test_texture)
        h, w = test_texture.shape[:2]
        assert out.shape == (h, w)  # or (h, w, 3) for RGB maps
```

**Range check:**

```python
    def test_output_range(self, test_texture):
        out = cupy_generate(test_texture)
        assert float(cp.min(out)) >= 0.0
        assert float(cp.max(out)) <= 1.0
```

### Recommended Tests

- Verify parameter effects (e.g., higher strength produces more deviation)
- Test edge cases (flat input, uniform color)
- Verify behavior with the small_texture fixture for fast iteration

## Step 6: Pipeline Registration

In `textureworks/pipeline.py`, add the new map type to the `MAP_TYPES` tuple:

```python
MAP_TYPES = ("normal", "height", "ao", "roughness", "metallic", "specular", "<new_type>")
```

The lazy import in `_get_generator` handles module resolution automatically. The function looks for `textureworks.cupy_ref.<map_type>.generate_<map_type>` and `textureworks.ptx.<map_type>.generate_<map_type>`.

## Step 7: Documentation

Update the following files:
- `docs/reference/map-types.md`: add parameter table and output encoding
- `docs/reference/api.md`: add function signatures for both CuPy and PTX
- `docs/reference/ptx-kernels.md`: add kernel documentation if PTX was created
- `docs/reference/output-conventions.md`: add encoding details
- `docs/index.md`: verify links still work

## Naming Conventions

| Item | Pattern | Example |
|------|---------|---------|
| CuPy module | `cupy_ref/<map_type>.py` | `cupy_ref/metallic.py` |
| PTX kernel | `ptx/kernels/<map_type>.ptx` | `ptx/kernels/metallic.ptx` |
| PTX wrapper | `ptx/<map_type>.py` | `ptx/metallic.py` |
| Public function | `generate_<map_type>` | `generate_metallic` |
| Test file | `tests/test_<map_type>.py` | `tests/test_metallic.py` |
| Output file | `<stem>_<map_type>.png` | `test_texture3_metallic.png` |

## Tolerance Selection Guide

Choose the tolerance based on the algorithm's numerical characteristics:

| Tolerance | When to Use |
|-----------|-------------|
| 1 | Simple operations: convolution, linear math, rounding only |
| 2 | Operations with division, power functions, or multi-step pipelines |
| 3 | Trigonometric approximations, nested loops, accumulated floating-point error |

Verify the chosen tolerance by running the comparison test on multiple input textures.

## Further Reading

- [Testing Guide](testing.md) for test architecture details
- [Project Structure](project-structure.md) for directory layout
- [Writing a Custom PTX Kernel](../how-to/write-custom-kernel.md) for PTX implementation guide
