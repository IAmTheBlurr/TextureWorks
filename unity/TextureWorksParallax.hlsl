#ifndef TEXTUREWORKS_PARALLAX_INCLUDED
#define TEXTUREWORKS_PARALLAX_INCLUDED

// Fragment-stage Parallax Occlusion Mapping for Unity Shader Graph (float mode).
// Height R: linear [0, 1], white at the mesh plane, black one slab depth below it.
// ViewDirectionTS points from the surface to the camera; +Z faces the viewer.
// UV is already tiled/offset. HeightScale is the full depth in those UV units.
// Sampling follows HeightMap's sampler wrap mode. No extra _ST transform occurs.
// See docs/how-to/parallax-occlusion-mapping.md for ports and import conventions.

float TextureWorksParallaxDepth(
    UnityTexture2D HeightMap, float2 UV, float2 UVdx, float2 UVdy)
{
    // Explicit gradients stay defined inside divergent march/refinement loops.
    return 1.0 - saturate(HeightMap.tex.SampleGrad(
        HeightMap.samplerstate, UV, UVdx, UVdy).r);
}

float TextureWorksParallaxFade(float ViewZ, float ViewDistance, float FadeStart, float FadeEnd)
{
    float fade = FadeEnd > FadeStart
        ? 1.0 - saturate((ViewDistance - FadeStart) / (FadeEnd - FadeStart))
        : 1.0;
    return fade * smoothstep(0.02, 0.10, ViewZ);
}

// Explicit gradients also allow the same trace to be exercised by GPU tests.
void TextureWorksParallaxTrace(
    UnityTexture2D HeightMap, float2 UV, float2 UVdx, float2 UVdy,
    float3 ViewDirectionTS, float2 HeightScale, float MinSteps, float MaxSteps,
    float RefinementSteps, float ViewDistance, float FadeStart, float FadeEnd,
    out float2 ParallaxUV, out float Depth)
{
    ParallaxUV = UV;
    Depth = 0.0;
    float lengthSquared = dot(ViewDirectionTS, ViewDirectionTS);
    if (lengthSquared < 1e-12)
        return;

    float3 view = ViewDirectionTS * rsqrt(lengthSquared);
    // Suppress grazing/back-facing rays before dividing by the view's Z value.
    if (view.z <= 0.02)
        return;

    // Equal/reversed fade bounds disable distance fading.
    float fade = TextureWorksParallaxFade(view.z, ViewDistance, FadeStart, FadeEnd);
    float2 scale = max(HeightScale, 0.0) * fade;
    if (max(scale.x, scale.y) <= 0.0)
        return;

    int maximum = (int)clamp(round(MaxSteps), 1.0, 128.0);
    int minimum = (int)clamp(round(MinSteps), 1.0, (float)maximum);
    int steps = (int)ceil(lerp((float)maximum, (float)minimum, saturate(view.z)));
    int refinements = (int)clamp(round(RefinementSteps), 0.0, 8.0);
    float2 ray = view.xy / view.z * scale;

    float upperDepth = 0.0;
    float lowerDepth = 0.0;
    float lowerError = TextureWorksParallaxDepth(HeightMap, UV, UVdx, UVdy);
    if (lowerError <= 0.0)
        return; // The ray starts on the white/top surface.
    float upperError = lowerError;

    // Find the first sampled crossing. Thin features between steps can be missed;
    // refinement improves a bracketed intersection, not the initial search.
    [loop]
    for (int layer = 1; layer <= steps; ++layer)
    {
        upperDepth = (float)layer / (float)steps;
        upperError = TextureWorksParallaxDepth(
            HeightMap, UV - ray * upperDepth, UVdx, UVdy) - upperDepth;
        if (upperError <= 0.0)
            break;
        lowerDepth = upperDepth;
        lowerError = upperError;
    }

    [loop]
    for (int refinement = 0; refinement < refinements; ++refinement)
    {
        float middle = 0.5 * (lowerDepth + upperDepth);
        float error = TextureWorksParallaxDepth(
            HeightMap, UV - ray * middle, UVdx, UVdy) - middle;
        if (error > 0.0)
        {
            lowerDepth = middle;
            lowerError = error;
        }
        else
        {
            upperDepth = middle;
            upperError = error;
        }
    }

    // Linear interpolation of the final signed errors is exact for a flat plane
    // or linear ramp and remains inside the refined crossing interval.
    float denominator = lowerError - upperError;
    float weight = denominator > 1e-8 ? saturate(lowerError / denominator) : 0.5;
    Depth = lerp(lowerDepth, upperDepth, weight);
    ParallaxUV = UV - ray * Depth;
}

