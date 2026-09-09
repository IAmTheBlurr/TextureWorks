Shader "TextureWorks/URP/Parallax Lit"
{
    Properties
    {
        [MainTexture] _BaseMap("Albedo (sRGB)", 2D) = "white" {}
        [MainColor] _BaseColor("Tint", Color) = (1,1,1,1)
        _HeightMap("Height (linear, white is top)", 2D) = "white" {}
        _RoughnessMap("Roughness (linear)", 2D) = "white" {}
        _AOMap("Ambient occlusion (linear)", 2D) = "white" {}
        _Metallic("Authored metallic", Range(0,1)) = 0
        _RoughnessMin("Authored minimum roughness", Range(0,1)) = 0
        _DepthMeters("Relief depth in world meters", Range(0,0.15)) = 0.04
        [Enum(Albedo,0,HeightNormal,1,Parallax,2)] _Stage("Demonstration stage", Float) = 2
        _MinSteps("Minimum steps", Range(1,128)) = 16
        _MaxSteps("Maximum steps", Range(1,128)) = 64
        _FadeStart("Fade start (meters)", Float) = 12
        _FadeEnd("Fade end (meters)", Float) = 20
    }
    SubShader
    {
        Tags { "RenderPipeline"="UniversalPipeline" "RenderType"="Opaque" "Queue"="Geometry" }
        HLSLINCLUDE
        #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
        #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
        #include "Packages/com.unity.render-pipelines.core/ShaderLibrary/Texture.hlsl"
        #include "TextureWorksParallax.hlsl"
        CBUFFER_START(UnityPerMaterial)
            float4 _BaseMap_ST;
            half4 _BaseColor;
            float _Metallic, _RoughnessMin, _DepthMeters, _Stage, _MinSteps, _MaxSteps, _FadeStart, _FadeEnd;
        CBUFFER_END
        TEXTURE2D(_BaseMap); SAMPLER(sampler_BaseMap);
        TEXTURE2D(_HeightMap); SAMPLER(sampler_HeightMap); float4 _HeightMap_TexelSize;
        TEXTURE2D(_RoughnessMap); SAMPLER(sampler_RoughnessMap);
        TEXTURE2D(_AOMap); SAMPLER(sampler_AOMap);
        struct Attributes
        {
            float4 positionOS : POSITION;
            float3 normalOS : NORMAL;
            float4 tangentOS : TANGENT;
            float2 uv : TEXCOORD0;
        };
        struct Varyings
        {
            float4 positionCS : SV_POSITION;
            float3 positionWS : TEXCOORD0;
            float3 normalWS : TEXCOORD1;
            float4 tangentWS : TEXCOORD2;
            float2 uv : TEXCOORD3;
            float fog : TEXCOORD4;
        };
        Varyings Vert(Attributes input)
        {
            Varyings o = (Varyings)0;
            VertexPositionInputs p = GetVertexPositionInputs(input.positionOS.xyz);
            VertexNormalInputs n = GetVertexNormalInputs(input.normalOS, input.tangentOS);
            o.positionCS = p.positionCS;
            o.positionWS = p.positionWS;
            o.normalWS = n.normalWS;
            o.tangentWS = float4(n.tangentWS, input.tangentOS.w * GetOddNegativeScale());
            o.uv = TRANSFORM_TEX(input.uv, _BaseMap);
            o.fog = ComputeFogFactor(p.positionCS.z);
            return o;
        }
        ENDHLSL
        Pass
        {
            Name "ForwardLit"
            Tags { "LightMode"="UniversalForwardOnly" }
            HLSLPROGRAM
            #pragma target 4.5
            #pragma vertex Vert
            #pragma fragment Frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
            #pragma multi_compile _ _ADDITIONAL_LIGHTS
            #pragma multi_compile_fragment _ _ADDITIONAL_LIGHT_SHADOWS
            #pragma multi_compile_fragment _ _SHADOWS_SOFT
            #pragma multi_compile_fog
            half4 Frag(Varyings input) : SV_Target
            {
                float2 dx = ddx(input.uv), dy = ddy(input.uv);
                float3 px = ddx(input.positionWS), py = ddy(input.positionWS);
                float determinant = dx.x * dy.y - dx.y * dy.x;
                // Recover meters per final UV unit, including object scale and tiling.
                // This profile requires a valid tangent frame and orthogonal UV axes.
                float2 scale = 0;
                if (abs(determinant) > 1e-12)
                {
                    float3 pu = (px * dy.y - py * dx.y) / determinant;
                    float3 pv = (py * dx.x - px * dy.x) / determinant;
                    scale = _DepthMeters / max(float2(length(pu), length(pv)), 1e-5);
                }
                float3 n = normalize(input.normalWS);
                float3 t = normalize(input.tangentWS.xyz - n * dot(input.tangentWS.xyz, n));
                float3 b = cross(n, t) * input.tangentWS.w;
                float3 view = GetWorldSpaceNormalizeViewDir(input.positionWS);
                float3 viewTS = float3(dot(view,t), dot(view,b), dot(view,n));
                float distanceToEye = distance(_WorldSpaceCameraPos, input.positionWS);
                UnityTexture2D heightMap = UnityBuildTexture2DStructNoScale(_HeightMap);
                float2 uv = input.uv;
                float depth;
                if (_Stage > 1.5)
                    TextureWorksParallaxTrace(heightMap, uv, dx, dy, viewTS, scale,
                        _MinSteps, _MaxSteps, 4, distanceToEye, _FadeStart, _FadeEnd, uv, depth);
                float fade = TextureWorksParallaxFade(viewTS.z, distanceToEye, _FadeStart, _FadeEnd);
                float3 normalTS = _Stage > 0.5
                    ? TextureWorksParallaxNormal(heightMap, uv, dx, dy, scale * fade) : float3(0,0,1);
                SurfaceData surface = (SurfaceData)0;
                surface.albedo = SAMPLE_TEXTURE2D_GRAD(_BaseMap, sampler_BaseMap, uv, dx, dy).rgb * _BaseColor.rgb;
                surface.metallic = _Metallic;
                surface.smoothness = 1 - lerp(_RoughnessMin, 1,
                    SAMPLE_TEXTURE2D_GRAD(_RoughnessMap, sampler_RoughnessMap, uv, dx, dy).r);
                surface.occlusion = SAMPLE_TEXTURE2D_GRAD(_AOMap, sampler_AOMap, uv, dx, dy).r;
                surface.normalTS = normalTS;
                surface.alpha = 1;
                InputData data = (InputData)0;
                data.positionWS = input.positionWS;
                data.normalWS = normalize(t * normalTS.x + b * normalTS.y + n * normalTS.z);
                data.viewDirectionWS = view;
                data.shadowCoord = TransformWorldToShadowCoord(input.positionWS);
                data.bakedGI = SampleSH(data.normalWS);
                data.shadowMask = half4(1,1,1,1);
                data.normalizedScreenSpaceUV = GetNormalizedScreenSpaceUV(input.positionCS);
                half4 color = UniversalFragmentPBR(data, surface);
                color.rgb = MixFog(color.rgb, input.fog);
                return color;
            }
            ENDHLSL
        }
        Pass
        {
            Name "ShadowCaster"
            Tags { "LightMode"="ShadowCaster" }
            ZWrite On ZTest LEqual ColorMask 0
            HLSLPROGRAM
            #pragma vertex ShadowVert
            #pragma fragment ShadowFrag
            #pragma multi_compile_vertex _ _CASTING_PUNCTUAL_LIGHT_SHADOW
            float3 _LightDirection, _LightPosition;
            float4 ShadowVert(Attributes input) : SV_POSITION
            {
                float3 p = TransformObjectToWorld(input.positionOS.xyz);
                float3 n = TransformObjectToWorldNormal(input.normalOS);
                #if defined(_CASTING_PUNCTUAL_LIGHT_SHADOW)
                    float3 direction = normalize(_LightPosition - p);
                #else
                    float3 direction = _LightDirection;
                #endif
                float4 position = TransformWorldToHClip(ApplyShadowBias(p,n,direction));
                #if UNITY_REVERSED_Z
                    position.z = min(position.z, UNITY_NEAR_CLIP_VALUE * position.w);
                #else
                    position.z = max(position.z, UNITY_NEAR_CLIP_VALUE * position.w);
                #endif
                return position;
            }
            half4 ShadowFrag() : SV_Target { return 0; }
            ENDHLSL
        }
        Pass
        {
            Name "DepthOnly"
            Tags { "LightMode"="DepthOnly" }
            ZWrite On ColorMask R
            HLSLPROGRAM
            #pragma vertex Vert
            #pragma fragment DepthFrag
            half DepthFrag(Varyings input) : SV_Target { return input.positionCS.z; }
            ENDHLSL
        }
    }
    FallBack Off
}
