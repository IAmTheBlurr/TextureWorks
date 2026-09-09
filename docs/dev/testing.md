# Testing Guide

How the TextureWorks test suite works, how to run it, and how to interpret results.

## Running Tests

Run all tests:

```bash
pytest tests/ -v
```

Run tests for a specific map type:

```bash
pytest tests/test_normal.py -v
```

Run a single test:

```bash
pytest tests/test_normal.py::TestNormalMap::test_cupy_vs_ptx_match -v
```

## Test Structure

Each map type has a dedicated test file:

```
tests/
  conftest.py          # Shared fixtures
  test_normal.py       # Normal map tests
  test_height.py       # Height map tests
  test_ao.py           # Ambient occlusion tests
  test_roughness.py    # Roughness map tests
  test_metallic.py     # Metallic map tests
  test_specular.py     # Specular map tests
```

## Fixtures

Defined in `tests/conftest.py`:

### test_texture

Loads `textures/test_texture3.png` as a float32 CuPy array on the GPU. This is a real-world sci-fi metallic panel texture used for full integration testing. Skips if the file is missing.

```python
@pytest.fixture
def test_texture() -> cp.ndarray:
    path = TEXTURE_DIR / "test_texture3.png"
    if not path.exists():
        pytest.skip(f"Test texture missing: {path}")
    return load_texture(path)
```

### small_texture

Generates a 64x64 synthetic RGB float32 CuPy array. Contains horizontal and vertical gradients with hard edges simulating panel lines. Used for fast unit tests where real texture content is not needed.

```python
@pytest.fixture
def small_texture() -> cp.ndarray:
    # 64x64 with gradient + panel lines
```

The synthetic texture produces predictable outputs: gradients create detectable normals and height variations, and panel lines create edges the roughness and AO algorithms can process.

## The CuPy vs PTX Comparison Pattern

Every test file follows the same core pattern:

```python
TOLERANCE = N  # From algorithm spec

class TestMapType:
    def test_cupy_vs_ptx_match(self, test_texture):
        cupy_out = cupy_generate(test_texture)
        ptx_out = ptx_generate(test_texture)
        result = compare_outputs(cupy_out, ptx_out, tolerance=TOLERANCE)
        assert result["matches"], (
            f"Max diff {result['max_diff']} exceeds tolerance {TOLERANCE}"
        )
```

1. Generate output from both backends using the same input
2. Call `compare_outputs` with the tolerance from the algorithm spec
3. Assert the `matches` key is `True`

The comparison function (`textureworks.core.compare.compare_outputs`) scales float32 arrays to the 0-255 range, computes absolute per-pixel differences, and checks the maximum difference against the tolerance.

### AO Test Isolation

The AO test uses a shared height map for both backends to isolate the AO algorithm comparison:

```python
def test_cupy_vs_ptx_match(self, test_texture):
    hmap = cupy_height(test_texture)
    cupy_out = cupy_ao(test_texture, height_map=hmap)
    ptx_out = ptx_ao(test_texture, height_map=hmap)
    result = compare_outputs(cupy_out, ptx_out, tolerance=TOLERANCE)
    assert result["matches"]
```

Without this, differences in the height map generation would cascade into the AO comparison and inflate the measured difference.

## Tolerance System

Each map type has a specific tolerance based on its numerical characteristics:

| Map Type | Tolerance | Reason |
|----------|-----------|--------|
| Normal | 1 | Rounding at integer boundaries |
| Height | 2 | Gaussian blur floating-point variance |
| AO | 3 | Trigonometric and sampling approximations |
| Roughness | 3 | Windowed variance computation differences |
| Metallic | 2 | Division and clamping rounding |
| Specular | 2 | Power function approximation |

Tolerances are defined on the uint8 (0-255) scale. A tolerance of 3 means the CuPy and PTX outputs may differ by up to 3 out of 255 per pixel per channel.

## Standard Test Cases

Each test file includes these test types:

### CuPy vs PTX Comparison

Two variants: `test_texture` (real-world) and `small_texture` (synthetic). Both must pass at the specified tolerance.

### Shape Check

Verifies the output dimensions match the input:

```python
def test_output_shape(self, test_texture):
    out = cupy_generate(test_texture)
    h, w = test_texture.shape[:2]
    assert out.shape == (h, w)       # Single-channel maps
    # or assert out.shape == (h, w, 3)  # Normal map (RGB)
```