void TextureWorksParallax_float(
    UnityTexture2D HeightMap, float2 UV, float3 ViewDirectionTS,
    float2 HeightScale, float MinSteps, float MaxSteps, float RefinementSteps,
    float ViewDistance, float FadeStart, float FadeEnd,
    out float2 ParallaxUV, out float Depth, out float InBounds)
{
    // Evaluate derivatives before any per-fragment branching.
    float2 UVdx = ddx(UV);
    float2 UVdy = ddy(UV);
    TextureWorksParallaxTrace(
        HeightMap, UV, UVdx, UVdy, ViewDirectionTS, HeightScale,
        MinSteps, MaxSteps, RefinementSteps, ViewDistance, FadeStart, FadeEnd,
        ParallaxUV, Depth);
    InBounds = all(ParallaxUV >= 0.0) && all(ParallaxUV <= 1.0) ? 1.0 : 0.0;
}

// Central differences of the SAME sampled field, scaled in tangent/UV units.
// Original UV gradients preserve the height filtering used by the ray trace.
float3 TextureWorksParallaxNormal(
    UnityTexture2D HeightMap, float2 UV, float2 UVdx, float2 UVdy, float2 HeightScale)
{
    if (max(HeightScale.x, HeightScale.y) <= 0.0)
        return float3(0, 0, 1);
    float2 texel = HeightMap.texelSize.xy;
    float left = TextureWorksParallaxDepth(HeightMap, UV - float2(texel.x, 0), UVdx, UVdy);
    float right = TextureWorksParallaxDepth(HeightMap, UV + float2(texel.x, 0), UVdx, UVdy);
    float down = TextureWorksParallaxDepth(HeightMap, UV - float2(0, texel.y), UVdx, UVdy);
    float up = TextureWorksParallaxDepth(HeightMap, UV + float2(0, texel.y), UVdx, UVdy);
    return normalize(float3(float2(right - left, up - down) * HeightScale / (2.0 * texel), 1));
}

// Optional convenience node: coherent lighting normals including both fades.
// The original UV-only entry point remains available for authored normal maps.
void TextureWorksParallaxSurface_float(
    UnityTexture2D HeightMap, float2 UV, float3 ViewDirectionTS,
    float2 HeightScale, float MinSteps, float MaxSteps, float RefinementSteps,
    float ViewDistance, float FadeStart, float FadeEnd,
    out float2 ParallaxUV, out float Depth, out float InBounds, out float3 NormalTS)
{
    float2 UVdx = ddx(UV), UVdy = ddy(UV);
    TextureWorksParallaxTrace(HeightMap, UV, UVdx, UVdy, ViewDirectionTS, HeightScale,
        MinSteps, MaxSteps, RefinementSteps, ViewDistance, FadeStart, FadeEnd,
        ParallaxUV, Depth);
    InBounds = all(ParallaxUV >= 0.0) && all(ParallaxUV <= 1.0) ? 1.0 : 0.0;
    float lengthSquared = dot(ViewDirectionTS, ViewDirectionTS);
    float viewZ = lengthSquared >= 1e-12 ? ViewDirectionTS.z * rsqrt(lengthSquared) : 0.0;
    float2 scale = max(HeightScale, 0.0)
        * TextureWorksParallaxFade(viewZ, ViewDistance, FadeStart, FadeEnd);
    NormalTS = TextureWorksParallaxNormal(HeightMap, ParallaxUV, UVdx, UVdy, scale);
}

#endif
