#ifndef TEXTUREWORKS_MATERIAL_LAYERS_INCLUDED
#define TEXTUREWORKS_MATERIAL_LAYERS_INCLUDED

#include "TextureWorksParallax.hlsl"

// Common composition contract, also implemented by both Python backends.
// A/B share the same white-top reference plane and physical relief depth.
float TextureWorksLayerWeight(float ha, float hb, float mask, float3 controls)
{
    float m = saturate(mask + 2*saturate(controls.x) - 1);
    float score = m + saturate(controls.z)*(hb-ha)*m*(1-m);
    float width = saturate(controls.y);
    if (width <= 0) return score >= .5 ? 1 : 0;
    float t = saturate((score-(.5-width*.5))/width);
    return t*t*(3-2*t);
}

// Return composed height and B weight. Global endpoints also avoid unnecessary
// texture reads. Every ray sample and final channel sample uses this function.
float2 TextureWorksLayerSample(UnityTexture2D a, UnityTexture2D b, UnityTexture2D mask,
    float2 uv, float2 dx, float2 dy, float3 controls)
{
    // One initialized return avoids FXC's false uninitialized-return warning
    // when early returns are inlined inside the dynamic march loops.
    float2 result=float2(0,0);
    if (controls.x <= 0) result=float2(1-TextureWorksParallaxDepth(a,uv,dx,dy),0);
    else if (controls.x >= 1) result=float2(1-TextureWorksParallaxDepth(b,uv,dx,dy),1);
    else
    {
        float ha = 1-TextureWorksParallaxDepth(a,uv,dx,dy);
        float hb = 1-TextureWorksParallaxDepth(b,uv,dx,dy);
        float m = saturate(mask.tex.SampleGrad(mask.samplerstate,uv,dx,dy).r);
        float weight = TextureWorksLayerWeight(ha,hb,m,controls);
        result=float2(lerp(ha,hb,weight),weight);
    }
    return result;
}

// Same march, first crossing, refinement, grazing/distance controls and original
// gradients as TextureWorksParallaxTrace. Only the sampled height function varies.
void TextureWorksLayerTrace(UnityTexture2D a, UnityTexture2D b, UnityTexture2D mask,
    float2 uv, float2 dx, float2 dy, float3 viewDirection, float2 heightScale,
    float minSteps, float maxSteps, float refinementSteps, float viewDistance,
    float fadeStart, float fadeEnd, float3 controls, out float2 resultUV, out float depth)
{
    resultUV = uv; depth = 0;
    float lengthSquared = dot(viewDirection,viewDirection);
    if (lengthSquared < 1e-12) return;
    float3 view = viewDirection*rsqrt(lengthSquared);
    if (view.z <= .02) return;
    float fade = TextureWorksParallaxFade(view.z,viewDistance,fadeStart,fadeEnd);
    float2 scale = max(heightScale,0)*fade;
    if (max(scale.x,scale.y) <= 0) return;
    int maximum = (int)clamp(round(maxSteps),1,128);
    int minimum = (int)clamp(round(minSteps),1,maximum);
    int steps = (int)ceil(lerp((float)maximum,(float)minimum,saturate(view.z)));
    int refinements = (int)clamp(round(refinementSteps),0,8);
    float2 ray = view.xy/view.z*scale;
    float upperDepth = 0, lowerDepth = 0;
    float lowerError = 1-TextureWorksLayerSample(a,b,mask,uv,dx,dy,controls).x;
    if (lowerError <= 0) return;
    float upperError = lowerError;
    [loop] for (int layer = 1; layer <= steps; ++layer)
    {
        upperDepth = (float)layer/steps;
        upperError = 1-TextureWorksLayerSample(a,b,mask,uv-ray*upperDepth,dx,dy,controls).x-upperDepth;
        if (upperError <= 0) break;
        lowerDepth = upperDepth; lowerError = upperError;
    }
    [loop] for (int refinement = 0; refinement < refinements; ++refinement)
    {
        float middle = .5*(lowerDepth+upperDepth);
        float error = 1-TextureWorksLayerSample(a,b,mask,uv-ray*middle,dx,dy,controls).x-middle;
        if (error > 0) { lowerDepth = middle; lowerError = error; }
        else { upperDepth = middle; upperError = error; }
    }
    float denominator = lowerError-upperError;
    float weight = denominator > 1e-8 ? saturate(lowerError/denominator) : .5;
    depth = lerp(lowerDepth,upperDepth,weight);
    resultUV = uv-ray*depth;
}

float3 TextureWorksLayerNormal(UnityTexture2D a, UnityTexture2D b, UnityTexture2D mask,
    float2 uv, float2 dx, float2 dy, float2 heightScale, float3 controls)
{
    float2 texel = min(a.texelSize.xy,min(b.texelSize.xy,mask.texelSize.xy));
    float left = TextureWorksLayerSample(a,b,mask,uv-float2(texel.x,0),dx,dy,controls).x;
    float right = TextureWorksLayerSample(a,b,mask,uv+float2(texel.x,0),dx,dy,controls).x;
    float down = TextureWorksLayerSample(a,b,mask,uv-float2(0,texel.y),dx,dy,controls).x;
    float up = TextureWorksLayerSample(a,b,mask,uv+float2(0,texel.y),dx,dy,controls).x;
    return normalize(float3(float2(left-right,down-up)*heightScale/(2*texel),1));
}

float TextureWorksDetailFade(float distanceToEye, float start, float end)
{
    if (end <= start) return 1; // Explicit convention: disable distance fading.
    float t = saturate((distanceToEye-start)/(end-start));
    return 1-t*t*(3-2*t);
}

// Upper-hemisphere normals. This is the shortest-arc rotation from +Z to base.
// Normalizing after filtering avoids length errors from mipmaps and quantization.
float3 TextureWorksReorientNormal(float3 baseNormal, float3 detailNormal, float strength)
{
    if (strength <= 0) return baseNormal;
    float3 detail = normalize(float3(detailNormal.xy*strength,detailNormal.z));
    float3 t = normalize(baseNormal)+float3(0,0,1);
    float3 u = detail*float3(-1,-1,1);
    return normalize(t*dot(t,u)-u*t.z);
}

float3 TextureWorksDecodeNormal(float3 encoded, float centered, float greenSign)
{
    float3 n = centered > .5 ? (encoded*255-128)/127 : encoded*2-1;
    n.y *= greenSign;
    return normalize(float3(n.xy,max(n.z,1e-4)));
}

#endif
