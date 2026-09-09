using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using TextureWorks.Editor;
using Unity.Pipeline.Commands;
using UnityEditor;
using UnityEngine;

namespace TextureWorks.MaterialLab.Editor
{
    public static class LabClusterValidation
    {
        [CliCommand("cluster_profile","Start a bounded editor frame timing probe in Play Mode. Poll Evidence/cluster/editor-performance.json for completion.",Tags=new[]{"textureworks"})]
        public static object Profile()
        {
            if(!Application.isPlaying) throw new InvalidOperationException("Enter Play Mode first");
            if(UnityEngine.Object.FindAnyObjectByType<LabPerformance>()!=null) throw new InvalidOperationException("A measurement is already running");
            string path=Path.GetFullPath("Evidence/cluster/editor-performance.json");
            if(File.Exists(path)) File.Delete(path);
            new GameObject("Bounded editor performance probe").AddComponent<LabPerformance>();
            return new {started=true,report=path};
        }
        [CliCommand("cluster_controls","Set runtime coverage, blend width, debug view 0-11 and quality 0-2.",Tags=new[]{"textureworks"})]
        public static object Controls(float coverage=.5f,float blend_width=.25f,int debug=0,int quality=1)
        {
            var lab=UnityEngine.Object.FindAnyObjectByType<LabController>();
            if(lab==null) throw new InvalidOperationException("Open the Material Lab first");
            lab.SetClusterControls(coverage,blend_width,debug,quality);
            return new {lab.coverage,lab.blendWidth,lab.debugView,lab.quality};
        }

        [CliCommand("cluster_validate","Run analytic GPU/import checks and fixed/moving camera comparisons. Writes Evidence/cluster. Full run requires Play Mode.",Tags=new[]{"textureworks"})]
        public static object Validate(bool numerical_only=false,bool motion=true)
        {
            string directory=Path.GetFullPath("Evidence/cluster"); Directory.CreateDirectory(directory);
            var checks=ClusterConformance.Run();
            ValidateRejectedMetadata(directory,checks);
            var imported=new List<object>();
            foreach(string path in Directory.GetFiles(LabBuilder.Root+"/Bundles","material.json",SearchOption.AllDirectories))
            {
                var bundle=TextureWorksBundleImporter.Validate(path);
                foreach(var entry in bundle.textures)
                {
                    string texturePath=(Path.GetDirectoryName(path)+"/"+entry.path).Replace('\\','/');
                    var texture=AssetDatabase.LoadAssetAtPath<Texture2D>(texturePath);
                    var importer=(TextureImporter)AssetImporter.GetAtPath(texturePath);
                    Require(texture!=null && texture.width==entry.width && texture.height==entry.height,
                        "Imported dimensions "+bundle.name+"/"+entry.path,checks);
                    Require(importer.textureType==TextureImporterType.Default && importer.sRGBTexture==(entry.color_space=="srgb")
                        && importer.mipmapEnabled && importer.filterMode==FilterMode.Trilinear && importer.anisoLevel==4
                        && importer.wrapMode==((entry.role.StartsWith("detail_",StringComparison.Ordinal) ? bundle.detail.boundary : bundle.boundary)=="wrap" ? TextureWrapMode.Repeat : TextureWrapMode.Clamp)
                        && importer.textureCompression==TextureImporterCompression.Uncompressed,
                        "Color/normal/sampler contract "+bundle.name+"/"+entry.path,checks);
                    if(entry.bits==16 || entry.role=="height")
                    {
                        Require(texture.format==TextureFormat.R16,"R16 precision "+bundle.name+"/"+entry.path,checks);
                        int distinct=texture.GetPixels().Select(p=>Mathf.RoundToInt(p.r*65535)).Distinct().Count();
                        imported.Add(new {bundle=bundle.name,entry.role,entry.layer,format=texture.format.ToString(),distinctLevels=distinct});
                    }
                }
            }
            var differences=new List<object>();
            if(!numerical_only) CaptureScene(directory,checks,differences,motion);
            var shader=Shader.Find(TextureWorksBundleImporter.ShaderName);
            Require(shader!=null && !ShaderUtil.ShaderHasError(shader),"Layered Lit rendered shader has no compilation errors",checks);
            var report=new {success=true,unity=Application.unityVersion,urp="17.6.0",gpu=SystemInfo.graphicsDeviceName,
                graphicsApi=SystemInfo.graphicsDeviceType.ToString(),width=1440,height=900,quality="balanced 16-64 / 4",
                conditions="Editor Camera.Render, fixed real-time lighting, ACES, identical geometry per stage; motion changes camera only.",
                checks,imported,differences,numericalOnly=numerical_only,motion,
                limitations="Pixel tests establish endpoints and visible effects. Image/animation review and player measurements are separate."};
            File.WriteAllText(Path.Combine(directory,"validation.json"),Newtonsoft.Json.JsonConvert.SerializeObject(report,Newtonsoft.Json.Formatting.Indented));
            Debug.Log("TEXTUREWORKS_CLUSTER_VALIDATION_PASSED "+checks.Count);
            return new {success=true,checks=checks.Count,report="Evidence/cluster/validation.json"};
        }

