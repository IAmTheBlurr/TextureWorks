Shader "Hidden/TextureWorks/ParallaxConformance"
{
    SubShader
    {
        Pass
        {
            ZTest Always ZWrite Off Cull Off
            HLSLPROGRAM
            #pragma target 4.5
            #pragma vertex Vert
            #pragma fragment Frag
            #include "Packages/com.unity.render-pipelines.core/ShaderLibrary/Common.hlsl"
            #include "Packages/com.unity.render-pipelines.core/ShaderLibrary/Texture.hlsl"
            #include "../TextureWorksParallax.hlsl"

            TEXTURE2D(_HeightMap);
            SAMPLER(sampler_HeightMap);
            float4 _HeightMap_TexelSize;
            float4 _TestUV;
            float4 _ViewDirection;
            float4 _HeightScale;
            float4 _Steps; // minimum, maximum, refinements
            float4 _Fade; // distance, start, end
            int _Preview;

            struct Varyings { float4 position : SV_POSITION; float2 uv : TEXCOORD0; };
            Varyings Vert(uint id : SV_VertexID)
            {
                Varyings output;
                output.uv = float2((id << 1) & 2, id & 2);
                output.position = float4(output.uv * 2.0 - 1.0, 0.0, 1.0);
                return output;
            }

            float4 Frag(Varyings input) : SV_Target
            {
                UnityTexture2D map = UnityBuildTexture2DStructInternal(
                    TEXTURE2D_ARGS(_HeightMap, sampler_HeightMap),
                    _HeightMap_TexelSize, float4(1, 1, 0, 0));
                float2 uv = _TestUV.xy;
                float2 scale = _HeightScale.xy;
                if (_Preview != 0)
                {
                    uv = float2(frac(input.uv.x * 2.0), input.uv.y);
                    if (input.uv.x < 0.5) scale = 0.0;
                }
                float2 shifted;
                float depth, inside;
                TextureWorksParallax_float(map, uv, _ViewDirection.xyz, scale,
                    _Steps.x, _Steps.y, _Steps.z, _Fade.x, _Fade.y, _Fade.z,
                    shifted, depth, inside);
                if (_Preview == 0) return float4(shifted, depth, inside);

                // Diagnostic surface: identical lighting, with ray correction on
                // the right. Use the same displaced coordinate for every sample.
                float2 delta = _HeightMap_TexelSize.xy;
                float2 dx = ddx(uv), dy = ddy(uv);
                float h = map.tex.SampleGrad(map.samplerstate, shifted, dx, dy).r;
                float hx = map.tex.SampleGrad(map.samplerstate, shifted + float2(delta.x, 0), dx, dy).r;
                float hy = map.tex.SampleGrad(map.samplerstate, shifted + float2(0, delta.y), dx, dy).r;
                float3 normal = normalize(float3((h - hx) * 8, (h - hy) * 8, 1));
                float light = 0.2 + 0.8 * saturate(dot(normal, normalize(float3(-0.6, 0.4, 0.7))));
                float3 albedo = lerp(float3(0.04, 0.06, 0.08), float3(0.45, 0.63, 0.72), h);
                return float4(albedo * light, 1);
            }
            ENDHLSL
        }
    }
}
