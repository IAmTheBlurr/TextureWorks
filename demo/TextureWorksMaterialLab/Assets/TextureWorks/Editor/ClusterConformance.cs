using System;
using System.Collections.Generic;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace TextureWorks.MaterialLab.Editor
{
    /// <summary>Independent analytic references for the actual shipped HLSL.</summary>
    public static class ClusterConformance
    {
        private static Material material;
        private static List<string> checks;
        private static readonly List<Texture2D> allocated = new List<Texture2D>();
        private static void Check(bool condition,string message)
        { if(!condition) throw new InvalidOperationException("Cluster GPU: "+message); checks.Add(message); }
        private static void Near(Color actual,Color expected,string name,float tolerance=3e-5f)
        {
            for(int c=0;c<4;++c)
                if(float.IsNaN(actual[c]) || float.IsInfinity(actual[c]) || Mathf.Abs(actual[c]-expected[c])>tolerance)
                    throw new InvalidOperationException($"Cluster GPU {name}: expected {expected}, got {actual}, tolerance {tolerance}");
            checks.Add(name);
        }
        private static Color ColorOf(Vector3 v) => new Color(v.x,v.y,v.z,1);
        private static Texture2D Field(Func<float,float,float> value,int width=257,int height=129)
        {
            var texture=new Texture2D(width,height,TextureFormat.RFloat,false,true);
            var pixels=new Color[width*height];
            for(int y=0;y<height;++y) for(int x=0;x<width;++x)
                pixels[y*width+x]=new Color(value((x+.5f)/width,(y+.5f)/height),0,0,1);
            texture.SetPixels(pixels); texture.Apply(); texture.filterMode=FilterMode.Bilinear; texture.wrapMode=TextureWrapMode.Clamp;
            allocated.Add(texture); return texture;
        }
        private static void Bind(string name,Texture2D texture)
        {
            material.SetTexture(name,texture);
            material.SetVector(name+"_TexelSize",new Vector4(1f/texture.width,1f/texture.height,texture.width,texture.height));
        }
        private static Color Render(int mode)
        {
            material.SetInt("_Mode",mode);
            var target=RenderTexture.GetTemporary(4,4,0,RenderTextureFormat.ARGBFloat,RenderTextureReadWrite.Linear);
            var active=RenderTexture.active;
            var image=new Texture2D(4,4,TextureFormat.RGBAFloat,false,true);
            try
            {
                RenderTexture.active=target; GL.Clear(false,true,Color.magenta);
                if(!material.SetPass(0)) throw new InvalidOperationException("Conformance shader failed to bind");
                Graphics.DrawProceduralNow(MeshTopology.Triangles,3);
                image.ReadPixels(new Rect(0,0,4,4),0,0); image.Apply(); return image.GetPixel(2,2);
            }
            finally { RenderTexture.active=active; RenderTexture.ReleaseTemporary(target); UnityEngine.Object.DestroyImmediate(image); }
        }

        // Double-precision independent evaluation, separate from the HLSL expression.
        private static double Weight(double ha,double hb,double mask,double coverage,double width,double bias)
        {
            double m=Math.Max(0,Math.Min(1,mask+2*coverage-1));
            double score=m+bias*(hb-ha)*m*(1-m);
            if(width==0) return score>=.5 ? 1 : 0;
            double t=Math.Max(0,Math.Min(1,(score-.5)/width+.5));
            return t*t*(3-2*t);
        }
        private static double HA(double u,double v) => .3+.15*u+.08*v;
        private static double HB(double u,double v) => .7-.05*u+.03*v;
        private static double Composite(double u,double v,double coverage,double width,double bias)
        {
            double a=HA(u,v),b=HB(u,v);
            return a+(b-a)*Weight(a,b,u,coverage,width,bias);
        }
        private static double Intersect(Vector2 uv,Vector2 ray,double coverage,double width,double bias)
        {
            // Dense scan establishes the first bracket, independently of GPU quality.
            double low=0,high=0;
            for(int i=1;i<=8192;++i)
            {
                high=i/8192.0;
                if(1-Composite(uv.x-ray.x*high,uv.y-ray.y*high,coverage,width,bias)-high<=0) break;
                low=high;
            }
            for(int i=0;i<45;++i)
            {
                double middle=(low+high)*.5;
                if(1-Composite(uv.x-ray.x*middle,uv.y-ray.y*middle,coverage,width,bias)-middle>0) low=middle;
                else high=middle;
            }
            return (low+high)*.5;
        }

        public static List<string> Run()
        {
            checks=new List<string>();
            bool oldAsync=ShaderUtil.allowAsyncCompilation; ShaderUtil.allowAsyncCompilation=false;
            try
            {
                Shader shader=Shader.Find("Hidden/TextureWorks/ClusterConformance");
                Check(shader!=null && shader.isSupported,"Conformance shader available on "+SystemInfo.graphicsDeviceType);
                material=new Material(shader);
                var random=new System.Random(1991);
                for(int i=0;i<24;++i)
                {
                    Vector3 n=new Vector3((float)random.NextDouble()-.5f,(float)random.NextDouble()-.5f,.5f).normalized;
                    Vector3 d=new Vector3((float)random.NextDouble()-.5f,(float)random.NextDouble()-.5f,.7f).normalized;
                    float strength=i%4;
                    material.SetVector("_Base",n); material.SetVector("_Detail",d); material.SetFloat("_Strength",strength);
                    Vector3 scaled=new Vector3(d.x*strength,d.y*strength,d.z).normalized;
                    Vector3 expected=Quaternion.FromToRotation(Vector3.forward,n)*scaled;
                    Near(Render(0),ColorOf(expected),"RNM shortest-arc rotation "+i);
                }
                Vector3 baseNormal=new Vector3(.3f,-.4f,.8f).normalized;
                material.SetVector("_Base",baseNormal); material.SetVector("_Detail",Vector3.forward); material.SetFloat("_Strength",4);
                Near(Render(0),ColorOf(baseNormal),"Neutral detail preserves base");
                material.SetVector("_Detail",new Vector3(.5f,.2f,.7f).normalized); material.SetFloat("_Strength",0);
                Near(Render(0),ColorOf(baseNormal),"Zero detail strength preserves base");
                foreach(var item in new[]{new Vector4(1,2,6,1),new Vector4(4,2,6,.5f),new Vector4(6,2,6,0),
                    new Vector4(50,2,6,0),new Vector4(50,2,2,1),new Vector4(50,6,2,1)})
                {
                    material.SetVector("_Fade",item);
                    Near(Render(1),new Color(item.w,item.w,item.w,item.w),"Detail fade "+item);
                }
                foreach(float width in new[]{0f,.2f,1f}) foreach(float coverage in new[]{0f,.5f,1f}) foreach(float mask in new[]{0f,.5f,1f})
                {
                    material.SetVector("_Base",new Vector4(.2f,0,0,0)); material.SetVector("_Detail",new Vector4(.8f,0,0,0));
                    material.SetVector("_UV",new Vector4(mask,0,0,0)); material.SetVector("_Controls",new Vector4(coverage,width,1,0));
                    float expected=(float)Weight(.2,.8,mask,coverage,width,1);
                    Near(Render(2),new Color(expected,expected,expected,expected),$"Layer endpoints/width {coverage}/{width}/{mask}");
                }
                Bind("_A",Field((u,v)=>(float)HA(u,v))); Bind("_B",Field((u,v)=>(float)HB(u,v))); Bind("_Mask",Field((u,v)=>u));
                Vector2 uv=new Vector2(.53f,.46f),scale=new Vector2(.12f,.08f);
                Vector3 view=new Vector3(.65f,.15f,1);
                Vector2 ray=new Vector2(view.x*scale.x,view.y*scale.y);
                material.SetVector("_UV",new Vector4(uv.x,uv.y,0,0)); material.SetVector("_View",view);
                material.SetVector("_Scale",new Vector4(scale.x,scale.y,0,0));
                material.SetVector("_Steps",new Vector4(16,64,6,0)); material.SetVector("_Fade",new Vector4(0,12,20,0));
                foreach(float coverage in new[]{0f,.35f,.5f,.65f,1f}) foreach(float width in new[]{0f,.2f,1f})
                {
                    material.SetVector("_Controls",new Vector4(coverage,width,.5f,0));
                    float expected=(float)Intersect(uv,ray,coverage,width,.5);
                    Near(Render(3),new Color(uv.x-ray.x*expected,uv.y-ray.y*expected,expected,1),$"Composed intersection {coverage}/{width}",8e-5f);
                    float h=(float)Composite(uv.x,uv.y,coverage,width,.5);
                    float w=(float)Weight(HA(uv.x,uv.y),HB(uv.x,uv.y),uv.x,coverage,width,.5);
                    Near(Render(5),new Color(h,w,0,1),$"Composed field {coverage}/{width}",8e-5f);
                    if(width>0)
                    {
                        // Independent continuous derivative, not a copy of the sampled stencil.
                        const double eps=1e-5;
                        double hu=(Composite(uv.x+eps,uv.y,coverage,width,.5)-Composite(uv.x-eps,uv.y,coverage,width,.5))/(2*eps);
                        double hv=(Composite(uv.x,uv.y+eps,coverage,width,.5)-Composite(uv.x,uv.y-eps,coverage,width,.5))/(2*eps);
                        Vector3 normal=new Vector3((float)-hu*scale.x,(float)-hv*scale.y,1).normalized;
                        Near(Render(4),ColorOf(normal),$"Composed geometric normal {coverage}/{width}",.001f);
                    }
                }
                material.SetVector("_Controls",new Vector4(0,.2f,.5f,0));
                Near(Render(3),Render(6),"Layer A endpoint equals baseline POM");
                material.SetVector("_Fade",new Vector4(20,12,20,0));
                Near(Render(3),new Color(uv.x,uv.y,0,1),"Layered POM distance fade recovers original UV");
                material.SetVector("_Fade",new Vector4(0,12,20,0)); material.SetVector("_View",new Vector4(1,0,.001f,0));
                Near(Render(3),new Color(uv.x,uv.y,0,1),"Layered POM grazing output finite and neutral");
                // Neighboring R16 codes are observable after the layered sampler.
                foreach(ushort code in new ushort[]{32767,32768})
                {
                    var height=new Texture2D(4,4,TextureFormat.R16,false,true);
                    var values=new ushort[16]; for(int i=0;i<values.Length;++i) values[i]=code;
                    height.SetPixelData(values,0); height.Apply(); allocated.Add(height); Bind("_A",height);
                    Near(Render(5),new Color(code/65535f,0,0,1),"Layered R16 code "+code,1e-7f);
                }
                Check(!ShaderUtil.ShaderHasError(shader),"Exercised cluster HLSL compiles without errors");
                LitProfileChannels();
                return checks;
            }
            finally
            {
                if(material!=null) UnityEngine.Object.DestroyImmediate(material);
                foreach(var texture in allocated) UnityEngine.Object.DestroyImmediate(texture);
                allocated.Clear(); ShaderUtil.allowAsyncCompilation=oldAsync;
            }
        }
        private static Texture2D Constant(Color color)
        {
            var texture=new Texture2D(4,4,TextureFormat.RGBAFloat,false,true);
            var pixels=new Color[16]; for(int i=0;i<16;++i) pixels[i]=color;
            texture.SetPixels(pixels); texture.Apply();
            texture.filterMode=FilterMode.Bilinear; texture.wrapMode=TextureWrapMode.Clamp;
            allocated.Add(texture); return texture;
        }

        private static void LitProfileChannels()
        {
            var quad=GameObject.CreatePrimitive(PrimitiveType.Quad);
            var cameraObject=new GameObject("Cluster channel validation camera");
            var lit=new Material(Shader.Find(TextureWorks.Editor.TextureWorksBundleImporter.ShaderName));
            var target=RenderTexture.GetTemporary(8,8,24,RenderTextureFormat.ARGBFloat,RenderTextureReadWrite.Linear);
            var readback=new Texture2D(8,8,TextureFormat.RGBAFloat,false,true);
            var previous=RenderTexture.active;
            try
            {
                quad.layer=31; quad.transform.position=new Vector3(1000,1000,1000);
                quad.GetComponent<Renderer>().sharedMaterial=lit;
                Camera camera=cameraObject.AddComponent<Camera>(); camera.enabled=false; camera.cullingMask=1<<31;
                camera.transform.position=quad.transform.position+Vector3.back*2; camera.transform.LookAt(quad.transform.position);
                camera.orthographic=true; camera.orthographicSize=.5f; camera.nearClipPlane=.1f; camera.farClipPlane=5;
                camera.clearFlags=CameraClearFlags.SolidColor; camera.backgroundColor=Color.magenta;
                camera.GetUniversalAdditionalCameraData().renderPostProcessing=false; camera.targetTexture=target;
                Vector3 na=new Vector3(.2f,.25f,1).normalized,nb=new Vector3(-.3f,-.1f,1).normalized;
                Color encodedA=new Color(na.x*.5f+.5f,na.y*.5f+.5f,na.z*.5f+.5f,1);
                Color encodedB=new Color(nb.x*.5f+.5f,-nb.y*.5f+.5f,nb.z*.5f+.5f,1);
                var data=new Dictionary<string,Color> {
                    {"_BaseMapA",new Color(.2f,.25f,.5f,1)},{"_BaseMapB",new Color(.6f,.75f,.2f,1)},
                    {"_HeightA",new Color(.3f,0,0,1)},{"_HeightB",new Color(.7f,0,0,1)},
                    {"_Mask",new Color(.5f,0,0,1)},{"_NormalA",encodedA},{"_NormalB",encodedB},
                    {"_RoughnessA",new Color(.2f,0,0,1)},{"_RoughnessB",new Color(.8f,0,0,1)},
                    {"_MetallicA",Color.black},{"_MetallicB",Color.white},{"_AOA",new Color(.4f,0,0,1)},{"_AOB",Color.white}};
                foreach(var pair in data) lit.SetTexture(pair.Key,Constant(pair.Value));
                lit.SetVector("_NormalEncoding",new Vector4(0,0,1,-1)); lit.SetVector("_AuthoredNormals",new Vector4(1,1,0,0));
                lit.SetFloat("_DetailColorStrength",0); lit.SetFloat("_DetailNormalStrength",0); lit.SetFloat("_DetailRoughness",0);
                lit.SetFloat("_Stage",5); lit.SetFloat("_BlendWidth",1); lit.SetFloat("_HeightBias",0);
                foreach(float weight in new[]{0f,.5f,1f})
                {
                    lit.SetFloat("_Coverage",weight);
                    Vector3 slopes=Vector3.Lerp(new Vector3(na.x/na.z,na.y/na.z,1),new Vector3(nb.x/nb.z,nb.y/nb.z,1),weight).normalized;
                    for(int debug=7;debug<=11;++debug)
                    {
                        lit.SetFloat("_Debug",debug); camera.Render(); RenderTexture.active=target;
                        readback.ReadPixels(new Rect(0,0,8,8),0,0); readback.Apply();
                        Color expected;
                        if(debug==7) expected=new Color(slopes.x*.5f+.5f,slopes.y*.5f+.5f,slopes.z*.5f+.5f,1);
                        else if(debug==8) expected=Color.Lerp(data["_BaseMapA"],data["_BaseMapB"],weight);
                        else
                        {
                            float value=debug==9 ? Mathf.Lerp(.2f,.8f,weight) : debug==10 ? weight : Mathf.Lerp(.4f,1,weight);
                            expected=new Color(value,value,value,1);
                        }
                        Near(readback.GetPixel(4,4),expected,$"Lit profile authored normals/linear channel {debug} weight {weight}",.001f);
                    }
                }
                Check(!ShaderUtil.ShaderHasError(lit.shader),"Authored normal and all channel branches compile in Layered Lit");
            }
            finally
            {
                RenderTexture.active=previous; RenderTexture.ReleaseTemporary(target);
                UnityEngine.Object.DestroyImmediate(readback); UnityEngine.Object.DestroyImmediate(lit);
                UnityEngine.Object.DestroyImmediate(cameraObject); UnityEngine.Object.DestroyImmediate(quad);
            }
        }
    }
}
