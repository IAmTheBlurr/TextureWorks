Shader "TextureWorks/URP/Layered Lit"
{
    Properties
    {
        [MainTexture] _BaseMapA("A albedo",2D)="white"{}
        _BaseMapB("B albedo",2D)="white"{}
        _HeightA("A height (linear R16)",2D)="white"{}
        _HeightB("B height (linear R16)",2D)="white"{}
        _NormalA("A normal (linear RGB XYZ)",2D)="bump"{}
        _NormalB("B normal (linear RGB XYZ)",2D)="bump"{}
        _RoughnessA("A roughness",2D)="white"{}
        _RoughnessB("B roughness",2D)="white"{}
        _MetallicA("A metallic",2D)="black"{}
        _MetallicB("B metallic",2D)="black"{}
        _AOA("A AO",2D)="white"{}
        _AOB("B AO",2D)="white"{}
        _Mask("B coverage mask",2D)="black"{}
        _Edge("Edge chipping",2D)="black"{}
        _Cavity("Cavity grime",2D)="black"{}
        _Curvature("Signed curvature, neutral 0.5",2D)="gray"{}
        _DetailColor("Linear residual, neutral byte 128",2D)="gray"{}
        _DetailNormal("Detail XYZ centered normal",2D)="bump"{}
        _Coverage("Coverage: all A to all B",Range(0,1))=.5
        _BlendWidth("Transition width (zero = hard)",Range(0,1))=.2
        _HeightBias("Height influence on coverage",Range(0,1))=.5
        _DepthMeters("Common relief depth in meters",Float)=.04
        _TextureSize("Texture size in meters (XY)",Vector)=(1,1,0,0)
        _DetailSize("Detail source size in meters (XY)",Vector)=(1,1,0,0)
        _DetailTiling("Detail tiling",Range(.01,128))=4
        _DetailColorStrength("Detail color strength",Range(0,2))=.35
        _DetailNormalStrength("Detail normal strength",Range(0,4))=.5
        _DetailRoughness("Detail roughness modulation",Range(0,1))=.1
        _DetailFadeStart("Detail fade start (meters)",Float)=3
        _DetailFadeEnd("Detail fade end (meters)",Float)=8
        _FadeStart("POM fade start (meters)",Float)=12
        _FadeEnd("POM fade end (meters)",Float)=20
        [Enum(Low,0,Balanced,1,High,2)] _Quality("POM quality",Float)=1
        [Enum(Base,0,Normal,1,POM,2,Detail,3,WearMasks,4,Layers,5)] _Stage("Stage",Float)=5
        [Enum(TextureWorks.Editor.MaterialDebugView)] _Debug("Debug view",Float)=0
        [HideInInspector] _NormalEncoding("Centered A/B, green sign A/B",Vector)=(1,1,1,1)
        [HideInInspector] _AuthoredNormals("Authored normals A/B",Vector)=(0,0,0,0)
    }
    SubShader
    {
        Tags { "RenderPipeline"="UniversalPipeline" "RenderType"="Opaque" "Queue"="Geometry" }
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
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            #include "Packages/com.unity.render-pipelines.core/ShaderLibrary/Texture.hlsl"
            #include "TextureWorksMaterialLayers.hlsl"
            CBUFFER_START(UnityPerMaterial)
                float4 _BaseMapA_ST, _TextureSize, _DetailSize, _NormalEncoding, _AuthoredNormals;
                float _Coverage,_BlendWidth,_HeightBias,_DepthMeters,_DetailTiling;
                float _DetailColorStrength,_DetailNormalStrength,_DetailRoughness,_DetailFadeStart,_DetailFadeEnd;
                float _FadeStart,_FadeEnd,_Quality,_Stage,_Debug;
            CBUFFER_END
            // Material fields share enforced wrap/filter settings. Detail has an
            // independent sampler so a clamped cabinet can repeat microdetail.
            TEXTURE2D(_BaseMapA); SAMPLER(sampler_BaseMapA); TEXTURE2D(_BaseMapB);
            TEXTURE2D(_HeightA); float4 _HeightA_TexelSize;
            TEXTURE2D(_HeightB); float4 _HeightB_TexelSize;
            TEXTURE2D(_Mask); float4 _Mask_TexelSize;
            TEXTURE2D(_NormalA); TEXTURE2D(_NormalB);
            TEXTURE2D(_RoughnessA); TEXTURE2D(_RoughnessB);
            TEXTURE2D(_MetallicA); TEXTURE2D(_MetallicB);
            TEXTURE2D(_AOA); TEXTURE2D(_AOB);
            TEXTURE2D(_DetailColor); SAMPLER(sampler_DetailColor); TEXTURE2D(_DetailNormal);
            TEXTURE2D(_Edge); TEXTURE2D(_Cavity); TEXTURE2D(_Curvature);
            #define sampler_HeightA sampler_BaseMapA
            #define sampler_HeightB sampler_BaseMapA
            #define sampler_Mask sampler_BaseMapA
            #define TW_SAMPLE(tex) SAMPLE_TEXTURE2D_GRAD(tex,sampler_BaseMapA,uv,dx,dy)
            struct Attributes { float4 positionOS:POSITION; float3 normalOS:NORMAL; float4 tangentOS:TANGENT; float2 uv:TEXCOORD0; };
            struct Varyings { float4 positionCS:SV_POSITION; float3 positionWS:TEXCOORD0; float3 normalWS:TEXCOORD1; float4 tangentWS:TEXCOORD2; float2 uv:TEXCOORD3; float fog:TEXCOORD4; };
            Varyings Vert(Attributes input)
            {
                Varyings o=(Varyings)0;
                VertexPositionInputs p=GetVertexPositionInputs(input.positionOS.xyz);
                VertexNormalInputs n=GetVertexNormalInputs(input.normalOS,input.tangentOS);
                o.positionCS=p.positionCS; o.positionWS=p.positionWS; o.normalWS=n.normalWS;
                o.tangentWS=float4(n.tangentWS,input.tangentOS.w*GetOddNegativeScale());
                o.uv=TRANSFORM_TEX(input.uv,_BaseMapA); o.fog=ComputeFogFactor(p.positionCS.z); return o;
            }
            half4 Frag(Varyings input):SV_Target
            {
                float2 dx=ddx(input.uv),dy=ddy(input.uv);
                float3 px=ddx(input.positionWS),py=ddy(input.positionWS);
                float determinant=dx.x*dy.y-dx.y*dy.x;
                float2 metersPerUV=1e8;
                if(abs(determinant)>1e-12)
                {
                    float3 pu=(px*dy.y-py*dx.y)/determinant;
                    float3 pv=(py*dx.x-px*dy.x)/determinant;
                    metersPerUV=max(float2(length(pu),length(pv)),1e-5);
                }
                float2 scale=max(_DepthMeters,0)/metersPerUV;
                float3 n=normalize(input.normalWS);
                float3 t=normalize(input.tangentWS.xyz-n*dot(input.tangentWS.xyz,n));
                float3 b=cross(n,t)*input.tangentWS.w;
                float3 view=GetWorldSpaceNormalizeViewDir(input.positionWS);
                float3 viewTS=float3(dot(view,t),dot(view,b),dot(view,n));
                float distanceToEye=distance(_WorldSpaceCameraPos,input.positionWS);
                // Version-aware Unity texture constructors, with a common sampler.
                UnityTexture2D ha=UnityBuildTexture2DStructNoScale(_HeightA);
                UnityTexture2D hb=UnityBuildTexture2DStructNoScale(_HeightB);
                UnityTexture2D mask=UnityBuildTexture2DStructNoScale(_Mask);
                float3 controls=float3(_Stage>4.5 ? _Coverage : 0,_BlendWidth,_HeightBias);
                float2 uv=input.uv; float depth=0;
                float3 quality=_Quality<.5 ? float3(8,24,2) : _Quality>1.5 ? float3(32,128,6) : float3(16,64,4);
                if(_Stage>1.5)
                {
                    float2 shiftedUV;
                    TextureWorksLayerTrace(ha,hb,mask,uv,dx,dy,viewTS,scale,quality.x,quality.y,quality.z,
                        distanceToEye,_FadeStart,_FadeEnd,controls,shiftedUV,depth);
                    uv=shiftedUV;
                }
                float2 sample=TextureWorksLayerSample(ha,hb,mask,uv,dx,dy,controls);
                float weight=sample.y;
                float fade=TextureWorksParallaxFade(viewTS.z,distanceToEye,_FadeStart,_FadeEnd);
                float3 normalTS=float3(0,0,1);
                if(_Stage>.5)
                {
                    normalTS=TextureWorksLayerNormal(ha,hb,mask,uv,dx,dy,scale,controls);
                    float2 slopes=normalTS.xy/max(normalTS.z,1e-4);
                    // Transition authored slope residuals on the geometric composition.
                    // Its weight derivative is already present in LayerNormal.
                    if(_AuthoredNormals.x>.5 || _AuthoredNormals.y>.5)
                    {
                        float3 ga=TextureWorksParallaxNormal(ha,uv,dx,dy,scale);
                        float3 gb=TextureWorksParallaxNormal(hb,uv,dx,dy,scale);
                        float3 na=TextureWorksDecodeNormal(TW_SAMPLE(_NormalA).rgb,_NormalEncoding.x,_NormalEncoding.z);
                        float3 nb=TextureWorksDecodeNormal(TW_SAMPLE(_NormalB).rgb,_NormalEncoding.y,_NormalEncoding.w);
                        float2 ra=(na.xy/na.z*_TextureSize.xy/metersPerUV-ga.xy/ga.z)*_AuthoredNormals.x;
                        float2 rb=(nb.xy/nb.z*_TextureSize.xy/metersPerUV-gb.xy/gb.z)*_AuthoredNormals.y;
                        slopes+=lerp(ra,rb,weight);
                    }
                    normalTS=normalize(float3(slopes*fade,1));
                }
                float3 albedo=lerp(TW_SAMPLE(_BaseMapA).rgb,TW_SAMPLE(_BaseMapB).rgb,weight);
                float roughness=lerp(TW_SAMPLE(_RoughnessA).r,TW_SAMPLE(_RoughnessB).r,weight);
                float metallic=lerp(TW_SAMPLE(_MetallicA).r,TW_SAMPLE(_MetallicB).r,weight);
                float ao=lerp(TW_SAMPLE(_AOA).r,TW_SAMPLE(_AOB).r,weight);
                float detailFade=_Stage>2.5 ? TextureWorksDetailFade(distanceToEye,_DetailFadeStart,_DetailFadeEnd) : 0;
                if(detailFade>0 && max(_DetailColorStrength,max(_DetailNormalStrength,_DetailRoughness))>0)
                {
                    float tiling=max(_DetailTiling,.01);
                    float2 detailUV=uv*tiling,ddxUV=dx*tiling,ddyUV=dy*tiling;
                    float3 residual=(SAMPLE_TEXTURE2D_GRAD(_DetailColor,sampler_DetailColor,detailUV,ddxUV,ddyUV).rgb*255-128)/127;
                    albedo=saturate(albedo+residual*max(_DetailColorStrength,0)*detailFade);
                    roughness=saturate(roughness+dot(residual,float3(.2126,.7152,.0722))*max(_DetailRoughness,0)*detailFade);
                    float3 dn=TextureWorksDecodeNormal(SAMPLE_TEXTURE2D_GRAD(_DetailNormal,sampler_DetailColor,detailUV,ddxUV,ddyUV).rgb,1,1);
                    dn=normalize(float3(dn.xy*_DetailSize.xy*tiling/metersPerUV,dn.z));
                    normalTS=TextureWorksReorientNormal(normalTS,dn,max(_DetailNormalStrength,0)*detailFade);
                }
                if(_Stage>3.5 && _Stage<4.5)
                    return half4(TW_SAMPLE(_Edge).r,TW_SAMPLE(_Cavity).r,TW_SAMPLE(_Curvature).r,1);
                if(_Debug>.5)
                {
                    float3 value=sample.xxx;
                    if(_Debug>1.5) value=TW_SAMPLE(_Mask).rrr;
                    if(_Debug>2.5) value=TW_SAMPLE(_Curvature).rrr;
                    if(_Debug>3.5) value=TW_SAMPLE(_Edge).rrr;
                    if(_Debug>4.5) value=TW_SAMPLE(_Cavity).rrr;
                    if(_Debug>5.5) value=weight.xxx;
                    if(_Debug>6.5) value=normalTS*.5+.5;
                    if(_Debug>7.5) value=albedo;
                    if(_Debug>8.5) value=roughness.xxx;
                    if(_Debug>9.5) value=metallic.xxx;
                    if(_Debug>10.5) value=ao.xxx;
                    return half4(value,1);
                }
                SurfaceData surface=(SurfaceData)0;
                surface.albedo=albedo; surface.metallic=metallic; surface.smoothness=1-roughness;
                surface.occlusion=ao; surface.normalTS=normalTS; surface.alpha=1;
                InputData data=(InputData)0;
                data.positionWS=input.positionWS; data.normalWS=normalize(t*normalTS.x+b*normalTS.y+n*normalTS.z);
                data.viewDirectionWS=view; data.shadowCoord=TransformWorldToShadowCoord(input.positionWS);
                data.bakedGI=SampleSH(data.normalWS); data.shadowMask=half4(1,1,1,1);
                data.normalizedScreenSpaceUV=GetNormalizedScreenSpaceUV(input.positionCS);
                half4 color=UniversalFragmentPBR(data,surface); color.rgb=MixFog(color.rgb,input.fog); return color;
            }
            ENDHLSL
        }
        UsePass "TextureWorks/URP/Parallax Lit/ShadowCaster"
        UsePass "TextureWorks/URP/Parallax Lit/DepthOnly"
    }
    FallBack Off
}
