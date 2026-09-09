Shader "Hidden/TextureWorks/ClusterConformance"
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
            #include "Packages/com.textureworks.materials/TextureWorksMaterialLayers.hlsl"
            TEXTURE2D(_A); SAMPLER(sampler_A); float4 _A_TexelSize;
            TEXTURE2D(_B); SAMPLER(sampler_B); float4 _B_TexelSize;
            TEXTURE2D(_Mask); SAMPLER(sampler_Mask); float4 _Mask_TexelSize;
            float4 _Base,_Detail,_UV,_View,_Scale,_Steps,_Fade,_Controls;
            float _Strength; int _Mode;
            struct Varyings { float4 position:SV_POSITION; };
            Varyings Vert(uint id:SV_VertexID)
            {
                Varyings o; float2 uv=float2((id<<1)&2,id&2); o.position=float4(uv*2-1,0,1); return o;
            }
            float4 Frag(Varyings input):SV_Target
            {
                if(_Mode==0) return float4(TextureWorksReorientNormal(_Base.xyz,_Detail.xyz,_Strength),1);
                if(_Mode==1) return TextureWorksDetailFade(_Fade.x,_Fade.y,_Fade.z).xxxx;
                if(_Mode==2) return TextureWorksLayerWeight(_Base.x,_Detail.x,_UV.x,_Controls.xyz).xxxx;
                UnityTexture2D a=UnityBuildTexture2DStructNoScale(_A);
                UnityTexture2D b=UnityBuildTexture2DStructNoScale(_B);
                UnityTexture2D m=UnityBuildTexture2DStructNoScale(_Mask);
                float2 dx=_UV.zw,dy=float2(0,_UV.w);
                if(_Mode==4) return float4(TextureWorksLayerNormal(a,b,m,_UV.xy,dx,dy,_Scale.xy,_Controls.xyz),1);
                if(_Mode==5) return float4(TextureWorksLayerSample(a,b,m,_UV.xy,dx,dy,_Controls.xyz),0,1);
                float2 uv; float depth;
                if(_Mode==6)
                    TextureWorksParallaxTrace(a,_UV.xy,dx,dy,_View.xyz,_Scale.xy,_Steps.x,_Steps.y,_Steps.z,
                        _Fade.x,_Fade.y,_Fade.z,uv,depth);
                else
                    TextureWorksLayerTrace(a,b,m,_UV.xy,dx,dy,_View.xyz,_Scale.xy,_Steps.x,_Steps.y,_Steps.z,
                        _Fade.x,_Fade.y,_Fade.z,_Controls.xyz,uv,depth);
                return float4(uv,depth,1);
            }
            ENDHLSL
        }
    }
}
