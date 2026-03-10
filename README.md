# TextureWorks

I got tired of a simple texture map generation tool not existing in a normal way, so here you go...

a GPU-accelerated PBR texture map generation from diffuse/albedo images with both Python and PTX implementations

Your one-stop shop for Normal, Height, Ambient Occlusion, Roughness, Metallic, Specular maps, no fuss, no muss, CLI and CI/CD friendly.

Because this stuff really shouldn't be all that hard, it's not rocket appliance

## Input & Output Example Images

<div align="center">

<div>
<strong>Input Diffuse</strong>
<br/>
<img src="docs/images/sci-fi-hull.png" width="384"/>
</div>

<table cellspacing="0" cellpadding="8" border="0">
<tr>
<td align="center"><sub><strong>Normal</strong></sub><br/><img src="docs/images/output/sci-fi-hull_normal.png" width="192"/></td>
<td align="center"><sub><strong>Roughness</strong></sub><br/><img src="docs/images/output/sci-fi-hull_roughness.png" width="192"/></td>
<td align="center"><sub><strong>Ambient Occlusion</strong></sub><br/><img src="docs/images/output/sci-fi-hull_ao.png" width="192"/></td>
</tr>
<tr>
<td align="center"><sub><strong>Height</strong></sub><br/><img src="docs/images/output/sci-fi-hull_height.png" width="192"/></td>
<td align="center"><sub><strong>Metallic</strong></sub><br/><img src="docs/images/output/sci-fi-hull_metallic.png" width="192"/></td>
<td align="center"><sub><strong>Specular</strong></sub><br/><img src="docs/images/output/sci-fi-hull_specular.png" width="192"/></td>
</tr>
</table>

</div>

## Overview
*One input image. Six PBR maps. Milliseconds on a GPU.*

TextureWorks generates six PBR texture maps (normal, height, ambient occlusion, roughness, metallic, specular) from a single diffuse or albedo image. Every algorithm ships as dual implementations: a CuPy reference (Python-level GPU array operations) and a hand-written PTX version (NVIDIA GPU assembly). CuPy validates correctness. PTX explores the machine. Both backends produce visually identical output, verified by a tolerance-based comparison suite.

The library is headless, library-first, and built for automation. It runs in build scripts, CI pipelines, and batch-processing workflows with no GUI and no display server. Deterministic algorithms with fixed parameters produce reproducible output across machines. The Python API exposes every parameter for programmatic control.

## Supported Map Types

| Map Type           | Input    | Output         | Algorithm                          |
|--------------------|----------|----------------|------------------------------------|
| Normal             | RGB      | RGB (XYZ)      | Sobel gradient, normal encoding    |
| Height/Displacement| RGB      | Grayscale      | Luminance extraction + contrast    |
| Ambient Occlusion  | Height   | Grayscale      | Height-field horizon mapping       |
| Roughness          | RGB      | Grayscale      | Local variance + edge density      |
| Metallic           | RGB      | Grayscale      | HSV saturation/value thresholding  |
| Specular           | RGB      | Grayscale      | Luminance-weighted sat. inversion  |

<table>
<tr>
<td align="center" width="30%"><strong>Input Diffuse</strong></td>
<td align="center" width="23%"><strong>Normal</strong></td>
<td align="center" width="23%"><strong>Height</strong></td>
<td align="center" width="23%"><strong>Ambient Occlusion</strong></td>
</tr>
<tr>
<td><img src="docs/images/stone-brick-wall.png" width="100%"/></td>
<td><img src="docs/images/output/stone-brick-wall_normal.png" width="100%"/></td>
<td><img src="docs/images/output/stone-brick-wall_height.png" width="100%"/></td>
<td><img src="docs/images/output/stone-brick-wall_ao.png" width="100%"/></td>
</tr>
<tr>
<td></td>
<td align="center"><strong>Roughness</strong></td>
<td align="center"><strong>Metallic</strong></td>
<td align="center"><strong>Specular</strong></td>
</tr>
<tr>
<td></td>
<td><img src="docs/images/output/stone-brick-wall_roughness.png" width="100%"/></td>
<td><img src="docs/images/output/stone-brick-wall_metallic.png" width="100%"/></td>
<td><img src="docs/images/output/stone-brick-wall_specular.png" width="100%"/></td>
</tr>
</table>

