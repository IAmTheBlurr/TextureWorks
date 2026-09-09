using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using Unity.Pipeline.Commands;
using TextureWorks.Editor;

namespace TextureWorks.MaterialLab.Editor
{
    /// <summary>Explicit rebuild of the lab scene. Normal editing never invokes it.</summary>
    public static class LabBuilder
    {
        public const string Root = "Assets/TextureWorks";
        public const string ScenePath = Root + "/Scenes/MaterialLab.unity";
        private static Material charcoal, stone, trim, teal, bronze, glow;
        private static Material[,] surfaces;
        private static Material[,] cluster;
        private static Font font;
        private static Transform architecture, exhibits, workshop;

        [MenuItem("TextureWorks/Rebuild demonstration scene")]
        [CliCommand("cluster_rebuild", "Import material bundles and rebuild the demonstration scene. Saves dirty scenes as backup copies first.", Tags = new[]{"textureworks"})]
        public static void Rebuild()
        {
            for (int i=0;i<UnityEngine.SceneManagement.SceneManager.sceneCount;++i)
            {
                var scene = UnityEngine.SceneManagement.SceneManager.GetSceneAt(i);
                if (!scene.isDirty) continue;
                Directory.CreateDirectory("Assets/Evidence/SceneBackups");
                string backup = AssetDatabase.GenerateUniqueAssetPath("Assets/Evidence/SceneBackups/"+scene.name+".unity");
                if (!EditorSceneManager.SaveScene(scene,backup,true))
                    throw new InvalidOperationException("Could not preserve dirty scene before rebuilding: "+scene.name);
            }
            Directory.CreateDirectory(Root + "/Materials");
            Directory.CreateDirectory(Root + "/Scenes");
            Directory.CreateDirectory(Root + "/Settings");
            AssetDatabase.Refresh();
            ConfigureTextures(); ConfigurePipeline();
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            charcoal = Solid("Charcoal", new Color(.045f,.061f,.069f), .28f);
            stone = Solid("Plaster", new Color(.43f,.47f,.46f), .12f);
            trim = Solid("Graphite steel", new Color(.10f,.13f,.14f), .6f, .65f);
            teal = Solid("Oxide green", new Color(.055f,.30f,.28f), .42f, .3f);
            bronze = Solid("Copper trim", new Color(.36f,.17f,.075f), .52f, .65f);
            glow = Solid("Luminous strip", new Color(.65f,.87f,.81f), .25f);
            glow.EnableKeyword("_EMISSION"); glow.SetColor("_EmissionColor", new Color(.7f,1,.85f) * 2);
            surfaces = new Material[4,3];
            string[] names = {"limestone-blocks", "red-brick", "machined-metal", "oak-planks"};
            float[] depths = {.06f,.04f,.025f,.035f};
            float[] minimumRoughness = {.64f,.76f,.36f,.59f};
            for (int material = 0; material < 4; ++material)
                for (int stage = 0; stage < 3; ++stage)
                {
                    Material m = GetMaterial(names[material] + "-stage" + stage, Shader.Find("TextureWorks/URP/Parallax Lit"));
                    m.SetTexture("_BaseMap", Texture(names[material], "albedo"));
                    m.SetTexture("_HeightMap", Texture(names[material], "height"));
                    m.SetTexture("_RoughnessMap", Texture(names[material], "roughness"));
                    m.SetTexture("_AOMap", Texture(names[material], "ao"));
                    m.SetFloat("_Stage", stage); m.SetFloat("_DepthMeters", depths[material]);
                    m.SetFloat("_Metallic", material == 2 ? .75f : 0);
                    m.SetFloat("_RoughnessMin", minimumRoughness[material]);
                    m.SetFloat("_MinSteps", 16); m.SetFloat("_MaxSteps", 64);
                    m.SetFloat("_FadeStart", 12); m.SetFloat("_FadeEnd", 20);
                    EditorUtility.SetDirty(m); surfaces[material,stage] = m;
                }
            cluster = new Material[4,6];
            string[] bundleNames = {"masonry","wood","painted-metal","fine-detail"};
            for(int i=0;i<4;++i)
            {
                Material imported = TextureWorksBundleImporter.Import(Root+"/Bundles/"+bundleNames[i]+"/material.json");
                for(int stage=0;stage<6;++stage)
                {
                    Material m = GetMaterial("cluster-"+bundleNames[i]+"-stage"+stage,imported.shader);
                    m.CopyPropertiesFromMaterial(imported); m.SetFloat("_Stage",stage);
                    EditorUtility.SetDirty(m); cluster[i,stage] = m;
                }
            }
            architecture = new GameObject("Architecture").transform;
            exhibits = new GameObject("01 Surface gallery").transform;
            workshop = new GameObject("02 Workshop").transform;
            BuildRooms(); BuildGallery(); BuildWorkshop(); ConfigureLighting();
            var player = new GameObject("Visitor");
            var controller = player.AddComponent<CharacterController>();
            controller.height = 1.75f; controller.radius = .28f; controller.center = new Vector3(0,.9f,0);
            controller.stepOffset = .25f; controller.skinWidth = .025f;
            var cameraObject = new GameObject("Visitor camera");
            cameraObject.transform.SetParent(player.transform, false);
            cameraObject.transform.localPosition = Vector3.up * 1.65f;
            var camera = cameraObject.AddComponent<Camera>();
            camera.tag = "MainCamera"; camera.fieldOfView = 63;
            camera.nearClipPlane = .06f; camera.farClipPlane = 70;
            camera.clearFlags = CameraClearFlags.SolidColor; camera.backgroundColor = new Color(.12f,.17f,.20f);
            camera.allowHDR = true; camera.allowMSAA = true;
            camera.GetUniversalAdditionalCameraData().renderPostProcessing = true;
            cameraObject.AddComponent<AudioListener>();
            var lab = player.AddComponent<LabController>(); lab.viewCamera = camera;
            lab.movingLight = UnityEngine.Object.FindAnyObjectByType<LabLighting>();
            var materialList = new List<Material>(); var stages = new List<int>();
            for (int i = 0; i < 4; ++i) for (int s = 0; s < 3; ++s) { materialList.Add(surfaces[i,s]); stages.Add(s); }
            for (int i = 0; i < 4; ++i) for (int s = 0; s < 6; ++s) { materialList.Add(cluster[i,s]); stages.Add(s); }
            lab.comparisonMaterials = materialList.ToArray(); lab.originalStages = stages.ToArray();
            lab.SetView(0);
            PlayerSettings.companyName = "TextureWorks"; PlayerSettings.productName = "TextureWorks Material Lab";
            PlayerSettings.colorSpace = ColorSpace.Linear;
            PlayerSettings.defaultScreenWidth = 1440; PlayerSettings.defaultScreenHeight = 900;
            PlayerSettings.fullScreenMode = FullScreenMode.Windowed;
            PlayerSettings.runInBackground = true;
            PlayerSettings.enableFrameTimingStats = true;
            EditorBuildSettings.scenes = new[] {new EditorBuildSettingsScene(ScenePath, true)};
            EditorSceneManager.SaveScene(UnityEngine.SceneManagement.SceneManager.GetActiveScene(), ScenePath);
            AssetDatabase.SaveAssets();
            Debug.Log("TEXTUREWORKS_LAB_READY " + ScenePath);
        }

