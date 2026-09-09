# CLI Quick Reference

Complete command reference for the TextureWorks command-line interface.

## Map Generation

### Command Syntax

```bash
python -m textureworks.pipeline INPUT_PATH [OPTIONS]
```

`INPUT_PATH` is required and must point to an existing image file (PNG, JPG, BMP, TIFF, or any format Pillow supports).

### Options

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--output` | `-o` | path | `output` | Output directory. Created automatically if it does not exist. |
| `--map` | `-m` | string | `all` | Map type to generate. Choices: `normal`, `height`, `ao`, `roughness`, `metallic`, `specular`, `all`. |
| `--backend` | `-b` | string | `ptx` | Computation backend. Choices: `cupy`, `ptx`. |
| `--height-bits` | | choice | `8` | Height PNG precision: `8` or `16`. Has no effect if height is not requested. |

### Examples

Generate all six maps with the default PTX backend:

```bash
python -m textureworks.pipeline textures/test_texture3.png --output output/
```

Generate only a normal map:

```bash
python -m textureworks.pipeline textures/test_texture3.png --map normal --output output/
```

Generate using the CuPy reference backend:

```bash
python -m textureworks.pipeline textures/test_texture3.png --backend cupy --output output/
```

Generate a specific map with a specific backend:

```bash
python -m textureworks.pipeline textures/test_texture3.png --map ao --backend ptx --output output/
```

Custom output directory:

```bash
python -m textureworks.pipeline textures/my_texture.png -o results/my_texture/
```

### Output Files

Generate all maps with a 16-bit height file:

```bash
python -m textureworks.pipeline textures/test_texture3.png --height-bits 16 --output output/
```

This works with either backend. The filename stays `<input_stem>_height.png`;
the five other maps retain their default 8-bit encoding.

Output files follow the naming pattern `<input_stem>_<map_type>.png`. For input `textures/test_texture3.png`:

```
output/test_texture3_normal.png
output/test_texture3_height.png
output/test_texture3_ao.png
output/test_texture3_roughness.png
output/test_texture3_metallic.png
output/test_texture3_specular.png
```

See [Output Conventions](../reference/output-conventions.md) for encoding details.

## CuPy vs PTX Comparison

Compare outputs from both backends for a specific map type:

```bash
python -m textureworks.core.compare cupy_ref.normal ptx.normal textures/test_texture3.png
```

The module arguments use Python dotted-path notation relative to `textureworks`:
- First argument: CuPy module path (e.g., `cupy_ref.normal`, `cupy_ref.ao`)
- Second argument: PTX module path (e.g., `ptx.normal`, `ptx.ao`)
- Third argument: path to the input texture

The comparison report shows:
- **Max pixel difference**: largest per-pixel deviation (on the 0-255 scale)
- **Mean pixel difference**: average deviation across all pixels
- **Within tolerance**: percentage of pixels within the acceptable threshold

See [Architecture: The Tolerance System](../explanation/architecture.md) for tolerance values per map type.

## GPU Information

Check GPU capabilities and available VRAM:

```python
python -c "from textureworks.core.gpu import print_device_info; print_device_info()"
```

Example output:

```
GPU: NVIDIA GeForce RTX 3080
  Compute capability: 8.6
  SMs: 68
  VRAM: 10240 MB total, 8934 MB free
  Max threads/block: 1024
```

## Benchmarks

Run the full benchmark suite across all map types, backends, and resolutions:

```bash
python benchmarks/bench.py
```

This tests all six map types at 1024x1024, 2048x2048, and 4096x4096 resolutions with 100 iterations each. Expect the full suite to take several minutes.

See [Benchmark Analysis](../explanation/benchmark-analysis.md) for interpreting results.

## Batch Processing

Process multiple textures with a shell loop:

```bash
for f in textures/*.png; do
    python -m textureworks.pipeline "$f" --output output/
done
```

Process only AO maps for a directory of textures:

```bash
for f in textures/*.png; do
    python -m textureworks.pipeline "$f" --map ao --output output/
done
```

## Material bundles and presets

Use `--bundle-preset masonry|wood|painted-metal|fine-detail` on the pipeline CLI
for a reproducible single-material bundle. The dedicated bundle CLI accepts
authored channels, detail and two-material composition parameters in JSON:

```powershell
.\.venv\Scripts\python.exe -m textureworks.bundle generate textures/material-cluster/masonry.json `
  --backend ptx --output output/material-cluster-masonry
.\.venv\Scripts\python.exe -m textureworks.bundle verify output/material-cluster-masonry
.\.venv\Scripts\python.exe -m textureworks.bundle batch textures/material-cluster/batch.json `
  --output output/material-cluster-collection
```

Bundle PNG and metadata requirements are stricter than the legacy image loader.
See [material bundles](../reference/material-bundles.md) for authored precision,
color space, physical units, parameter ranges and Unity setup.

## Tests

Run all tests:

```bash
pytest tests/ -v
```

Run tests for a specific map type:

```bash
pytest tests/test_normal.py -v
```

See [Testing Guide](../dev/testing.md) for test architecture details.

## Notes

- The legacy six-map CLI does not expose per-map parameters (strength, blur_sigma, etc.). Use the [Python API](integrate-pipeline.md) for those controls; bundle recipes expose their own documented material parameters.
- There is no `--backend=both` option. Use the comparison CLI or the Python API to compare backends.
- RGBA images are automatically converted to RGB (alpha channel is dropped).
- The pipeline caches the height map and passes it to the AO generator when generating all maps, avoiding redundant computation.

## Further Reading

- [Python API Integration](integrate-pipeline.md) for programmatic usage
- [Map Type Reference](../reference/map-types.md) for parameter details per map type
- [Troubleshooting](troubleshooting.md) for common issues
