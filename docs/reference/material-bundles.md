# Material bundles, version 1

`textureworks.bundle.generate_bundle(recipe, output, base_dir=".", backend="ptx")`
exports a folder with `material.json` and PNG textures. `load_bundle(path)` checks
the schema, profile, every image header, color/encoding metadata and SHA-256 hash.
`generate_batch(batch_path, output, backend="ptx")` resolves recipe paths relative
to the batch file and generates materials in name order. Duplicate names, including
case collisions on Windows, are errors. The six-map API and default CLI are unchanged.

The profile is `textureworks-urp-two-material-v1`, implemented in the local Unity
package by `TextureWorks/URP/Layered Lit`. Version 1 supports one or two materials
on the same UV grid, physical texture dimensions and white-top height reference.
Every material channel and coverage mask must have identical dimensions. The
external detail source may have its own dimensions and physical size. No implicit
resizing, normalization of authored heights, color-profile conversion or normal
channel guessing takes place.

## Generate

```powershell
# Quick single-material workflow, 1 meter square, deterministic preset defaults:
.\.venv\Scripts\python.exe -m textureworks.pipeline textures/pom-validation/oak-planks.png `
  --bundle-preset wood --output output/material-lab-oak

# Authored inputs, two materials and explicit physical sizes:
.\.venv\Scripts\python.exe -m textureworks.bundle generate path/to/recipe.json `
  --output output/material-lab-example --backend ptx
.\.venv\Scripts\python.exe -m textureworks.bundle verify output/material-lab-example
.\.venv\Scripts\python.exe -m textureworks.bundle batch path/to/batch.json `
  --output output/material-lab-collection
```

The API accepts the same recipe object:

```python
from textureworks.bundle import generate_bundle, load_bundle
manifest = generate_bundle(recipe, "output/material-lab-example", base_dir="textures")
bundle = load_bundle(manifest)
```

Minimal two-material recipe (all paths relative to the recipe file):

```json
{
  "schema_version": 1,
  "name": "paint-over-steel",
  "preset": "painted-metal",
  "physical_size": [1.0, 1.0],
  "relief_depth": 0.012,
  "boundary": "wrap",
  "seed": 42,
  "layers": [
    {"name": "Paint", "albedo": "paint.png", "height": "paint-height.png", "roughness": 0.45, "metallic": 0},
    {"name": "Steel", "albedo": "steel.png", "height": "steel-height.png", "roughness": 0.3, "metallic": 1}
  ],
  "mask": "exposed-steel.png",
  "detail": {"source": "fine-grain.png", "physical_size": [0.2, 0.2], "radius": 4},
  "composition": {"coverage": 0.5, "blend_width": 0.2, "height_bias": 0.5, "quality": "balanced"}
}
```

A batch is `{"schema_version":1,"recipes":["paint.json","stone.json"]}`.
Material names contain 1–64 letters, digits, underscores or hyphens. Unknown
recipe keys are rejected so misspelled controls cannot silently disappear.
Output directories must be empty or contain an intact bundle. Regeneration checks
the previous hashes before replacing generated files; Unity `.meta` files survive.
Source imagery must live outside the destination. Temporary generation completes
before copying files, and the manifest is replaced last. File copy failures can
leave a partially updated folder, which verification will reject.

## Authored inputs and encodings

PNG is the version 1 interchange: RGB8 albedo and normals, grayscale 8/16-bit
height, roughness, metallic, AO, edge, cavity and coverage masks. Alpha, palette,
RGB16, HDR and ICC-profiled inputs are rejected with an explicit error. Convert
them deliberately before bundling. Dimensions are 2–8192 on each axis, including
odd and non-square images. Raw authored files are copied byte for byte.

Each layer accepts `albedo`, `height`, `normal`, `roughness`, `metallic`, `ao`,
`edge` and `cavity`. Only albedo is required. Roughness/metallic/AO also accept a
constant in [0,1]. A file may be a path string or this metadata object:

```json
{"path":"normal.png","color_space":"linear","encoding":"xyz-unorm",
 "normal_convention":"directx","physical_size":[1,1],"relief_depth":0.012,
 "height_reference":1,"provenance":"Authored tangent normal, exported from mesh bake"}
