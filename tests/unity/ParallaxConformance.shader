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
            int _NormalOutput;

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
                if (_NormalOutput != 0)
                {
                    float2 normalUV;
                    float normalDepth, normalInside;
                    float3 normal;
                    TextureWorksParallaxSurface_float(map, uv, _ViewDirection.xyz, scale,
                        _Steps.x, _Steps.y, _Steps.z, _Fade.x, _Fade.y, _Fade.z,
                        normalUV, normalDepth, normalInside, normal);
                    return float4(normal, 1);
                }
                float2 shifted;
                float depth, inside;
                TextureWorksParallax_float(map, uv, _ViewDirection.xyz, scale,
                    _Steps.x, _Steps.y, _Steps.z, _Fade.x, _Fade.y, _Fade.z,
                    shifted, depth, inside);
                return float4(shifted, depth, inside);
            }
            ENDHLSL
        }
    }
}