*The same pipeline handles both hard-surface and organic/natural materials.*

## Features

- Six PBR map types: normal, height, ambient occlusion, roughness, metallic, specular
- Two backends per algorithm: CuPy (reference) and PTX (performance)
- CLI for single-command map generation with backend selection
- Python API with per-map parameter control (strength, blur, contrast, thresholds)
- Automatic height map caching when generating AO alongside other maps
- Tolerance-based CuPy-vs-PTX comparison tool for correctness validation
- Benchmark suite across three resolutions (1024, 2048, 4096) with median and p95 timing
- 8-bit PNG output with standard PBR encoding conventions
- Accepts any image format Pillow supports (PNG, JPG, BMP, TIFF)
- RGBA input auto-converted to RGB

## Requirements

### Hardware

- NVIDIA GPU with compute capability 7.5 or higher (Turing architecture: RTX 20-series and later)
- Minimum ~600 MB free VRAM for 4096x4096 textures (input + intermediate buffers). Smaller textures need proportionally less.

### Software

- Python 3.10+
- CUDA toolkit 11.x, 12.x, or 13.x (the CuPy wheel must match your installed toolkit version)
- Operating system: Windows, Linux, or WSL. The project develops and tests on Windows 11 with CUDA.

## Installation and Setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd TextureWorks
```

### 2. Create a Python virtual environment

```bash
python -m venv .venv

# Activate (Linux/Mac/WSL)
source .venv/bin/activate

# Activate (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Activate (Windows cmd)
.venv\Scripts\activate.bat
```

### 3. Install the CUDA Toolkit (if not already present)

Verify your CUDA installation:

```bash
nvcc --version
```

If the command is not found, you need the NVIDIA CUDA Toolkit. Download the installer for your platform from:

[https://developer.nvidia.com/cuda-downloads](https://developer.nvidia.com/cuda-downloads)

Select your operating system, architecture, and preferred installer format. After installation, confirm `nvcc` is available by running the version check above. On Linux, you may need to add the toolkit to your PATH:

```bash
export PATH=/usr/local/cuda/bin:$PATH
```

On Windows, the installer typically configures PATH automatically. If `nvcc` still isn't found after installation, restart your terminal session.

CUDA 13.x is the newest at time of writing. CUDA 12.x is recommended as a minimum. CUDA 11.x is also supported.

### 4. Install CuPy for your CUDA version

Install the matching CuPy package:

```bash
# CUDA 11.x
pip install cupy-cuda11x

# CUDA 12.x
pip install cupy-cuda12x

# CUDA 13.x
pip install cupy-cuda13x
```

### 5. Install remaining dependencies

```bash
pip install -r requirements.txt
```

The requirements file includes numpy, Pillow, click, and pytest. CuPy is intentionally excluded from requirements.txt because the correct wheel depends on your CUDA version.

### 6. Verify GPU access

```bash
python -c "from textureworks.core.gpu import print_device_info; print_device_info()"
```

Expected output:

```
GPU: NVIDIA GeForce RTX 3080
  Compute capability: 8.6
  SMs: 68
  VRAM: 10240 MB total, 8934 MB free
  Max threads/block: 1024
```

### Troubleshooting

**`ImportError` when importing CuPy:** The installed CuPy wheel does not match your CUDA toolkit. Uninstall all CuPy packages (`pip uninstall cupy cupy-cuda11x cupy-cuda12x`) and reinstall the correct variant.

**`CUDADriverError` at runtime:** Your CUDA driver is older than the toolkit CuPy was built for. Update the NVIDIA driver, or install an older CuPy version matching your driver.

**`OutOfMemoryError` during generation:** The texture exceeds available VRAM. Close other GPU applications, reduce input resolution, or generate one map at a time instead of all six.

**GPU not detected:** Ensure the NVIDIA driver is installed and `nvidia-smi` reports your GPU. On WSL, confirm CUDA is forwarded from the host.

## Quick Start: Python/CuPy Path

### CLI (simplest)

Generate all six PBR maps from an input texture:

```bash
python -m textureworks.pipeline textures/test_texture3.png --output output/
```

This produces six PNG files in `output/`:

```
test_texture3_normal.png      (RGB normal map)
test_texture3_height.png      (grayscale height)
test_texture3_ao.png          (grayscale ambient occlusion)
test_texture3_roughness.png   (grayscale roughness)
test_texture3_metallic.png    (grayscale metallic)
test_texture3_specular.png    (grayscale specular)
```

Generate a single map type:

```bash
python -m textureworks.pipeline textures/test_texture3.png --map normal --output output/
```

Switch to the CuPy reference backend:

```bash
python -m textureworks.pipeline textures/test_texture3.png --backend cupy --output output/
```

### Python API

For parameter control, import generators directly:

```python
from textureworks.core.io import load_texture, save_map
from textureworks.ptx.normal import generate_normal

