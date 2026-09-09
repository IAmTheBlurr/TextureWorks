# Parallax Occlusion Mapping contract

The runtime implementation is
[`TextureWorksParallax.hlsl`](../../unity/TextureWorksParallax.hlsl).
The [integration guide](../how-to/parallax-occlusion-mapping.md) defines its ports.

## Height field and ray

Let `H(u)` be the filtered, linear red-channel height at UV `u`, clamped to `[0, 1]`.
White is the top plane, coincident with the mesh; black is the bottom of a virtual
slab. Surface depth is `D(u) = 1 - H(u)`. This convention recesses the virtual
surface below the mesh plane. It introduces no additional normalization of the
generated height field and makes no assumption that the source contains every
height value.

Normalize the supplied tangent-space surface-to-camera vector `v`. Its Z component
must be positive. The ray into the slab travels opposite the camera's XY direction:

```text
ray = (v.xy / v.z) * max(HeightScale, 0) * distanceFade * angularFade
u(t) = UV - ray * t,  0 <= t <= 1
intersection: t = D(u(t))
```

`HeightScale` is a two-component depth in the final UV units. Normal incidence
leaves UV unchanged. On a constant height `h`, the solution is `t = 1 - h` and
`u = UV - ray * (1 - h)`. The Unity tests use this and the analytic solution for
a linear ramp to verify the sign, scale, and intersection.

## Search and refinement

The implementation rounds `MinSteps` and `MaxSteps` to integers in `[1, 128]`,
limiting the minimum to the maximum. Its actual count is
`ceil(lerp(MaxSteps, MinSteps, saturate(v.z)))`. Refinement is rounded and clamped
to `[0, 8]`.

Evaluate `e(t) = D(u(t)) - t` at the top and then at evenly spaced depth samples.
Stop at the first sampled `e(t) <= 0`. This brackets a crossing between the
preceding sample and the current one. At the bottom, `D <= 1` guarantees a
nonpositive error. If the top is white, the initial intersection is already zero.

Bisect the interval for the requested refinements, preserving a positive lower
error and a nonpositive upper error. Interpolate the remaining errors to choose
the returned depth inside that interval. A nearly zero denominator uses the
interval midpoint. This interpolation is exact for a constant or linear field
within the final interval. Narrow features can still fall between march samples;
refinement cannot recover an intersection that the initial search missed.

Height samples use `SampleGrad` with derivatives evaluated from the incoming UV
before any branch. The same gradients are used throughout the trace. Wrap mode
comes from the supplied sampler. Inputs must be finite. The function is evaluated
in float precision in the fragment stage.

## Fades and bypasses

If `FadeEnd > FadeStart`, distance fade is
`1 - saturate((ViewDistance - FadeStart) / (FadeEnd - FadeStart))`; otherwise it
is `1`. Angular fade is `smoothstep(0.02, 0.10, v.z)`.

The trace returns the original UV with depth zero for a view vector whose squared
length is below `1e-12`, normalized `v.z <= 0.02`, or nonpositive effective scale
in both dimensions. The last condition covers zero depth and completed distance
fading. These paths avoid height texture reads.

`InBounds` tests the final UV against the closed unit square. It is an optional
mask for a single UV square; it is not a validity test for repeated textures or
an atlas-aware intersection test. No fragment is discarded internally.

## Height-derived normal

`TextureWorksParallaxSurface_float` has the same inputs and UV/depth outputs as
`TextureWorksParallax_float`, plus a normalized tangent-space `NormalTS` output.
At the returned UV, it takes central differences of `D = 1 - H` one texel to
either side on each axis, using the trace's original UV gradients:

```text
dDdu = (D(u + texelU) - D(u - texelU)) / (2 * texelU)
dDdv = (D(u + texelV) - D(u - texelV)) / (2 * texelV)
scale = max(HeightScale, 0) * distanceFade * angularFade
NormalTS = normalize((dDdu * scale.x, dDdv * scale.y, 1))
```

The finite difference smooths slopes over a two-texel span. The physical tangent
frame and UV-density assumptions are the same as the ray's. Invalid/back-facing
views and zero effective relief produce `(0, 0, 1)` without normal texture reads.
The surface variant adds four height samples when relief is active. It retains
the sampler's filtering; filtering can change the effective height field.

## Validation boundary

The Python suite checks file precision, loading, and both generation backends.
The Unity harness renders the shipped HLSL with the actual SRP texture structures
and verifies known fields, adjacent R16 codes, sampler modes, bypasses, and control
limits. It also compares 40 perspective renders across four generated materials,
five camera angles and two quality settings against a dense displaced mesh, plus
100 frames during a camera sweep. UV
errors use the shared interior; silhouette differences are reported separately.
Normals have analytic slope/fade tests, and camera sweeps provide visual evidence.
See the [validation method](../dev/parallax-validation.md).

The trace is a runtime shader, not a seventh static texture generator;
the existing CuPy/PTX height pair supplies its offline input.

Shader Graph material wiring, target builds, production filtering, frame cost, and
scene-specific depth/shadow behavior need acceptance in the consuming project.
