# TextureWorks Documentation

TextureWorks is a GPU-accelerated library for generating PBR (Physically Based Rendering) texture maps from diffuse/albedo input images. It produces six map types: normal, height, ambient occlusion, roughness, metallic, and specular. Every algorithm ships with two implementations: a CuPy reference (Python GPU arrays) and a hand-written PTX kernel (NVIDIA GPU assembly).

## Quick Start

```bash
pip install -r requirements.txt
python -m textureworks.pipeline textures/test_texture3.png --output output/
ls output/
```

This generates all six PBR maps from the test texture and saves them as 8-bit PNGs in the `output/` directory.

## Tutorials

Learning-oriented guides. Start here if you are new to TextureWorks.

- [Generate Your First Texture Map](tutorials/tutorial-first-map.md): Walk through producing a normal map, then all maps at once
- [Understanding the Dual Implementation](tutorials/tutorial-cupy-vs-ptx.md): Run the same generation with CuPy and PTX backends, then compare outputs
- [Tuning Map Parameters](tutorials/tutorial-custom-params.md): Experiment with strength, blur, and contrast settings to control map output

## How-To Guides

Task-oriented recipes for specific goals.

- [CLI Quick Reference](how-to/cli-reference.md): Every command, flag, and common usage pattern
- [Parallax Occlusion Mapping in Unity](how-to/parallax-occlusion-mapping.md): Export 16-bit height and wire the HLSL function into URP Shader Graph
- [Walk the Unity Material Lab](how-to/material-lab.md): Compare materials in a walkable Unity 6.6 gallery and workshop
- [Integrate TextureWorks Into Your Asset Pipeline](how-to/integrate-pipeline.md): Python API usage, batch processing, and map chaining
- [Write a Custom PTX Kernel](how-to/write-custom-kernel.md): Anatomy of a PTX kernel and step-by-step guide for adding a new map type
- [Troubleshooting Common Issues](how-to/troubleshooting.md): CUDA errors, out of memory, wrong output, and parameter tuning

## Reference

Precise technical descriptions for lookup.

- [Python API Reference](reference/api.md): Every public function, parameter, and return type across all modules
- [PTX Kernel Reference](reference/ptx-kernels.md): Kernel names, parameter layouts, register conventions, and memory patterns
- [Map Type Reference](reference/map-types.md): All six map types with parameters, defaults, valid ranges, and output encoding
- [Output Format and Naming Conventions](reference/output-conventions.md): File naming, color encoding, value ranges, and bit depth
- [Algorithm Specifications](algorithms.md): Full mathematical definitions for every map generation algorithm
- [Parallax Occlusion Mapping Contract](reference/parallax-algorithm.md): Runtime ray, sampling, height polarity, and validation boundaries
- [Material Bundles](reference/material-bundles.md): Reproducible authored inputs, batch recipes, encodings and Unity import
- [Material Fields](reference/material-fields.md): Detail, physical normals, signed curvature, wear and two-material composition

## Explanation

Background knowledge and design rationale.

- [Why Dual Implementations?](explanation/architecture.md): The CuPy-as-oracle, PTX-as-target design philosophy
- [PTX Assembly Primer](explanation/ptx-primer.md): PTX's role in the NVIDIA pipeline, registers, memory spaces, and a worked kernel walkthrough
- [PBR Texture Maps and Why They Matter](explanation/pbr-maps-explained.md): How each map type contributes to rendered surfaces in game engines
- [Performance: CuPy vs PTX](explanation/benchmark-analysis.md): Interpreting benchmark results and when each backend matters

## Developer Notes

For contributors and maintainers.

- [Adding a New Map Type](dev/contributing.md): Step-by-step checklist from algorithm spec through pipeline integration
- [Test Architecture](dev/testing.md): How CuPy-vs-PTX comparison tests work, fixtures, and tolerance values
- [POM Geometric Validation](dev/parallax-validation.md): Perspective comparisons, generated inputs, camera sweeps, and measured limits
- [Material Cluster Validation](dev/material-cluster-validation.md): Analytic GPU checks, visual review, player smoke and measured cost
- [Project Layout](dev/project-structure.md): Directory map, file naming conventions, and module dependency graph

## Where to Go Next

| Your goal | Start here |
|-----------|-----------|
| Never used TextureWorks before | [Generate Your First Texture Map](tutorials/tutorial-first-map.md) |
| Need to accomplish a specific task | [CLI Quick Reference](how-to/cli-reference.md) |
| Looking up a function signature or parameter | [Python API Reference](reference/api.md) |
| Understanding a design decision | [Why Dual Implementations?](explanation/architecture.md) |
| Adding a new map type | [Adding a New Map Type](dev/contributing.md) |
