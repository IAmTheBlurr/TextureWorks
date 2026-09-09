# Generated POM inputs

Four generated albedo inputs exercise different structures: limestone blocks,
brick and mortar, machined metal seams, and wood grain. Each source is preserved
at its delivered 1254 x 1254 resolution. The complete prompts, original filenames,
and SHA-256 hashes are in [provenance.json](provenance.json).

Generation used the built-in image tool on 2026-09-08. The request named ImageGen
2.5, but that tool exposed no model selector. Each PNG's embedded C2PA metadata
names `gpt-image` version `2.0`; its signature was not independently validated.
The serving model cannot be established beyond that metadata. Do not label these
assets as verified ImageGen 2.5 output.

These images have no ground-truth height. Brightness varies with color and baked
lighting, and the edges are not certified seamless. The red brick is a useful
failure case for luminance inference: light mortar may become raised. Inverting
the whole height map also inverts the brick detail, so that is not a general fix.
Use an authored or measured height map when physical material structure matters.

Generate repeatable test inputs using the project's CuPy and PTX implementations:

```powershell
.\.venv\Scripts\python.exe -m scripts.prepare_parallax_validation
```

The script downsamples albedo to 512 pixels and the height input to 256 pixels,
checks height backend parity, and exports 16-bit height with sigma 1.5 and contrast
1.2. It records source/output hashes and physical depth presets. The derived files
go into ignored `output/pom-inputs/`; the source images remain unchanged.

The Unity geometry harness compares POM with the same inferred height field
rendered as a displaced mesh. That comparison tests ray intersection and visual
consistency; it does not establish the true shape of the photographed material.
