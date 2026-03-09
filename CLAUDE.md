# CLAUDE.md — TextureWorks Project

## Project Overview

TextureWorks is a GPU-accelerated texture map generation library. It produces
PBR (Physically Based Rendering) texture maps from diffuse/albedo input images.
Every algorithm has two implementations: a CuPy reference implementation and a
hand-written PTX (NVIDIA GPU assembly) implementation. The CuPy version serves
as the correctness oracle. The PTX version serves as the learning artifact and
performance target.

## Architecture

```
textureworks/
├── core/          # I/O, comparison utilities, GPU device management
├── cupy_ref/      # CuPy reference implementations (one module per map type)
├── ptx/
│   ├── kernels/   # Raw .ptx files (GPU assembly source)
│   └── *.py       # Python wrappers loading PTX via cupy.RawKernel
├── pipeline.py    # Orchestrates full map generation from a single input
```

Each map type follows the same pattern:
1. Mathematical specification lives in `docs/algorithms.md`
2. CuPy implementation in `cupy_ref/<map_type>.py`
3. PTX kernel in `ptx/kernels/<map_type>.ptx`
4. Python wrapper in `ptx/<map_type>.py`
5. Test in `tests/test_<map_type>.py`
6. Benchmark in `benchmarks/bench.py`

## Map Types (Implementation Order)

1. **Normal map** — Sobel convolution, gradient-to-normal encoding
2. **Height map** — Weighted luminance extraction, contrast normalization
3. **Ambient Occlusion** — Height-field ray marching / horizon mapping
4. **Roughness map** — Local variance and frequency analysis
5. **Metallic map** — Saturation/value classification with thresholds
6. **Specular map** — Luminance and saturation-derived reflectance

## Development Environment

- Python virtual environment is active. Use `pip install` directly (no
  `--break-system-packages` needed).
- CUDA toolkit is available on the host system.
- CuPy is installed and configured for the host's CUDA version.
- Test textures live in `textures/`. The primary test asset is a sci-fi
  metallic panel texture.

## Coding Standards

### Python
- Python 3.10+ features are acceptable.
- Type hints on all public function signatures.
- Docstrings on all public functions. Keep them brief: one line purpose,
  then Args/Returns if non-obvious.
- No classes unless state management genuinely requires them. Prefer
  module-level functions.
- Use `cupy.ndarray` for GPU data, `numpy.ndarray` for CPU data. Never
  mix them silently. Explicit `.get()` to move GPU→CPU, `cupy.asarray()`
  for CPU→GPU.

### PTX
- Target `sm_75` or higher (Turing+). The host machines have RTX cards.
- Use `.version 7.0` or higher PTX ISA.
- Comment every non-obvious instruction. PTX is the learning artifact;
  readability matters more than density.
- Register naming convention: prefix with purpose (`px_` for pixel coords,
  `grad_` for gradient values, `norm_` for normalized results).
- Each kernel file begins with a block comment specifying: purpose,
  expected grid/block dimensions, parameter layout, memory access pattern.

### Tests
- pytest is the test framework.
- Every map type test loads the reference texture, generates output via
  both CuPy and PTX paths, and asserts pixel-wise similarity within a
  configurable tolerance (default: max absolute difference ≤ 2 per channel
  on 8-bit output).
- Tests also verify output dimensions match input dimensions and output
  value ranges are valid (0-255 for 8-bit, 0.0-1.0 for float).

### Benchmarks
- Use `cupyx.time.repeat` for GPU timing (handles synchronization).
- Report median and p95 over 100 iterations.
- Test at 1024x1024, 2048x2048, and 4096x4096 resolutions.

## Key Dependencies

| Package   | Purpose                                    |
|-----------|--------------------------------------------|
| cupy      | GPU array operations, PTX kernel loading   |
| numpy     | CPU array operations, test comparisons     |
| Pillow    | Image I/O (load PNG/JPG, save output maps) |
| click     | CLI interface                              |
| pytest    | Testing                                    |

## Common Commands

```bash
# Run all tests
pytest tests/ -v

# Run tests for a specific map type
pytest tests/test_normal.py -v

# Generate all maps for a texture
python -m textureworks.pipeline textures/test_texture3.png --output output/

# Generate a specific map type
python -m textureworks.pipeline textures/test_texture3.png --map normal --output output/

# Run benchmarks
python benchmarks/bench.py

# Compare CuPy vs PTX output for a specific algorithm
python -m textureworks.core.compare cupy_ref.normal ptx.normal textures/test_texture3.png
```

## PTX Development Notes

CuPy's `RawKernel` loads PTX source strings or compiled .ptx files. The
pattern used in this project:

```python
import cupy

ptx_source = open("ptx/kernels/normal.ptx").read()
kernel = cupy.RawKernel(ptx_source, "sobel_normal_kernel", backend="nvptx")
kernel((grid_x, grid_y), (block_x, block_y), (input_gpu, output_gpu, width, height))
```

When writing PTX kernels:
- `%tid.x`, `%tid.y` give thread index within the block.
- `%ctaid.x`, `%ctaid.y` give block index within the grid.
- `%ntid.x`, `%ntid.y` give block dimensions.
- Global pixel coordinates: `px = ctaid.x * ntid.x + tid.x`
- Boundary checks are mandatory. Threads beyond image dimensions must exit early.
- Use `.global` memory space for input/output arrays.
- Use `.shared` memory for tile-based convolutions (load a tile, sync, compute).

## Error Handling

- GPU out-of-memory: catch `cupy.cuda.memory.OutOfMemoryError`, report
  texture size and available VRAM, suggest reducing resolution.
- Missing CUDA: detect at import time, raise a clear error pointing to
  CuPy installation docs.
- Invalid input: validate image is 2D grayscale or 3D RGB/RGBA before
  processing. Convert RGBA→RGB by dropping alpha unless the algorithm
  specifically uses alpha.

## Output Conventions

- All output maps are 8-bit single-channel or 3-channel PNG files.
- Normal maps: RGB, where R=X, G=Y, B=Z. Neutral normal (flat surface)
  encodes as (128, 128, 255).
- Height maps: single-channel grayscale. White=high, black=low.
- AO maps: single-channel grayscale. White=unoccluded, black=fully occluded.
- Roughness maps: single-channel grayscale. White=rough, black=smooth.
- Metallic maps: single-channel grayscale. White=metal, black=dielectric.
- Specular maps: single-channel grayscale. White=high specularity.
- File naming: `<input_name>_<map_type>.png`
  (e.g., `test_texture3_normal.png`)