        private static Texture2D Texture(string name, string kind) =>
            AssetDatabase.LoadAssetAtPath<Texture2D>($"{Root}/Textures/{name}-{kind}.png");

        private static void ConfigureTextures()
        {
            foreach (string file in Directory.GetFiles(Root + "/Textures", "*.png"))
            {
                var importer = (TextureImporter)AssetImporter.GetAtPath(file.Replace('\\','/'));
                bool height = file.EndsWith("-height.png", StringComparison.Ordinal);
                importer.textureType = TextureImporterType.Default;
                importer.sRGBTexture = file.EndsWith("-albedo.png", StringComparison.Ordinal);
                importer.textureCompression = TextureImporterCompression.Uncompressed;
                importer.mipmapEnabled = true; importer.filterMode = FilterMode.Trilinear;
                importer.anisoLevel = 1; importer.wrapMode = TextureWrapMode.Repeat;
                importer.isReadable = height; // The acceptance check verifies imported precision.
                if (height)
                {
                    var settings = importer.GetDefaultPlatformTextureSettings();
                    settings.format = TextureImporterFormat.R16; importer.SetPlatformTextureSettings(settings);
                    var windows = importer.GetPlatformTextureSettings("Standalone");
                    windows.overridden = true; windows.format = TextureImporterFormat.R16;
                    importer.SetPlatformTextureSettings(windows);
                }
                importer.SaveAndReimport();
            }
        }

