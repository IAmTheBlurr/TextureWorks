# TextureWorks

GPU-accelerated PBR texture map generation from diffuse/albedo images.

Every algorithm ships as dual implementations: a **CuPy** reference (Python,
GPU-accelerated via CUDA) and a **hand-written PTX** version (NVIDIA GPU
assembly). CuPy validates correctness. PTX explores the machine.

## Supported Map Types

| Map Type           | Input    | Output         | Algorithm                          |
|--------------------|----------|----------------|------------------------------------|
| Normal             | RGB      | RGB (XYZ)      | Sobel gradient → normal encoding   |
| Height/Displacement| RGB      | Grayscale      | Luminance extraction + contrast    |
| Ambient Occlusion  | Height   | Grayscale      | Height-field horizon mapping       |
| Roughness          | RGB      | Grayscale      | Local variance + edge density      |
| Metallic           | RGB      | Grayscale      | HSV saturation/value thresholding  |
| Specular           | RGB      | Grayscale      | Luminance-weighted sat. inversion  |

## Quick Start

```bash
# Set up virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac

# Install CuPy for your CUDA version (check with nvcc --version)
pip install cupy-cuda12x    # adjust for your CUDA version

# Install remaining dependencies
pip install -r requirements.txt

# Copy your texture into the textures/ directory, then:
python -m textureworks.pipeline textures/my_texture.png --output output/
```

## Project Structure

```
textureworks/
├── core/           # I/O, comparison, GPU device management
├── cupy_ref/       # CuPy reference implementations
├── ptx/
│   ├── kernels/    # Raw .ptx assembly files
│   └── *.py        # Python wrappers via cupy.RawKernel
├── pipeline.py     # Full map generation orchestrator
docs/
├── algorithms.md   # Mathematical specifications for all algorithms
tests/              # pytest suite (CuPy vs PTX comparison tests)
benchmarks/         # GPU timing benchmarks
textures/           # Input test textures
output/             # Generated map output
```

## Algorithm Details

See [docs/algorithms.md](docs/algorithms.md) for complete mathematical
specifications, parameter definitions, and tolerance requirements.

## Testing

```bash
pytest tests/ -v
```

Each test generates output via both CuPy and PTX, then asserts pixel-wise
agreement within the algorithm's specified tolerance.

## Benchmarking

```bash
python benchmarks/bench.py
```

Reports median and p95 GPU execution time at 1024, 2048, and 4096 resolutions.
