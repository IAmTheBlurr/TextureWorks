# Tutorial: Generating Your First Texture Map

This tutorial walks you through generating PBR texture maps from a diffuse input image. By the end, you will have generated a normal map, inspected the output, and then generated a full set of six maps.

## Prerequisites

- Python 3.10 or later
- NVIDIA GPU with CUDA support
- CuPy installed for your CUDA version (`pip install cupy-cuda11x` or `cupy-cuda12x`)
- TextureWorks dependencies installed: `pip install -r requirements.txt`

Verify your GPU is accessible:

```bash
python -c "from textureworks.core.gpu import print_device_info; print_device_info()"
```

You should see your GPU name, compute capability, and available VRAM.

## Step 1: Generate a Normal Map

TextureWorks includes a test texture at `textures/test_texture3.png`. Generate a normal map from it:

```bash
python -m textureworks.pipeline textures/test_texture3.png --map normal --output output/
```

Expected terminal output:

```
Loading textures/test_texture3.png...
  Texture shape: (1024, 1024, 3), backend: ptx
  Saved normal -> output/test_texture3_normal.png
Done.
```

The output file is `output/test_texture3_normal.png`.

## Step 2: Understand the Output

Open `output/test_texture3_normal.png` in an image viewer. The image has a blue-purple tint. This is expected.

A normal map encodes surface direction as color:
- **Red channel** = horizontal direction (left/right). 128 = no deflection.
- **Green channel** = vertical direction (up/down). 128 = no deflection.
- **Blue channel** = surface-facing direction. 255 = pointing straight outward.

A flat surface with no detail produces the color (128, 128, 255), a medium blue. Edges and surface details in the original texture produce color shifts in the red and green channels.

Game engines read these color values and use them to adjust per-pixel lighting. The result is surface detail without extra geometry.

## Step 3: Generate All Maps

Generate the complete set of six PBR maps:

```bash
python -m textureworks.pipeline textures/test_texture3.png --output output/
```

Expected terminal output:

```
Loading textures/test_texture3.png...
  Texture shape: (1024, 1024, 3), backend: ptx
  Saved normal -> output/test_texture3_normal.png
  Saved height -> output/test_texture3_height.png
  Saved ao -> output/test_texture3_ao.png
  Saved roughness -> output/test_texture3_roughness.png
  Saved metallic -> output/test_texture3_metallic.png
  Saved specular -> output/test_texture3_specular.png
Done.
```

## Step 4: Inspect Each Map

Open each output file and observe:

**Normal map** (`_normal.png`): RGB image with a blue tint. Surface details appear as color variations in the red and green channels.

**Height map** (`_height.png`): Grayscale image. Bright pixels represent high points, dark pixels represent low points. This map drives displacement and parallax effects.

**AO map** (`_ao.png`): Grayscale image. Mostly bright (white = fully lit). Crevices and concave areas appear darker. This simulates soft ambient shadows.

**Roughness map** (`_roughness.png`): Grayscale image. Bright pixels are rough (scattered reflections). Dark pixels are smooth (sharp reflections). Areas with fine texture detail tend to appear rougher.

**Metallic map** (`_metallic.png`): Grayscale image, often near-binary. White pixels are classified as metal. Black pixels are dielectric (non-metal). The classification is based on color saturation and brightness.

**Specular map** (`_specular.png`): Grayscale image. Bright pixels reflect more light. Derived from luminance and saturation of the original texture.

## Step 5: Try Your Own Texture

Replace the input path with any image file:

```bash
python -m textureworks.pipeline path/to/your/texture.png --output output/
```

TextureWorks accepts PNG, JPG, BMP, TIFF, and any format Pillow supports. RGBA images are automatically converted to RGB.

## What Next?

- [Comparing CuPy and PTX Backends](tutorial-cupy-vs-ptx.md) to understand the dual-implementation system
- [Tuning Parameters](tutorial-custom-params.md) to customize map output
- [CLI Reference](../how-to/cli-reference.md) for all command-line options
- [PBR Maps Explained](../explanation/pbr-maps-explained.md) for deeper context on how game engines use these maps