        private static void ConfigurePipeline()
        {
            string rendererPath = Root + "/Settings/LabRenderer.asset";
            var data = AssetDatabase.LoadAssetAtPath<UniversalRendererData>(rendererPath);
            if (data == null) { data = ScriptableObject.CreateInstance<UniversalRendererData>(); AssetDatabase.CreateAsset(data, rendererPath); }
            data.renderingMode = RenderingMode.Forward;
            string pipelinePath = Root + "/Settings/LabPipeline.asset";
            var pipeline = AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>(pipelinePath);
            if (pipeline == null) { pipeline = UniversalRenderPipelineAsset.Create(data); AssetDatabase.CreateAsset(pipeline, pipelinePath); }
            pipeline.msaaSampleCount = 4; pipeline.shadowDistance = 45;
            pipeline.mainLightShadowmapResolution = 2048; pipeline.maxAdditionalLightsCount = 8;
            pipeline.gpuResidentDrawerMode = GPUResidentDrawerMode.Disabled;
            EditorSettings.enterPlayModeOptionsEnabled = false;
            var serialized = new SerializedObject(pipeline);
            serialized.FindProperty("m_MainLightShadowsSupported").boolValue = true;
            serialized.FindProperty("m_AdditionalLightShadowsSupported").boolValue = true;
            serialized.FindProperty("m_AdditionalLightsRenderingMode").intValue = 1;
            serialized.FindProperty("m_AdditionalLightsShadowmapResolution").intValue = 4096;
            serialized.ApplyModifiedPropertiesWithoutUndo();
            GraphicsSettings.defaultRenderPipeline = pipeline;
            int previous = QualitySettings.GetQualityLevel();
            for (int i = 0; i < QualitySettings.names.Length; ++i) { QualitySettings.SetQualityLevel(i); QualitySettings.renderPipeline = pipeline; }
            QualitySettings.SetQualityLevel(previous); QualitySettings.vSyncCount = 1;
            EditorUtility.SetDirty(data); EditorUtility.SetDirty(pipeline);
        }