texture = load_texture("textures/test_texture3.png")
result = generate_normal(texture, strength=8.0)
save_map(result, "output/test_texture3_normal_strong.png")
```

Generate all maps with the pipeline function:

```python
from textureworks.core.io import load_texture, save_map
from textureworks.pipeline import generate_maps

texture = load_texture("textures/test_texture3.png")
results = generate_maps(texture, backend="ptx")

for name, data in results.items():
    save_map(data, f"output/test_texture3_{name}.png")
```

Each generator accepts parameters documented in [docs/reference/map-types.md](docs/reference/map-types.md). For example, `generate_ao` accepts `height_scale`, `power`, `num_directions`, and `max_steps`.

## Quick Start: PTX Assembly

The PTX kernels require no separate compilation. CuPy's driver API loads `.ptx` source files at runtime and JIT-compiles them to device machine code (SASS) through the NVIDIA driver.

### How it works

Each PTX wrapper in `textureworks/ptx/` follows this pattern:

```python
import cupy as cp

# Load the .ptx file and create a CUDA module
ptx_source = open("textureworks/ptx/kernels/normal.ptx").read()
mod = cp.cuda.function.Module()
mod.load(ptx_source.encode("utf-8"))

# Get a kernel function handle and launch it
kernel = mod.get_function("sobel_normal_kernel")
kernel(
    grid=(grid_x, grid_y, 1),
    block=(16, 16, 1),
    args=(input_array.data.ptr, output_array.data.ptr,
          np.int32(width), np.int32(height), np.float32(strength)),
    shared_mem=0,
)
```

### Reading the PTX source

The `.ptx` files in `textureworks/ptx/kernels/` are hand-written GPU assembly. Each file begins with a header comment documenting its purpose, grid/block configuration, and parameter layout.

A recommended reading order by complexity:

1. `metallic.ptx` (simplest: one kernel, element-wise classification, no loops)
2. `normal.ptx` (3x3 Sobel convolution, vector normalization, RGB encoding)
3. `height.ptx` (four-kernel pipeline: normalize, horizontal blur, vertical blur, contrast)
4. `roughness.ptx` (three kernels: windowed variance, Sobel edge, blend)
5. `ao.ptx` (nested loops, trigonometric approximation, most complex single kernel)

All kernels target PTX ISA version 7.0 and `sm_75` (Turing architecture). They use 16x16 thread blocks with one thread per pixel.

See [docs/explanation/ptx-primer.md](docs/explanation/ptx-primer.md) for a guided walkthrough of PTX concepts using TextureWorks kernels as examples.

## Architecture

```
textureworks/
  core/                   Shared utilities (I/O, blur, comparison, GPU info)
  cupy_ref/               CuPy reference implementations (correctness oracles)
    normal.py             generate_normal()
    height.py             generate_height()
    ao.py                 generate_ao()
    roughness.py          generate_roughness()
    metallic.py           generate_metallic()
    specular.py           generate_specular()
  ptx/                    PTX implementations (performance targets)
    kernels/              Hand-written .ptx assembly (6 files, 11 kernel entry points)
    normal.py             Python wrapper loading normal.ptx
    height.py             Python wrapper loading height.ptx (4 kernels)
    ...
  pipeline.py             CLI entry point and generate_maps() orchestrator

