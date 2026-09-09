# Output Format and Naming Conventions

Reference for file naming, color encoding, value ranges, and bit depth of TextureWorks output maps.

## File Naming

Output files follow the pattern:

```
<input_stem>_<map_type>.png
```

Where `<input_stem>` is the input filename without extension and `<map_type>` is one of: `normal`, `height`, `ao`, `roughness`, `metallic`, `specular`.

**Example:** Input `textures/test_texture3.png` produces:

```
output/test_texture3_normal.png
output/test_texture3_height.png
output/test_texture3_ao.png
output/test_texture3_roughness.png
output/test_texture3_metallic.png
output/test_texture3_specular.png
```

The default output directory is `output/`. Override it with `--output` / `-o`.

## Bit Depth

Output maps default to 8-bit PNG files. Use `--height-bits 16` to export height
as a 16-bit grayscale PNG for Parallax Occlusion Mapping or displacement. Other
maps retain their 8-bit encoding. The Python API exposes `save_map(..., bits=16)`
for any scalar map.

- Single-channel maps (height, AO, roughness, metallic, specular): 8-bit grayscale (mode `"L"`)
- Normal maps: 8-bit per channel RGB (mode `"RGB"`)

Internal computation uses float32. Quantization to 8-bit occurs only at the final `save_map` step: values are multiplied by 255, clipped to [0, 255], and cast to uint8.

For 16-bit output, values are clipped to `[0, 1]`, multiplied by 65535, and rounded
to the nearest unsigned integer. Maximum quantization error is half a 16-bit
step (plus float rounding). `load_texture` preserves this precision when reading
the grayscale image back. Extra output precision does not change the height
algorithm or tighten the existing CuPy/PTX comparison tolerance.

## Color Encoding Per Map Type

| Map Type | Channels | White Means | Black Means | Neutral Value |
|----------|----------|-------------|-------------|---------------|
| Normal | 3 (RGB) | N/A (directional) | N/A (directional) | (128, 128, 255) = flat surface |
| Height | 1 (grayscale) | High elevation | Low elevation | 128 = midpoint |
| AO | 1 (grayscale) | Unoccluded (fully lit) | Fully occluded | 255 = typical open surface |
| Roughness | 1 (grayscale) | Rough surface | Smooth surface | Varies by texture |
| Metallic | 1 (grayscale) | Metal | Dielectric (non-metal) | 0 or 255 (often near-binary) |
| Specular | 1 (grayscale) | High specularity | Low specularity | Varies by texture |

## Normal Map Encoding

The normal map uses a standard tangent-space encoding:

- **R channel** = X component of the normal vector: 128 = no horizontal deflection
- **G channel** = Y component of the normal vector: 128 = no vertical deflection
- **B channel** = Z component (surface-facing): 255 = pointing straight up (flat surface)

Encoding formula: `pixel = (normal_component * 0.5 + 0.5) * 255`

Decoding formula: `normal_component = (pixel / 255.0) * 2.0 - 1.0`

## Value Ranges

Map outputs use float32 in `[0, 1]`. The default file conversion uses `[0, 255]`;
16-bit grayscale uses `[0, 65535]`. Height is linear data: black is low, white
is high. Disable sRGB conversion and select a runtime format that preserves
16-bit precision in the consuming engine.

## Input Format

TextureWorks accepts any image format supported by Pillow (PIL): PNG, JPG, BMP, TIFF, and others.

- RGB images are used directly
- RGBA images are converted to RGB (alpha channel is dropped)
- Other modes (palette, CMYK) are converted to RGB automatically
- Grayscale input is used as-is for single-channel processing
# Versioned material outputs

The [material bundle reference](material-bundles.md) defines per-file precision,
color space, normal convention, height reference and SHA-256 records. Bundle
scalars use separate 16-bit generated outputs; legacy six-map defaults below
are unchanged. Bundle centered RGB encodings have their own explicit decoder.