```

Albedo defaults to sRGB; it can explicitly declare `linear`. Data is always linear.
Height encoding is `white-top`: 1 at the mesh plane, 0 one `relief_depth` below it.
Normals are tangent XYZ, with explicit `opengl` (+Y, default) or `directx` (-Y).
Positive Z is required. Optional physical metadata must agree with the bundle.
Other scalar encodings are `unorm`. Signed curvature is `2*C-1`, scaled by the
recorded `wear.curvature_range` in inverse meters.

Derived scalars are separate **16-bit PNGs**. Height is rounded once before
normals, AO and curvature use it, so they share the exported field. Authored height
is neither renormalized nor blurred. Missing height uses the existing generator
on linear albedo with sigma 1.5 and contrast 1.2; this remains an estimate.
Missing roughness and metallic use the named material preset. AO uses the common
height with the legacy heuristic's default horizon parameters.

Generated normal components use byte = round(128+127*N). Decode as
`(sample*255-128)/127`, then normalize. This `xyz-centered-unorm8` encoding has
exact neutral bytes (128,128,255). Authored normals retain `xyz-unorm`, decoded
as `2*sample-1`, and their recorded green direction. Generated detail color uses
`residual-centered-unorm8`: byte = round(128+127*residual), neutral byte 128.
All are sampled **linear**, with no Unity normal-map channel repacking.

The `wear` RGB texture identifies R=edge chipping, G=cavity grime, B=maximum of
the two. Separate edge/cavity files preserve 16-bit derived values. This is a
TextureWorks diagnostic layout. There is no standard URP/HDRP mask-map claim or
height packed into an 8-bit alpha channel. Runtime scalar textures remain separate.

`preview_height` and `preview_weight` show the recipe's initial offline composition.
They are diagnostics. The runtime material reads both original heights and the
mask, recomputing their composition while tracing whenever coverage changes.

## Presets and parameters

All presets are deterministic artistic defaults, not measured material properties.

| Preset | Relief meters | Roughness | Metallic | Curvature range /m | Detail relief meters |
| --- | ---: | ---: | ---: | ---: | ---: |
| masonry | .04 | .78 | 0 | 40 | .0008 |
| wood | .025 | .65 | 0 | 30 | .0004 |
| painted-metal | .012 | .40 | 0 | 50 | .0002 |
| fine-detail | .003 | .70 | 0 | 80 | .0003 |

Physical size defaults to [1,1] meters. Common relief depth is [0,100] meters.
Sampling defaults to wrap; clamp is also supported. The stable seed is uint32.
The full resolved recipe and input/output hashes are recorded in the manifest.

| Group | Parameters and defaults |
| --- | --- |
| Detail | radius 4 texels [1,64]; physical_size = base size; tiling 4 [.01,128]; color_strength .35 [0,2]; normal_strength .5 [0,4]; roughness_strength .1 [0,1]; fade_start 3, fade_end 8 meters [0,10000] |
| Wear | curvature_range from preset [1e-6,1e6]; threshold .1 [0,.999]; variation .35 [0,1]; edge_amount .4/.35/.8/.25 and cavity_amount .85/.45/.25/.35 for masonry/wood/painted-metal/fine-detail |
| Composition | coverage .5 [0,1]; blend_width .2 [0,1]; height_bias .5 [0,1]; mask_source cavity (edge/combined available); quality balanced (low/high available) |

When an authored coverage mask is absent, the selected controlled wear signal from
layer A supplies it. A/B can represent paint/substrate or masonry/grime; the
recipe establishes those identities. Authored edge/cavity inputs replace the
inference before wear controls. They do not modify the original material.
See the [algorithm contract](material-fields.md) for formulas and boundaries.

## Unity setup

Install the local package, then copy the complete bundle folder under `Assets`.
Select its `material.json` and choose **TextureWorks > Set up selected material
bundle**. The reusable editor API is
`TextureWorks.Editor.TextureWorksBundleImporter.Import("Assets/MyBundle/material.json")`.
Setup validates hashes and headers before changing imports. It enforces linear
data/sRGB color, raw XYZ normals, wrap/clamp, trilinear mipmaps, anisotropy 4,
uncompressed RGB24/R8/R16 and no NPOT resizing. Height is always imported as R16;
authored scalar precision is preserved. It writes deterministic material defaults
beside the manifest. Re-running setup explicitly resets those material defaults.

The profile targets Unity 6000.6 / URP 17.6, forward opaque rendering with valid
tangents and orthogonal UV axes. Material stages are base, height/authored normals,
POM, detail, wear visualization and final layers. The debug selector exposes height,
mask, signed curvature, chipping, grime, weight and normals. Coverage controls can
be changed at runtime; 0 and 1 are exact endpoints, including zero blend width.
The low POM setting uses 8–24 samples and 2 refinements; balanced uses 16–64/4;
high uses 32–128/6. Thin features can be missed between march samples.
The validation record reports measured costs and the tested Windows graphics API.

RNM superposes detail. Material transitions interpolate authored slope residuals
over a normal differentiated from the composed height, retaining the mask-gradient
term. Physical depth follows world scale and texture tiling. POM keeps the baseline
distance/grazing fade; detail has its own smooth distance fade. Equal/reversed fade
bounds disable distance fading. Sampling always uses the original UV gradients.
Silhouettes and cast shadows remain at the mesh surface. General skewed UVs,
baked lightmaps, deferred rendering, XR and other pipelines are outside this profile.
