# PBR Texture Maps: What They Are and Why They Matter

This document explains Physically Based Rendering maps in the context of real-time game engines. It covers what each map contributes to the final rendered image, how the maps interact, and where algorithmic generation fits into a production workflow.

## PBR in Brief

Physically Based Rendering models light-surface interaction using principles from physics. Two core ideas drive PBR shaders:

**Energy conservation.** A surface cannot reflect more light than it receives. Highly reflective areas reduce diffuse light proportionally. This constraint produces materials with consistent behavior across lighting environments.

**Microfacet theory.** Real surfaces consist of tiny facets oriented in various directions. The statistical distribution of facet orientations determines how a surface scatters light. Rough surfaces spread reflections; smooth surfaces produce sharp specular highlights.

PBR shaders consume multiple texture maps, each encoding a distinct physical property. TextureWorks generates six of these maps from a single diffuse/albedo input.

## The Six Maps

### Normal Map

A normal map encodes per-pixel surface orientation as an RGB vector. The red channel stores the X component, green stores Y, and blue stores Z. A flat surface pointing straight up encodes as (128, 128, 255).

Game engines use normal maps to simulate geometric detail without adding polygons. Rivets, panel seams, and surface scratches all produce visual depth through normal mapping. TextureWorks derives normals from luminance gradients using Sobel convolution.

The `strength` parameter controls how dramatic the surface detail appears. Low values (0.5) produce subtle relief. High values (10.0+) create exaggerated, almost embossed effects.

See [Normal Map Algorithm](../algorithms.md#1-normal-map) for the mathematical specification.

### Height Map

A height map encodes perceived surface elevation in grayscale. White pixels represent high points, black pixels represent low points. This is the simplest map conceptually: it answers "how tall is the surface here?"

Engines use height maps for parallax occlusion mapping and tessellation-based displacement. Both techniques create actual geometric depth from a flat polygon. Height maps also serve as input to the ambient occlusion algorithm, where they define the terrain the AO rays march across.

TextureWorks extracts height from luminance, normalizes the range, applies optional Gaussian blur for smoothing, and stretches contrast. The `blur_sigma` parameter controls smoothness, and `contrast` controls the dynamic range of the output.

See [Height Map Algorithm](../algorithms.md#2-height-map) for the mathematical specification.

### Ambient Occlusion (AO)

An AO map approximates how much ambient light reaches each surface point. Crevices, concavities, and tight corners appear dark. Open, exposed areas remain bright (white = fully lit, black = fully occluded).

AO adds depth and grounding to rendered scenes. Without it, objects appear flat and disconnected from their environment. The effect is subtle but its absence is immediately noticeable.

TextureWorks computes AO through screen-space horizon mapping. For each pixel, rays march outward in multiple directions across the height field. The algorithm measures the maximum elevation angle in each direction, averages those angles, and converts the result into an occlusion value. The `height_scale` parameter controls how much the height field influences occlusion depth, and `power` adjusts the contrast curve.

See [AO Algorithm](../algorithms.md#3-ambient-occlusion) for the mathematical specification.

### Roughness Map

A roughness map encodes micro-surface texture variation. White pixels represent rough areas (scattered reflections). Black pixels represent smooth areas (sharp reflections). This map directly controls the width of specular highlights in PBR shaders.

Consider a metal panel with scratches: the scratched regions appear rougher than the polished areas. TextureWorks detects these variations by combining two signals. Local variance captures intensity fluctuation within a neighborhood. Sobel edge magnitude captures sharp transitions. The `alpha` parameter controls the blend between variance and edge signals.

See [Roughness Algorithm](../algorithms.md#4-roughness-map) for the mathematical specification.

### Metallic Map

A metallic map classifies each pixel as metal (white) or dielectric/non-metal (black). PBR shaders treat these two material classes differently: metals tint their reflections with the albedo color, while dielectrics reflect the light color directly.

Most production metallic maps are near-binary. A pixel is either metal or it is not. Transition zones exist mainly at material boundaries. TextureWorks classifies pixels based on HSV saturation and value. Metals tend to be desaturated with moderate-to-high brightness. The `hard_edges` parameter forces a strict binary threshold when soft transitions are not desired.

See [Metallic Algorithm](../algorithms.md#5-metallic-map) for the mathematical specification.

### Specular Map

A specular map encodes per-pixel reflectance intensity. Bright areas reflect more light. This map is used in non-PBR and legacy rendering pipelines, and as a supplementary control in metallic/roughness PBR workflows.

TextureWorks derives specularity from luminance and saturation. High luminance and low saturation both increase the specular score. A power curve and contrast adjustment shape the final distribution. The `sat_weight` parameter controls how much saturation reduction contributes to specularity.

See [Specular Algorithm](../algorithms.md#6-specular-map) for the mathematical specification.

## How Maps Interact in a Shader

PBR shaders combine these maps at render time. Understanding their interaction clarifies why each map matters:

**Normal + Height.** The normal map provides per-pixel lighting variation. The height map adds parallax depth. Together, they create the illusion of 3D surface detail on a flat polygon. Height maps also feed into the AO computation.

**AO + Roughness.** AO darkens crevices. Roughness scatters reflections in those same areas. The combination prevents crevices from showing unrealistic specular highlights while maintaining physically plausible light behavior.

**Metallic + Specular.** The metallic map selects the shading model (metallic vs dielectric). The specular map fine-tunes reflectance intensity within each class. In a pure metallic/roughness workflow, the specular map is optional. In hybrid or legacy pipelines, it provides direct control over reflectivity.

**All maps together.** A PBR shader reads all maps simultaneously for each rendered pixel. The normal map perturbs the surface direction. The roughness map controls reflection spread. The metallic map selects the BRDF model. AO modulates indirect lighting. The combined result is a material with consistent, physically plausible behavior across all lighting conditions.

## Algorithmic vs Artist-Authored Maps

TextureWorks generates maps algorithmically from a diffuse input. This approach has clear strengths and limitations.

**Strengths:**
- Speed. A full set of six maps generates in milliseconds on a GPU, compared to minutes or hours of manual authoring per texture.
- Consistency. The same algorithm produces maps with uniform style across an entire texture library.
- Iteration. Parameter adjustments produce new maps instantly. An artist can explore different roughness or normal strength values without re-painting.

**Limitations:**
- No semantic understanding. The algorithm cannot distinguish a painted bolt from a real bolt. It operates on pixel patterns, not material knowledge.
- Approximation only. Algorithmic normal maps approximate surface orientation from luminance gradients. They cannot capture geometry invisible in the diffuse image.
- Parameter sensitivity. Results depend on input texture style. A photographic texture may need different parameters than a hand-painted or stylized texture.

For production workflows, algorithmic maps often serve as a starting point. Artists refine the output by adjusting parameters or painting over specific regions. The algorithmic baseline eliminates blank-canvas problems and establishes consistent material properties across large texture sets.

## Further Reading

- [Map Type Reference](../reference/map-types.md) for parameter tables and output encoding
- [Architecture](architecture.md) for the dual CuPy/PTX implementation design
- [Algorithm Specifications](../algorithms.md) for the full mathematical definitions
