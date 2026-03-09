# Tutorial: Tuning Map Parameters

This tutorial demonstrates how custom parameters affect texture map output. You will use the Python API to generate maps with different settings and observe the visual impact.

## Prerequisites

Complete the [First Map Tutorial](tutorial-first-map.md) before starting this one. You should be comfortable generating maps from the command line.

## Why the Python API?

The CLI does not expose per-map parameters like `strength`, `blur_sigma`, or `contrast`. It uses default values for all parameters. To customize these, import the generator functions directly in Python.

## Normal Map: Strength

The `strength` parameter controls how exaggerated the surface relief appears. Higher values create deeper-looking surface detail.

Create a Python script or run interactively:

```python
from textureworks.core.io import load_texture, save_map
from textureworks.ptx.normal import generate_normal

texture = load_texture("textures/test_texture3.png")

# Subtle relief
result_low = generate_normal(texture, strength=0.5)
save_map(result_low, "output/normal_strength_0.5.png")

# Default
result_default = generate_normal(texture, strength=2.0)
save_map(result_default, "output/normal_strength_2.0.png")

# Exaggerated relief
result_high = generate_normal(texture, strength=10.0)
save_map(result_high, "output/normal_strength_10.0.png")
```

Open all three images:

- **strength=0.5**: The image is almost entirely blue (128, 128, 255). Surface detail is barely visible. Use this for subtle materials like polished stone.
- **strength=2.0** (default): Clear surface detail with moderate depth. Good for most textures.
- **strength=10.0**: Dramatic surface relief. Colors shift strongly toward red and green at edges. Use this for stylized or exaggerated materials.

Valid range: [0.1, 20.0].

## Height Map: Blur and Contrast

The height map has two primary controls: `blur_sigma` smooths the height field, and `contrast` stretches its dynamic range.

```python
from textureworks.ptx.height import generate_height

texture = load_texture("textures/test_texture3.png")

# Sharp, no blur
result_sharp = generate_height(texture, blur_sigma=0.0, contrast=1.2)
save_map(result_sharp, "output/height_sharp.png")

# Default
result_default = generate_height(texture, blur_sigma=1.0, contrast=1.2)
save_map(result_default, "output/height_default.png")

# Very smooth
result_smooth = generate_height(texture, blur_sigma=5.0, contrast=1.2)
save_map(result_smooth, "output/height_smooth.png")
```

- **blur_sigma=0.0**: Every luminance variation in the original texture appears in the height map. Pixel-level noise is preserved. Produces noisy displacement.
- **blur_sigma=1.0** (default): Mild smoothing removes high-frequency noise while preserving major features.
- **blur_sigma=5.0**: Only large-scale features remain. Fine detail is completely smoothed away. Use this for broad, rolling displacement.

Valid range: [0.0, 10.0].

Now try varying contrast:

```python
# Low contrast
result_flat = generate_height(texture, blur_sigma=1.0, contrast=0.5)
save_map(result_flat, "output/height_flat.png")

# High contrast
result_crisp = generate_height(texture, blur_sigma=1.0, contrast=3.0)
save_map(result_crisp, "output/height_crisp.png")
```

- **contrast=0.5**: The height range is compressed. The image appears washed out with values clustered around mid-gray.
- **contrast=3.0**: The height range is stretched. Highlights clip to white, shadows clip to black. Features become more defined.

Valid range: [0.5, 3.0].

## Ambient Occlusion: Height Scale and Power

AO is sensitive to `height_scale`, which controls how much the height field influences occlusion depth.

```python
from textureworks.ptx.ao import generate_ao

texture = load_texture("textures/test_texture3.png")

# Subtle occlusion
result_subtle = generate_ao(texture, height_scale=5.0, power=1.0)
save_map(result_subtle, "output/ao_subtle.png")

# Default
result_default = generate_ao(texture, height_scale=10.0, power=1.5)
save_map(result_default, "output/ao_default.png")

# Deep occlusion
result_deep = generate_ao(texture, height_scale=30.0, power=2.0)
save_map(result_deep, "output/ao_deep.png")
```