tests/                    pytest suite: CuPy-vs-PTX comparison per map type
benchmarks/               GPU timing: median/p95 at 1K, 2K, 4K resolutions
docs/                     Diataxis-structured documentation
textures/                 Test assets
```

The CuPy and PTX modules mirror each other exactly. Both expose `generate_<map_type>()` with identical signatures. The pipeline selects between them via the `backend` parameter. Several PTX wrappers use CuPy's `gaussian_blur` for post-processing, demonstrating interoperability between hand-written kernels and CuPy array operations.

When both `height` and `ao` appear in a generation request, the pipeline caches the height map output and passes it to the AO generator, avoiding redundant computation.

The CuPy and PTX paths produce visually identical output. A tolerance-based comparison system quantifies the small numerical differences caused by approximate math instructions (`rsqrt.approx.f32`, polynomial atan2) in the PTX kernels. Per-map tolerances range from 1 to 3 on the 0-255 scale, verified by the test suite.

See [docs/explanation/architecture.md](docs/explanation/architecture.md) for the full design rationale.

## Documentation

The `docs/` directory follows the [Diataxis](https://diataxis.fr/) framework:

**Tutorials** (learning-oriented):
- [Generate Your First Texture Map](docs/tutorials/tutorial-first-map.md)
- [Comparing CuPy and PTX Backends](docs/tutorials/tutorial-cupy-vs-ptx.md)
- [Tuning Map Parameters](docs/tutorials/tutorial-custom-params.md)

**How-to Guides** (task-oriented):
- [CLI Quick Reference](docs/how-to/cli-reference.md)
- [Integrate Into Your Asset Pipeline](docs/how-to/integrate-pipeline.md)
- [Write a Custom PTX Kernel](docs/how-to/write-custom-kernel.md)
- [Troubleshooting](docs/how-to/troubleshooting.md)

**Reference** (lookup):
- [Python API Reference](docs/reference/api.md)
- [PTX Kernel Reference](docs/reference/ptx-kernels.md)
- [Map Type Reference](docs/reference/map-types.md)
- [Output Conventions](docs/reference/output-conventions.md)
- [Algorithm Specifications](docs/algorithms.md)

**Explanation** (understanding):
- [Why Dual Implementations?](docs/explanation/architecture.md)
- [PTX Assembly Primer](docs/explanation/ptx-primer.md)
- [PBR Maps Explained](docs/explanation/pbr-maps-explained.md)
- [Benchmark Analysis](docs/explanation/benchmark-analysis.md)

## Why TextureWorks?

Commercial tools like Substance Designer and Material Maker provide powerful PBR map authoring through node-based GUIs. They excel at interactive, artist-driven workflows. They also require a display server, manual operation, and commercial licenses. Blender's shader nodes can derive maps programmatically, yet extracting standalone textures from Blender still requires scripting a GUI application.

TextureWorks occupies a different position. It is a library. It runs headless. It integrates into Python scripts, CI pipelines, and automated asset workflows with no GUI dependency. A build system can generate consistent PBR maps for hundreds of textures in a batch job.

The dual-implementation architecture serves a second audience: developers learning GPU programming. Each PTX kernel is a standalone, heavily commented example of writing NVIDIA GPU assembly. Reading the same algorithm in CuPy (high-level array operations) and PTX (register-level instructions) builds intuition for how GPU hardware executes parallel workloads. The tolerance-based comparison system demonstrates a practical approach to validating hand-written GPU code against a trusted reference.

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run tests for a specific map type
pytest tests/test_normal.py -v
```

Each test generates output via both CuPy and PTX, then asserts pixel-wise agreement within the algorithm-specified tolerance (1 to 3 on the 0-255 scale). Tests also verify output dimensions and value ranges.

## Benchmarking

```bash
python benchmarks/bench.py
```

Reports median and 95th-percentile GPU execution time for all six map types at 1024x1024, 2048x2048, and 4096x4096 resolutions. The PTX backend is faster or equivalent across all map types. AO shows the largest speedup because the PTX kernel replaces 320+ separate CuPy kernel launches with a single launch.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Contributing

See [docs/dev/contributing.md](docs/dev/contributing.md) for the step-by-step checklist for adding a new map type: algorithm specification, CuPy implementation, PTX kernel, Python wrapper, tests, and pipeline registration.