### Range Check

Verifies output values fall within [0.0, 1.0]:

```python
def test_output_range(self, test_texture):
    out = cupy_generate(test_texture)
    assert float(cp.min(out)) >= 0.0
    assert float(cp.max(out)) <= 1.0
```

### Semantic Tests

Map-specific behavior verification:
- **Normal**: flat input produces neutral normal (0.5, 0.5, 1.0)
- **Normal**: higher strength increases deviation from neutral
- **AO**: flat height map produces bright (high) AO values
- **AO**: auto-generates height map when none is provided

## Interpreting Failures

### "Max diff X exceeds tolerance Y"

The CuPy and PTX implementations diverged beyond the acceptable threshold. Possible causes:

- **Small overshoot (e.g., max_diff=4, tolerance=3)**: An edge case in the approximation. Check if a specific pixel coordinate causes the divergence. May indicate a boundary handling difference or a rounding issue near a threshold.

- **Large overshoot (e.g., max_diff=50+)**: A logic error in the PTX kernel. Common causes: wrong register used, incorrect memory offset calculation, missing boundary clamp, swapped width/height.

### "Test texture missing"

The `test_texture` fixture skips if `textures/test_texture3.png` is not present. The `small_texture` tests still run since they use synthetic data.

### GPU errors

`cupy.cuda.driver.CUDADriverError` during tests usually means a PTX kernel has a bug (invalid memory access, parameter mismatch). See [Troubleshooting](../how-to/troubleshooting.md).

## Parallax Occlusion Mapping validation

`tests/test_io.py` verifies 8-bit compatibility, actual PNG bit depth, clipping,
16-bit round trips, and invalid input handling. `tests/test_pipeline.py` exercises
the CLI through both backends and checks that `--height-bits` affects only height.

For shader changes, run the separate GPU harness using an installed Unity 6 editor:

```powershell
.\scripts\test-unity-parallax.ps1 -UnityEditor 'C:\Program Files\Unity\Hub\Editor\6000.3.7f1\Editor\Unity.exe'
```

The harness compiles and renders the shipped HLSL with Unity's actual SRP texture
types. Tests cover constant and ramp intersections, first ledge occlusion, R16
sampling precision, view direction, sampler boundaries, control bounds, and fades.
The script retains its temporary Unity project, results, comparison renders,
and camera sweeps for inspection. It requires graphics access, the project's
Python/CuPy environment, and the generated material inputs. It is not part of pytest.

The suite also tests normals against analytic slopes and fades, and compares
POM with a dense displaced mesh across four generated materials. It measures
40 fixed cases plus 100 camera-sweep frames. See the
[validation method](parallax-validation.md) for sampling controls, error bounds,
and the limitations of inferred height. Acceptance of a complete material in
the consuming project follows the checklist in the
[integration guide](../how-to/parallax-occlusion-mapping.md).

## Material cluster validation

`tests/test_material_fields.py` checks both new backends and independent semantic
references: flat detail, frequency attenuation, signed bumps/depressions, ramps,
physical normal orientation, clamp/wrap, odd dimensions, seed repeatability,
extreme controls and zero-width composition. `tests/test_bundle.py` exercises
lossless authored PNGs, external detail, metadata/hash rejection, shared-height
dependencies, deterministic regeneration, Python APIs and both CLI entry points.

The Unity lab's `cluster_validate` renders the actual reusable HLSL against CPU
analytic composition and independent shortest-arc normal references. It checks
the imported formats and actual Lit shader's normal conventions and channel
blend endpoints, then captures six scene stages, motion, exact zero/fade behavior
and moving illumination. Run `scripts/test-material-lab.ps1 -UseOpenEditor`
against the open lab, or omit that flag with the editor closed. Include the
Windows player smoke run from `scripts/test-material-cluster-player.ps1`.
Reports, visual review and timing conditions are documented in
[material-cluster-validation.md](material-cluster-validation.md).

## Further Reading

- [Contributing](contributing.md) for the full checklist when adding a new map type
- [Architecture](../explanation/architecture.md) for the dual-implementation design
- [API Reference](../reference/api.md) for `compare_outputs` function details