- **height_scale=5.0, power=1.0**: Faint shadows in deep crevices. Most of the image stays white. Suitable for subtle, realistic AO.
- **height_scale=10.0, power=1.5** (default): Visible darkening in concavities. Good balance for most textures.
- **height_scale=30.0, power=2.0**: Strong, dark shadows. Crevices and edges are prominently darkened. Use for stylized rendering or when the input texture has subtle height variation.

Valid ranges: `height_scale` [0.1, 50.0], `power` [0.5, 4.0].

## Roughness: Variance vs Edge Blending

The roughness map blends two signals: local variance and Sobel edge magnitude. The `alpha` parameter controls the blend ratio.

```python
from textureworks.ptx.roughness import generate_roughness

texture = load_texture("textures/test_texture3.png")

# Variance-dominant
result_var = generate_roughness(texture, alpha=1.0, radius=4)
save_map(result_var, "output/roughness_variance.png")

# Edge-dominant
result_edge = generate_roughness(texture, alpha=0.0, radius=4)
save_map(result_edge, "output/roughness_edges.png")

# Balanced (default is 0.6)
result_balanced = generate_roughness(texture, alpha=0.6, radius=4)
save_map(result_balanced, "output/roughness_balanced.png")
```

- **alpha=1.0**: Only variance contributes. Areas with noisy or varied pixel values appear rough. Uniform areas appear smooth.
- **alpha=0.0**: Only edge magnitude contributes. Sharp edges appear rough, flat regions appear smooth. Produces a more "outlined" look.
- **alpha=0.6** (default): Both signals contribute, with variance weighted higher. This captures both texture variation and edge sharpness.

Valid range: [0.0, 1.0].

## Metallic: Threshold Tuning

The metallic map classifies pixels based on HSV saturation and brightness. Different input textures need different thresholds.

```python
from textureworks.ptx.metallic import generate_metallic

texture = load_texture("textures/test_texture3.png")

# Default (soft transitions)
result_soft = generate_metallic(texture, sat_threshold=0.35, hard_edges=False)
save_map(result_soft, "output/metallic_soft.png")

# Binary classification
result_hard = generate_metallic(texture, sat_threshold=0.35, hard_edges=True)
save_map(result_hard, "output/metallic_hard.png")

# More permissive (more pixels classified as metal)
result_permissive = generate_metallic(texture, sat_threshold=0.5, val_threshold=0.05)
save_map(result_permissive, "output/metallic_permissive.png")
```

- **hard_edges=False** (default): Soft gradient transitions between metallic and dielectric regions.
- **hard_edges=True**: Binary output (pure black or pure white). Every pixel above the 0.5 threshold becomes metal, every pixel below becomes dielectric.
- **Higher sat_threshold**: Allows more saturated pixels to qualify as metallic. Use when the input contains colored metals.

Valid ranges: `sat_threshold` [0.05, 0.5], `val_threshold` [0.01, 0.8].

## Combining Parameters Across Maps

Maps interact in a PBR shader. Adjusting one map may require compensating adjustments in others:

```python
texture = load_texture("textures/test_texture3.png")

# High-relief style: strong normals, deep AO, high contrast
normal = generate_normal(texture, strength=8.0)
height = generate_height(texture, blur_sigma=0.5, contrast=2.0)
ao = generate_ao(texture, height_map=height, height_scale=25.0, power=2.0)

save_map(normal, "output/stylized_normal.png")
save_map(height, "output/stylized_height.png")
save_map(ao, "output/stylized_ao.png")
```

Notice the `height_map=height` parameter in `generate_ao`. Passing a pre-computed height map avoids regenerating it with default parameters inside the AO function. This ensures the AO computation uses the same height settings.

## What Next?

- [Map Type Reference](../reference/map-types.md) for complete parameter tables
- [Python API Integration](../how-to/integrate-pipeline.md) for batch processing and pipeline workflows
- [Troubleshooting](../how-to/troubleshooting.md) if output looks wrong