        private static void Require(bool condition,string message,List<string> checks)
        { if(!condition) throw new InvalidOperationException(message); checks.Add(message); }

        private static void ValidateRejectedMetadata(string directory,List<string> checks)
        {
            string source=LabBuilder.Root+"/Bundles/masonry";
            string temporary=Path.Combine(directory,"import-rejections"); Directory.CreateDirectory(temporary);
            foreach(string file in Directory.GetFiles(source,"*.png"))
                File.Copy(file,Path.Combine(temporary,Path.GetFileName(file)),true);
            string original=File.ReadAllText(Path.Combine(source,"material.json"));
            foreach(string change in new[]{"normal provenance","detail boundary","height encoding"})
            {
                var value=Newtonsoft.Json.Linq.JObject.Parse(original);
                if(change=="normal provenance") value["layers"][0]["normal_authored"]=true;
                else if(change=="detail boundary") value["detail"]["boundary"]="guess";
                else value["textures"].First(t=>(string)t["role"]=="height")["encoding"]="black-top";
                string manifest=Path.Combine(temporary,"material.json"); File.WriteAllText(manifest,value.ToString());
                bool rejected=false;
                try { TextureWorksBundleImporter.Validate(manifest); }
                catch(InvalidDataException) { rejected=true; }
                Require(rejected,"Importer rejects incompatible "+change,checks);
            }
        }
        private static Color32[] Capture(Camera camera,string path,int width=1440,int height=900)
        {
            var rt=RenderTexture.GetTemporary(width,height,24,RenderTextureFormat.ARGB32,RenderTextureReadWrite.sRGB);
            var target=camera.targetTexture; var active=RenderTexture.active;
            var image=new Texture2D(width,height,TextureFormat.RGB24,false);
            try
            {
                camera.targetTexture=rt; camera.Render(); RenderTexture.active=rt;
                image.ReadPixels(new Rect(0,0,width,height),0,0); image.Apply();
                File.WriteAllBytes(path,image.EncodeToPNG()); return image.GetPixels32();
            }
            finally { camera.targetTexture=target; RenderTexture.active=active; RenderTexture.ReleaseTemporary(rt); UnityEngine.Object.DestroyImmediate(image); }
        }
        private static double Difference(Color32[] a,Color32[] b)
        {
            double sum=0; for(int i=0;i<a.Length;++i) sum+=Math.Abs(a[i].r-b[i].r)+Math.Abs(a[i].g-b[i].g)+Math.Abs(a[i].b-b[i].b);
            return sum/(a.Length*3.0*255);
        }
        private static void Observe(Camera camera,Vector3 position,Vector3 target)
        { camera.transform.position=position; camera.transform.LookAt(target); }
        private static void Set(IEnumerable<Material> materials,string name,float value)
        { foreach(var material in materials) material.SetFloat(name,value); }

