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

All output maps are 8-bit PNG files.

- Single-channel maps (height, AO, roughness, metallic, specular): 8-bit grayscale (mode `"L"`)
- Normal maps: 8-bit per channel RGB (mode `"RGB"`)

Internal computation uses float32. Quantization to 8-bit occurs only at the final `save_map` step: values are multiplied by 255, clipped to [0, 255], and cast to uint8.

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

All internal float32 arrays use the [0.0, 1.0] range. The `save_map` function converts to [0, 255] uint8 for PNG output. The `load_texture` function converts from [0, 255] uint8 input to [0.0, 1.0] float32.

## Input Format

TextureWorks accepts any image format supported by Pillow (PIL): PNG, JPG, BMP, TIFF, and others.

- RGB images are used directly
- RGBA images are converted to RGB (alpha channel is dropped)
- Other modes (palette, CMYK) are converted to RGB automatically
- Grayscale input is used as-is for single-channel processing
