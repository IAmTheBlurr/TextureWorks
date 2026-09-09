using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Unity.Pipeline.Commands;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace TextureWorks.MaterialLab.Editor
{
    [InitializeOnLoad]
    public static class LabValidation
    {
        private static int warmupFrames;
        static LabValidation() { EditorApplication.update += TickBatch; }

        // A bounded CLI session is useful on machines without an interactive editor.
        public static void OpenAutomationSession()
        {
            if (!Application.isBatchMode) throw new InvalidOperationException("Use Batch Mode for an automation session.");
            EditorSceneManager.OpenScene(LabBuilder.ScenePath);
            SessionState.SetFloat("TextureWorks.AutomationExpiry", (float)EditorApplication.timeSinceStartup + 300);
            EditorApplication.isPlaying = true;
        }
        [CliCommand("lab_finish_automation", "Close a dedicated batch automation session. Never closes an interactive editor.", Tags = new[] {"textureworks"})]
        public static string FinishAutomation()
        {
            if (!Application.isBatchMode || SessionState.GetFloat("TextureWorks.AutomationExpiry",0) <= 0)
                throw new InvalidOperationException("This is not a dedicated batch automation session.");
            EditorApplication.delayCall += () => EditorApplication.Exit(0);
            return "Automation session finished";
        }

        // Batch Mode can validate with a real GPU independently of the editor UI.
        public static void RunBatch()
        {
            EditorSceneManager.OpenScene(LabBuilder.ScenePath);
            if (!Environment.GetCommandLineArgs().Contains("-twSkipBuild")) BuildWindows();
            SessionState.SetBool("TextureWorks.LabBatch", true);
            EditorApplication.isPlaying = true;
        }
        private static void TickBatch()
        {
            float expiry = SessionState.GetFloat("TextureWorks.AutomationExpiry",0);
            if (Application.isBatchMode && expiry > 0 && EditorApplication.timeSinceStartup > expiry)
            { EditorApplication.Exit(0); return; }
            if (!SessionState.GetBool("TextureWorks.LabBatch", false) || !EditorApplication.isPlaying) return;
            if (++warmupFrames < 30) return;
            SessionState.SetBool("TextureWorks.LabBatch", false);
            try { Validate(); Debug.Log("TEXTUREWORKS_LAB_VALIDATION_PASSED"); EditorApplication.Exit(0); }
            catch (Exception exception) { Debug.LogException(exception); EditorApplication.Exit(1); }
        }
        [CliCommand("lab_view", "Set a lab viewpoint (0-3) and stage (-1 exhibit defaults, 0 base, 1 normal, 2 POM).", Tags = new[] {"textureworks"})]
        public static object View(int index = 0, int stage = -1)
        {
            LabController lab = UnityEngine.Object.FindAnyObjectByType<LabController>();
            if (lab == null) throw new InvalidOperationException("Open the MaterialLab scene first.");
            lab.SetView(index); lab.SetStage(stage);
            return new {index, stage, playing = Application.isPlaying};
        }

        [CliCommand("lab_validate", "Validate the running lab, capture fixed views, and exercise movement/collisions. Writes Evidence/validation.json.", Tags = new[] {"textureworks"})]
        public static object Validate()
        {
            if (!Application.isPlaying) throw new InvalidOperationException("Enter Play Mode before lab_validate.");
            var lab = UnityEngine.Object.FindAnyObjectByType<LabController>();
            if (lab == null) throw new InvalidOperationException("MaterialLab is not loaded.");
            var checks = new List<string>();
            Action<bool,string> require = (valid, message) => { if (!valid) throw new InvalidOperationException(message); checks.Add(message); };
            require(SystemInfo.graphicsDeviceType != GraphicsDeviceType.Null, "Real graphics device available");
            require(GraphicsSettings.currentRenderPipeline != null, "Scriptable render pipeline active");
            string evidence = Path.GetFullPath("Evidence"); Directory.CreateDirectory(evidence);
            var imported = new List<object>();
            foreach (string file in Directory.GetFiles(LabBuilder.Root + "/Textures", "*-height.png"))
            {
                string path = file.Replace('\\','/');
                var texture = AssetDatabase.LoadAssetAtPath<Texture2D>(path);
                var importer = (TextureImporter)AssetImporter.GetAtPath(path);
                int distinct = texture.GetPixels().Select(p => Mathf.RoundToInt(p.r * 65535)).Distinct().Count();
                require(!importer.sRGBTexture && texture.format == TextureFormat.R16 && distinct > 256,
                    Path.GetFileName(file) + " imports as linear R16 with more than 256 levels");
                imported.Add(new {file = Path.GetFileName(file), format = texture.format.ToString(), distinctLevels = distinct});
            }
            var renderers = UnityEngine.Object.FindObjectsByType<Renderer>();
            require(renderers.All(r => r.sharedMaterials.All(m => m != null && m.shader != null && m.shader.isSupported)), "Every renderer has supported materials");
            bool oldInput = lab.acceptInput, oldAnimate = lab.movingLight.animate;
            int oldStage = lab.selectedStage; float oldPhase = lab.movingLight.phase;
            bool oldAsync = ShaderUtil.allowAsyncCompilation; ShaderUtil.allowAsyncCompilation = false;
            lab.acceptInput = false; lab.movingLight.animate = false; lab.movingLight.ApplyPhase(0);
            double pomDifference = 0, lightDifference = 0;
            try
            {
                for (int i = 0; i < LabController.ViewPositions.Length; ++i)
                {
                    lab.SetView(i); lab.SetStage(-1);
                    Capture(lab.viewCamera, Path.Combine(evidence, "view-" + i + ".png"), require);
                }
                lab.SetView(1); lab.SetStage(1);
                Color32[] normals = Capture(lab.viewCamera, Path.Combine(evidence,"normal.png"), require);
                lab.SetStage(2);
                Color32[] pom = Capture(lab.viewCamera, Path.Combine(evidence,"pom.png"), require);
                pomDifference = Difference(normals, pom);
                require(pomDifference > .001, "POM changes an oblique view of the same surfaces");
                lab.SetView(2); lab.SetStage(0);
                Capture(lab.viewCamera, Path.Combine(evidence,"workshop-base.png"), require);
                lab.SetStage(1);
                Capture(lab.viewCamera, Path.Combine(evidence,"workshop-normal.png"), require);
                lab.SetStage(2); lab.movingLight.ApplyPhase(0);
                Color32[] firstLight = Capture(lab.viewCamera, Path.Combine(evidence,"light-a.png"), require);
                lab.movingLight.ApplyPhase(2.1f);
                Color32[] secondLight = Capture(lab.viewCamera, Path.Combine(evidence,"light-b.png"), require);
                lightDifference = Difference(firstLight, secondLight);
                require(lightDifference > .001, "Moving task light changes rendered workshop illumination");
                lab.SetView(0);
                var controller = lab.GetComponent<CharacterController>();
                Walk(controller, new Vector3(0,0,1));
                require(Vector2.Distance(new Vector2(lab.transform.position.x,lab.transform.position.z), new Vector2(0,1)) < .15f,
                    "Visitor walks across gallery without falling");
                Walk(controller, new Vector3(13,0,1));
                require(Mathf.Abs(lab.transform.position.x-13) < .15f && lab.transform.position.y > -.15f,
                    "Visitor passes through workshop doorway with floor collision");
                lab.SetView(0); Walk(controller, new Vector3(0,0,-8));
                require(lab.transform.position.z > -5.6f, "South wall blocks visitor movement");
                var shader = Shader.Find("TextureWorks/URP/Parallax Lit");
                string[] shaderErrors = ShaderUtil.GetShaderMessages(shader)
                    .Where(m => m.severity == UnityEditor.Rendering.ShaderCompilerMessageSeverity.Error).Select(m => m.message).ToArray();
                require(shaderErrors.Length == 0, "Rendered POM shader variants compile without errors");
                var report = new {unity = Application.unityVersion, gpu = SystemInfo.graphicsDeviceName,
                    graphicsApi = SystemInfo.graphicsDeviceType.ToString(), checks, importedHeights = imported,
                    renderers = renderers.Length, pomMeanAbsoluteDifference = pomDifference,
                    movingLightMeanAbsoluteDifference = lightDifference, captureWidth = 1440, captureHeight = 900,
                    limitations = "Camera captures exclude the HUD. Visual review and player build are separate acceptance steps."};
                File.WriteAllText(Path.Combine(evidence,"validation.json"), Newtonsoft.Json.JsonConvert.SerializeObject(report, Newtonsoft.Json.Formatting.Indented));
                return report;
            }
            finally
            {
                lab.SetView(0); lab.SetStage(oldStage); lab.acceptInput = oldInput;
                lab.movingLight.ApplyPhase(oldPhase); lab.movingLight.animate = oldAnimate;
                ShaderUtil.allowAsyncCompilation = oldAsync;
                // SetView keeps the controller's yaw/pitch consistent with the default view.
            }
        }

        private static void Walk(CharacterController controller, Vector3 target)
        {
            // Exercise the same CharacterController.Move path as keyboard walking at 60 Hz.
            for (int step = 0; step < 600; ++step)
            {
                Vector3 delta = target - controller.transform.position; delta.y = 0;
                if (delta.magnitude < .03f) break;
                controller.Move(Vector3.ClampMagnitude(delta, 2.6f / 60) + Vector3.down * (2f / 60));
            }
        }
        private static Color32[] Capture(Camera camera, string path, Action<bool,string> require)
        {
            var rt = RenderTexture.GetTemporary(1440,900,24,RenderTextureFormat.ARGB32,RenderTextureReadWrite.sRGB);
            var previousTarget = camera.targetTexture; var previousActive = RenderTexture.active;
            var image = new Texture2D(1440,900,TextureFormat.RGB24,false);
            try
            {
                camera.targetTexture = rt; camera.Render(); RenderTexture.active = rt;
                image.ReadPixels(new Rect(0,0,1440,900),0,0); image.Apply();
                Color32[] pixels = image.GetPixels32();
                require(pixels.Count(p => p.r > 220 && p.b > 220 && p.g < 40) < pixels.Length / 1000,
                    Path.GetFileName(path) + " has no significant error-magenta area");
                require(pixels.Count(p => p.r > 20 || p.g > 20 || p.b > 20) > pixels.Length / 3,
                    Path.GetFileName(path) + " is visibly illuminated");
                File.WriteAllBytes(path, image.EncodeToPNG()); return pixels;
            }
            finally
            {
                camera.targetTexture = previousTarget; RenderTexture.active = previousActive;
                RenderTexture.ReleaseTemporary(rt); UnityEngine.Object.DestroyImmediate(image);
            }
        }
        private static double Difference(Color32[] a, Color32[] b)
        {
            double sum = 0;
            for (int i = 0; i < a.Length; ++i)
                sum += Math.Abs(a[i].r-b[i].r) + Math.Abs(a[i].g-b[i].g) + Math.Abs(a[i].b-b[i].b);
            return sum / (a.Length * 3.0 * 255);
        }

        [MenuItem("TextureWorks/Build Windows player")]
        [CliCommand("lab_build_windows", "Build a Windows player under Builds/Windows. Exit Play Mode first.", Tags = new[] {"textureworks"})]
        public static object BuildWindows()
        {
            if (Application.isPlaying) throw new InvalidOperationException("Exit Play Mode before building.");
            var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions {
                scenes = new[] {LabBuilder.ScenePath}, target = BuildTarget.StandaloneWindows64,
                locationPathName = "Builds/Windows/TextureWorksMaterialLab.exe", options = BuildOptions.None
            });
            if (report.summary.result != BuildResult.Succeeded)
                throw new InvalidOperationException("Player build failed: " + report.summary.result);
            return new {result = report.summary.result.ToString(), bytes = report.summary.totalSize,
                errors = report.summary.totalErrors, warnings = report.summary.totalWarnings};
        }
    }
}
