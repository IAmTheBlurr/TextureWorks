Shader "Hidden/TextureWorks/ParallaxGeometry"
{
    SubShader
    {
        Pass
        {
            ZTest LEqual ZWrite On Cull Off
            HLSLPROGRAM
            #pragma target 4.5
            #pragma vertex Vert
            #pragma fragment Frag
            #include "Packages/com.unity.render-pipelines.core/ShaderLibrary/Common.hlsl"
            #include "Packages/com.unity.render-pipelines.core/ShaderLibrary/Texture.hlsl"
            #include "../TextureWorksParallax.hlsl"

            TEXTURE2D(_HeightMap); SAMPLER(sampler_HeightMap);
            TEXTURE2D(_Albedo); SAMPLER(sampler_Albedo);
            float4 _HeightMap_TexelSize;
            float4x4 _ObjectToClip;
            float3 _CameraPosition;
            float _DepthWorld, _PlaneSize, _MinSteps, _MaxSteps;
            int _Mode, _Diagnostic;
            struct Attributes { float3 position : POSITION; float2 uv : TEXCOORD0; };
            struct Varyings { float4 position : SV_POSITION; float3 objectPosition : TEXCOORD0; float2 uv : TEXCOORD1; };
            Varyings Vert(Attributes input)
            {
                Varyings o;
                o.position = mul(_ObjectToClip, float4(input.position, 1));
                o.objectPosition = input.position;
                o.uv = input.uv;
                return o;
            }
            float4 Frag(Varyings input) : SV_Target
            {
                UnityTexture2D map = UnityBuildTexture2DStructNoScale(_HeightMap);
                float2 uv = input.uv;
                float2 dx = ddx(uv), dy = ddy(uv);
                float3 n = float3(0, 0, 1);
                if (_Mode == 1)
                {
                    float depth, inside;
                    TextureWorksParallaxSurface_float(map, uv,
                        _CameraPosition - input.objectPosition, _DepthWorld / _PlaneSize,
                        _MinSteps, _MaxSteps, 6, 0, 0, 0, uv, depth, inside, n);
                    clip(min(min(uv.x, uv.y), min(1 - uv.x, 1 - uv.y)));
                }
                if (_Diagnostic != 0) return float4(uv, 0, 1);

                // Match the geometric height field in world units. Normals use
                // the SAME height and UV as the ray, including its blur/contrast.
                if (_Mode != 1)
                {
                    float2 texel = _HeightMap_TexelSize.xy;
                    float left = map.tex.SampleLevel(map.samplerstate, uv - float2(texel.x, 0), 0).r;
                    float right = map.tex.SampleLevel(map.samplerstate, uv + float2(texel.x, 0), 0).r;
                    float down = map.tex.SampleLevel(map.samplerstate, uv - float2(0, texel.y), 0).r;
                    float up = map.tex.SampleLevel(map.samplerstate, uv + float2(0, texel.y), 0).r;
                    n = normalize(float3(-(right-left) / (2*texel.x) * _DepthWorld / _PlaneSize,
                                          -(up-down) / (2*texel.y) * _DepthWorld / _PlaneSize, 1));
                }
                float light = .22 + .78 * saturate(dot(n, normalize(float3(-.5, .7, 1))));
                float3 color = SAMPLE_TEXTURE2D_GRAD(_Albedo, sampler_Albedo, uv, dx, dy).rgb;
                return float4(pow(saturate(color * light), 1.0 / 2.2), 1);
            }
            ENDHLSL
        }
    }
}