        private static void CaptureScene(string directory,List<string> checks,List<object> differences,bool motion)
        {
            Require(Application.isPlaying,"Scene comparisons run in Play Mode",checks);
            var lab=UnityEngine.Object.FindAnyObjectByType<LabController>();
            Require(lab!=null,"Lab controller exists",checks);
            var materials=lab.comparisonMaterials.Where(m=>m.shader.name==TextureWorksBundleImporter.ShaderName).ToArray();
            var copies=materials.Select(m=>new Material(m)).ToArray();
            var camera=lab.viewCamera;
            Vector3 oldCameraPosition=camera.transform.localPosition;
            Quaternion oldCameraRotation=camera.transform.localRotation;
            bool oldInput=lab.acceptInput,oldAnimate=lab.movingLight.animate,oldAsync=ShaderUtil.allowAsyncCompilation;
            float oldPhase=lab.movingLight.phase;
            ShaderUtil.allowAsyncCompilation=false; lab.acceptInput=false; lab.movingLight.animate=false; lab.movingLight.ApplyPhase(0);
            try
            {
                string[] names={"masonry","wood","painted-metal","fine-detail"};
                for(int index=0;index<4;++index)
                {
                    string name=names[index]; float center=12.7f+3.55f*index;
                    Vector3 target=new Vector3(center,2.25f,-5.49f);
                    Observe(camera,target+new Vector3(.6f,.1f,2.15f),target);
                    Set(materials,"_Debug",0); Set(materials,"_Coverage",.5f); Set(materials,"_BlendWidth",.25f);
                    Color32[] withoutDetail=null;
                    for(int stage=0;stage<6;++stage)
                    {
                        Set(materials,"_Stage",stage);
                        Color32[] pixels=Capture(camera,Path.Combine(directory,name+"-stage"+stage+".png"));
                        Require(pixels.Count(p=>p.r>20 || p.g>20 || p.b>20)>pixels.Length/3,name+" stage "+stage+" visibly illuminated",checks);
                        if(stage==2) withoutDetail=pixels;
                        if(stage==3) Require(Difference(withoutDetail,pixels)>1e-6,name+" nonzero detail changes the rendered surface",checks);
                    }
                    Set(materials,"_Stage",2);
                    Color32[] baseline=Capture(camera,Path.Combine(directory,name+"-base-pom.png"));
                    Set(materials,"_DetailColorStrength",0); Set(materials,"_DetailNormalStrength",0); Set(materials,"_DetailRoughness",0);
                    Set(materials,"_Stage",3);
                    Color32[] zero=Capture(camera,Path.Combine(directory,name+"-zero-detail.png"));
                    double zeroDifference=Difference(baseline,zero);
                    Require(zeroDifference==0,name+" zero detail is exactly base",checks);
                    Set(materials,"_Stage",5); Set(materials,"_Coverage",0);
                    Color32[] allA=Capture(camera,Path.Combine(directory,name+"-all-a.png"));
                    Require(Difference(baseline,allA)==0,name+" all A exactly matches base POM",checks);
                    Set(materials,"_Coverage",1); Set(materials,"_BlendWidth",0);
                    Color32[] allB=Capture(camera,Path.Combine(directory,name+"-all-b.png"));
                    double endpointDifference=Difference(allA,allB);
                    Require(endpointDifference>.0005,name+" all B changes material appearance at zero width",checks);
                    for(int i=0;i<materials.Length;++i) materials[i].CopyPropertiesFromMaterial(copies[i]);
                    Set(materials,"_Stage",3); Set(materials,"_DetailFadeStart",0); Set(materials,"_DetailFadeEnd",.01f);
                    Color32[] far=Capture(camera,Path.Combine(directory,name+"-faded-detail.png"));
                    Require(Difference(baseline,far)==0,name+" beyond detail fade exactly matches base",checks);
                    for(int i=0;i<materials.Length;++i) materials[i].CopyPropertiesFromMaterial(copies[i]);
                    Set(materials,"_Stage",5);
                    for(int debug=1;debug<=7;++debug)
                    {
                        Set(materials,"_Debug",debug);
                        Capture(camera,Path.Combine(directory,name+"-debug"+debug+".png"));
                    }
                    Set(materials,"_Debug",0);
                    if(motion)
                    {
                        string frames=Path.Combine(directory,name+"-motion"); Directory.CreateDirectory(frames);
                        for(int frame=0;frame<48;++frame)
                        {
                            // Orbit inside the room, return to the front, then retreat
                            // through the detail fade. No camera moves outside a wall.
                            float degrees=frame<24 ? Mathf.Lerp(-68,68,frame/23f)
                                : frame<32 ? Mathf.Lerp(68,0,(frame-23)/8f) : 0;
                            float angle=degrees*Mathf.Deg2Rad;
                            float distance=frame<32 ? 1.6f : Mathf.Lerp(1.6f,8,(frame-31)/16f);
                            Vector3 position=target+new Vector3(Mathf.Sin(angle)*distance,.12f,Mathf.Cos(angle)*distance);
                            Observe(camera,position,target);
                            Capture(camera,Path.Combine(frames,frame.ToString("D3")+".png"),960,600);
                        }
                        checks.Add(name+" 48 close/grazing/distant motion frames captured inside workshop bounds");
                    }
                    differences.Add(new {material=name,zeroDetailDifference=zeroDifference,endpointDifference});
                }
                // Moving illumination on actual game fixtures at identical camera position.
                camera.transform.localPosition=oldCameraPosition; lab.SetView(3); Set(materials,"_Stage",5);
                lab.movingLight.ApplyPhase(0);
                var lightA=Capture(camera,Path.Combine(directory,"cabinet-light-a.png"));
                lab.movingLight.ApplyPhase(2.1f);
                var lightB=Capture(camera,Path.Combine(directory,"cabinet-light-b.png"));
                double movingDifference=Difference(lightA,lightB);
                Require(movingDifference>.0001,"Layered cabinet responds to moving illumination",checks);
                differences.Add(new {movingLightMeanDifference=movingDifference});
            }
            finally
            {
                for(int i=0;i<materials.Length;++i) { materials[i].CopyPropertiesFromMaterial(copies[i]); UnityEngine.Object.DestroyImmediate(copies[i]); }
                camera.transform.localPosition=oldCameraPosition; camera.transform.localRotation=oldCameraRotation;
                lab.SetView(0); lab.acceptInput=oldInput; lab.movingLight.ApplyPhase(oldPhase); lab.movingLight.animate=oldAnimate;
                ShaderUtil.allowAsyncCompilation=oldAsync;
            }
        }
    }
}