        private static Material GetMaterial(string name, Shader shader)
        {
            if (shader == null) throw new InvalidOperationException("A required lab shader did not import.");
            string path = Root + "/Materials/" + name + ".mat";
            Material material = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (material == null) { material = new Material(shader); AssetDatabase.CreateAsset(material, path); }
            material.shader = shader; return material;
        }
        private static Material Solid(string name, Color color, float smooth, float metal = 0)
        {
            Material material = GetMaterial(name, Shader.Find("Universal Render Pipeline/Lit"));
            material.SetColor("_BaseColor", color); material.SetFloat("_Smoothness", smooth); material.SetFloat("_Metallic", metal);
            EditorUtility.SetDirty(material); return material;
        }
        private static GameObject Shape(string name, PrimitiveType type, Vector3 position, Vector3 scale, Material material, Transform parent)
        {
            GameObject gameObject = GameObject.CreatePrimitive(type); gameObject.name = name;
            gameObject.transform.SetParent(parent); gameObject.transform.position = position; gameObject.transform.localScale = scale;
            gameObject.GetComponent<Renderer>().sharedMaterial = material; return gameObject;
        }
        private static GameObject Box(string name, Vector3 position, Vector3 scale, Material material, Transform parent) =>
            Shape(name, PrimitiveType.Cube, position, scale, material, parent);
        private static void Text(string name, string content, Vector3 position, float size, Color color, Transform parent, float angle = 0)
        {
            GameObject label = new GameObject(name); label.transform.SetParent(parent);
            label.transform.position = position; label.transform.rotation = Quaternion.Euler(0,angle,0);
            TextMesh text = label.AddComponent<TextMesh>(); text.text = content; text.font = font;
            text.fontSize = 80; text.characterSize = size * .53f; text.anchor = TextAnchor.MiddleCenter; text.alignment = TextAlignment.Center;
            text.color = color; label.GetComponent<MeshRenderer>().sharedMaterial = font.material;
            label.SetActive(false);
            label.AddComponent<LabSign>().shader = Shader.Find("TextureWorks/Lab/Signage");
            label.SetActive(true);
        }
        private static void BuildRooms()
        {
            Box("Gallery floor", new Vector3(0,-.15f,2), new Vector3(20,.3f,16), charcoal, architecture);
            Box("Workshop floor", new Vector3(18,-.15f,2), new Vector3(16,.3f,16), charcoal, architecture);
            Box("Gallery north wall", new Vector3(0,2.3f,10), new Vector3(20,4.6f,.3f), stone, architecture);
            Box("South wall", new Vector3(8,2.3f,-6), new Vector3(36,4.6f,.3f), stone, architecture);
            Box("West wall", new Vector3(-10,2.3f,2), new Vector3(.3f,4.6f,16), stone, architecture);
            Box("Workshop north wall", new Vector3(18,2.3f,10), new Vector3(16,4.6f,.3f), stone, architecture);
            Box("East wall", new Vector3(26,2.3f,2), new Vector3(.3f,4.6f,16), stone, architecture);
            Box("Divider north", new Vector3(10,2.3f,6.5f), new Vector3(.35f,4.6f,7), trim, architecture);
            Box("Divider south", new Vector3(10,2.3f,-3.5f), new Vector3(.35f,4.6f,5), trim, architecture);
            Box("Door lintel", new Vector3(10,3.8f,1), new Vector3(.5f,1.6f,4), teal, architecture);
            Box("Workshop canopy", new Vector3(18,4.6f,6), new Vector3(16,.25f,8), trim, architecture);
            for (int x = -8; x <= 24; x += 2)
                Box("Floor joint", new Vector3(x,.002f,2), new Vector3(.014f,.005f,15.7f), trim, architecture);
            for (int z = -4; z <= 8; z += 2)
                Box("Floor joint", new Vector3(8,.002f,z), new Vector3(35.7f,.005f,.014f), trim, architecture);
            Box("Gallery datum", new Vector3(0,.03f,7.4f), new Vector3(19,.01f,.035f), bronze, architecture);
            Box("Wayfinding line", new Vector3(5,.015f,1), new Vector3(15,.02f,.06f), teal, architecture);
            for (int x = -9; x <= 25; x += 4)
            {
                var beam = Box("Roof beam", new Vector3(x,4.7f,2), new Vector3(.14f,.28f,16), trim, architecture);
                if (x < 10) beam.GetComponent<Renderer>().shadowCastingMode = ShadowCastingMode.Off;
            }
            Text("Workshop direction", "02 / WORKSHOP  >", new Vector3(8.8f,3.5f,3.2f), .065f, new Color(.75f,.94f,.85f), architecture);
        }
        private static void BuildGallery()
        {
            string[] titles = {"LIMESTONE", "FIRED BRICK", "MACHINED METAL", "OAK PLANKS"};
            string[] labels = {"BASE", "NORMAL", "POM"};
            Text("Gallery heading", "01 / SURFACE STUDIES", new Vector3(0,4.2f,9.78f), .12f, Color.white, exhibits);
            for (int i = 0; i < 4; ++i)
            {
                float center = -7.2f + i * 4.8f;
                Box("Display backing", new Vector3(center,2.2f,9.75f), new Vector3(4.48f,3.3f,.12f), charcoal, exhibits);
                Text("Material name", titles[i], new Vector3(center,3.52f,9.61f), .065f, new Color(.73f,.88f,.83f), exhibits);
                for (int stage = 0; stage < 3; ++stage)
                {
                    float x = center + (stage - 1) * 1.44f;
                    Box("Sample frame", new Vector3(x,2.4f,9.55f), new Vector3(1.38f,1.56f,.15f), bronze, exhibits);
                    Shape(titles[i] + " " + labels[stage], PrimitiveType.Quad, new Vector3(x,2.4f,9.455f),
                        new Vector3(1.28f,1.46f,1), surfaces[i,stage], exhibits);
                    Text("Stage label", labels[stage], new Vector3(x,1.4f,9.53f), .054f, Color.white, exhibits);
                }
                Text("Depth label", "SAME INPUT / SAME LIGHT", new Vector3(center,.99f,9.59f), .038f, new Color(.65f,.7f,.72f), exhibits);
                Box("Display plinth", new Vector3(center,.34f,9), new Vector3(4.48f,.68f,1.3f), trim, exhibits);
                Box("Display light strip", new Vector3(center,.695f,9.48f), new Vector3(4.2f,.035f,.04f), glow, exhibits);
            }
            Text("Gallery explanation", "WALK CLOSER. LOOK ALONG THE SURFACE.\n1 / BASE    2 / NORMAL    3 / PARALLAX", new Vector3(0,2.6f,-5.79f), .10f,
                Color.white, exhibits, 180);
        }
        private static void BuildWorkshop()
        {
            Text("Workshop heading", "02 / MATERIAL WORKSHOP", new Vector3(18,4.0f,9.72f), .12f, Color.white, workshop);
            Text("Workshop explanation", "GAME ASSEMBLIES / MOVING TASK LIGHT", new Vector3(18,3.55f,9.72f), .052f, new Color(.76f,.86f,.82f), workshop);
            Box("Masonry inset", new Vector3(17,1.5f,9.65f), new Vector3(6,3,.22f), cluster[0,5], workshop);
            // Bench planks and structural framing expose UV seams, scale, and oblique views.
            for (int i = 0; i < 4; ++i)
                Box("Oak bench plank", new Vector3(18,1.02f,5.7f + i * .31f), new Vector3(6,.14f,.3f), cluster[1,5], workshop);
            foreach (float x in new[] {15.4f,20.6f}) foreach (float z in new[] {5.8f,6.6f})
                Box("Bench leg", new Vector3(x,.46f,z), new Vector3(.12f,.92f,.12f), trim, workshop);
            Box("Bench rail", new Vector3(18,.38f,6.15f), new Vector3(5.3f,.12f,.1f), trim, workshop);
            Crate(new Vector3(12.8f,.62f,6.9f), 1.2f); Crate(new Vector3(14.3f,.46f,7.5f), .88f);
            Crate(new Vector3(12.8f,1.6f,6.9f), .72f);
            Box("Machine cabinet", new Vector3(23,1.28f,6.6f), new Vector3(2.6f,2.56f,1.35f), cluster[2,5], workshop);
            for (int i = 0; i < 2; ++i)
            {
                Box("Recessed cabinet panel", new Vector3(22.35f+i*1.3f,1.44f,5.9f), new Vector3(1.14f,1.9f,.075f), cluster[2,5], workshop);
                Box("Cabinet handle", new Vector3(22.78f+i*.44f,1.5f,5.8f), new Vector3(.06f,.34f,.08f), bronze, workshop);
            }
            for (int i = 0; i < 3; ++i)
            {
                var cylinder = Shape("Pipe", PrimitiveType.Cylinder, new Vector3(25.1f,1.65f,6+i*.85f), new Vector3(.23f,1.65f,.23f), trim, workshop);
                Shape("Pipe collar", PrimitiveType.Cylinder, cylinder.transform.position + Vector3.up*.7f,
                    new Vector3(.33f,.1f,.33f), bronze, workshop);
            }
            Box("Stone inspection pedestal", new Vector3(17,.55f,0), new Vector3(2.4f,1.1f,2.4f), cluster[0,5], workshop);
            Box("Woven inspection mat",new Vector3(19.2f,1.14f,6.2f),new Vector3(1.7f,.06f,.85f),cluster[3,5],workshop);
            Shape("Metal curved specimen", PrimitiveType.Sphere, new Vector3(17,1.6f,0), Vector3.one, surfaces[2,2], workshop);
            Text("Sphere caution", "CURVED UV STRESS TEST", new Vector3(17,.7f,-1.215f), .04f, Color.white, workshop);
            Text("Surface history heading","03 / SURFACE HISTORY",new Vector3(18,4.08f,-5.77f),.1f,Color.white,workshop,180);
            string[] titles={"MASONRY / GRIME","OAK / FINISH","PAINT / STEEL","WEAVE / DIRT"};
            string[] labels={"DETAIL","WEAR","LAYERS"};
            for(int material=0;material<4;++material)
            {
                float center=12.7f+3.55f*material;
                Box("Surface history backing",new Vector3(center,2.25f,-5.65f),new Vector3(3.35f,2.7f,.1f),charcoal,workshop);
                Text("Cluster material title",titles[material],new Vector3(center,3.45f,-5.55f),.052f,Color.white,workshop,180);
                for(int stage=0;stage<3;++stage)
                {
                    // Reverse order on the south wall so left-to-right is detail/wear/layers.
                    float x=center+(1-stage)*1.06f;
                    var sample=Shape("Cluster "+titles[material]+" "+labels[stage],PrimitiveType.Quad,
                        new Vector3(x,2.25f,-5.49f),new Vector3(.97f,1.55f,1),cluster[material,stage+3],workshop);
                    sample.transform.rotation=Quaternion.Euler(0,180,0);
                    Text("Cluster stage",labels[stage],new Vector3(x,1.27f,-5.50f),.045f,Color.white,workshop,180);
                }
                Box("Cluster specimen shelf",new Vector3(center,.55f,-5.05f),new Vector3(3.3f,1.1f,.95f),trim,workshop);
            }
            Text("Cluster limits","WEAR: RED / CHIPPING   GREEN / GRIME   BLUE / CURVATURE\nCabinet borders use an authored mesh-face mask. Relief leaves silhouettes unchanged.",
                new Vector3(18,.30f,-4.54f),.030f,new Color(.75f,.86f,.8f),workshop,180);
        }
        private static void Crate(Vector3 center, float size)
        {
            Box("Oak cargo crate", center, Vector3.one * size, cluster[1,5], workshop);
            foreach (float x in new[] {-.42f,.42f}) foreach (float z in new[] {-.51f,.51f})
                Box("Crate strap", center + new Vector3(x,0,z)*size, new Vector3(.08f,1.02f,.025f)*size, trim, workshop);
            foreach (float y in new[] {-.42f,.42f})
                Box("Crate face rail", center + new Vector3(0,y,-.52f)*size, new Vector3(1.03f,.10f,.05f)*size, bronze, workshop);
        }
        private static Light Lamp(string name, LightType type, Vector3 position, Color color, float intensity, float range)
        {
            var gameObject = new GameObject(name); gameObject.transform.position = position;
            var light = gameObject.AddComponent<Light>(); light.type = type; light.color = color;
            light.intensity = intensity; light.range = range; light.shadows = LightShadows.Soft;
            light.shadowBias = .035f; light.shadowNormalBias = .15f; return light;
        }
        private static void ConfigureLighting()
        {
            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(.32f,.39f,.46f);
            RenderSettings.ambientEquatorColor = new Color(.15f,.18f,.19f);
            RenderSettings.ambientGroundColor = new Color(.07f,.075f,.08f);
            var sun = Lamp("Fixed daylight", LightType.Directional, new Vector3(0,5,0), new Color(.95f,.97f,1), 1.4f, 50);
            sun.transform.rotation = Quaternion.Euler(48,-32,0); RenderSettings.sun = sun;
            for (int i = 0; i < 4; ++i)
            {
                float x = -7.2f + i * 4.8f;
                var light = Lamp("Gallery wash", LightType.Spot, new Vector3(x,4.1f,6.5f), new Color(1,.88f,.72f), 5, 9);
                light.spotAngle = 88; light.innerSpotAngle = 55; light.transform.LookAt(new Vector3(x,2.1f,9.7f));
            }
            Lamp("Workshop cool fill", LightType.Point, new Vector3(22,3.3f,1), new Color(.45f,.72f,1), 3.5f, 11);
            var softFill = Lamp("Workshop soft fill", LightType.Point, new Vector3(15.8f,3.6f,3.6f), new Color(.76f,.85f,1), 12, 13);
            softFill.shadows = LightShadows.None;
            for(int i=0;i<4;++i)
            {
                float x=12.7f+3.55f*i;
                var wash=Lamp("Surface history wash",LightType.Spot,new Vector3(x,3.8f,-2.8f),new Color(1,.94f,.85f),24,7);
                wash.spotAngle=100; wash.innerSpotAngle=65;
                wash.transform.LookAt(new Vector3(x,2.2f,-5.5f));
            }
            var cabinetLight=Lamp("Cabinet inspection fill",LightType.Spot,new Vector3(21.1f,3.5f,3.5f),new Color(.9f,.95f,1),22,8);
            cabinetLight.spotAngle=95; cabinetLight.innerSpotAngle=60;
            cabinetLight.transform.LookAt(new Vector3(23,1.5f,6.5f));
            var taskLight = Lamp("Moving amber task light", LightType.Spot, Vector3.zero, new Color(1,.74f,.40f), 15, 13);
            taskLight.spotAngle = 100; taskLight.innerSpotAngle = 45;
            var animation = taskLight.gameObject.AddComponent<LabLighting>(); animation.ApplyPhase(0);
            var volume = new GameObject("Lab exposure").AddComponent<Volume>(); volume.isGlobal = true;
            string profilePath = Root + "/Settings/LabVolume.asset";
            var profile = AssetDatabase.LoadAssetAtPath<VolumeProfile>(profilePath);
            if (profile == null)
            {
                profile = ScriptableObject.CreateInstance<VolumeProfile>(); AssetDatabase.CreateAsset(profile, profilePath);
                var tonemapping = profile.Add<Tonemapping>(true); tonemapping.mode.Override(TonemappingMode.ACES);
                AssetDatabase.AddObjectToAsset(tonemapping, profile);
            }
            volume.sharedProfile = profile;
        }
    }
}
