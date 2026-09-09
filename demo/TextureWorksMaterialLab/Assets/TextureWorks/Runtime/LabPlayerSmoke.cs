using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace TextureWorks.MaterialLab
{
    /// <summary>Opt-in player acceptance probe; normal launches only run the demo.</summary>
    public sealed class LabPlayerSmoke : MonoBehaviour
    {
        private readonly List<string> errors = new List<string>();
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        private static void Begin()
        {
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "-textureworks-smoke") >= 0)
                new GameObject("Player acceptance probe").AddComponent<LabPlayerSmoke>();
        }
        private void OnEnable() { Application.logMessageReceived += ObserveLog; }
        private void OnDisable() { Application.logMessageReceived -= ObserveLog; }
        private void ObserveLog(string message, string stack, LogType type)
        { if (type == LogType.Error || type == LogType.Exception || type == LogType.Assert) errors.Add(message); }
        private IEnumerator Start()
        {
            LabController lab = FindAnyObjectByType<LabController>();
            string directory = Path.GetDirectoryName(Application.dataPath);
            if (lab == null) { errors.Add("No lab controller in player"); WriteReport(directory); Application.Quit(1); yield break; }
            lab.acceptInput = false;
            yield return new WaitForSeconds(2);
            lab.SetView(0); lab.SetStage(-1);
            yield return new WaitForSeconds(.5f);
            ScreenCapture.CaptureScreenshot(Path.Combine(directory,"player-gallery.png"));
            yield return new WaitForSeconds(1);
            lab.SetView(2); lab.SetStage(2);
            yield return new WaitForSeconds(.5f);
            ScreenCapture.CaptureScreenshot(Path.Combine(directory,"player-workshop.png"));
            yield return new WaitForSeconds(1);
            CheckScreenshot(Path.Combine(directory,"player-gallery.png"));
            CheckScreenshot(Path.Combine(directory,"player-workshop.png"));
            WriteReport(directory); Application.Quit(errors.Count == 0 ? 0 : 1);
        }
        private void CheckScreenshot(string path)
        {
            if (!File.Exists(path)) { errors.Add("Player screenshot missing: " + Path.GetFileName(path)); return; }
            var image = new Texture2D(2,2);
            try
            {
                if (!image.LoadImage(File.ReadAllBytes(path))) { errors.Add("Invalid player screenshot"); return; }
                Color32[] pixels = image.GetPixels32(); int lit = 0, magenta = 0;
                foreach (Color32 pixel in pixels)
                {
                    if (pixel.r > 20 || pixel.g > 20 || pixel.b > 20) lit++;
                    if (pixel.r > 220 && pixel.b > 220 && pixel.g < 40) magenta++;
                }
                if (lit < pixels.Length/3 || magenta > pixels.Length/1000)
                    errors.Add("Player capture is blank or contains error magenta: " + Path.GetFileName(path));
            }
            finally { Destroy(image); }
        }
        private void WriteReport(string directory)
        {
            var report = new Report {unity = Application.unityVersion, gpu = SystemInfo.graphicsDeviceName,
                graphicsApi = SystemInfo.graphicsDeviceType.ToString(), width = Screen.width, height = Screen.height,
                errors = errors.ToArray(), success = errors.Count == 0};
            File.WriteAllText(Path.Combine(directory,"player-smoke.json"), JsonUtility.ToJson(report,true));
        }
        [Serializable] private sealed class Report
        {
            public string unity, gpu, graphicsApi;
            public int width, height;
            public string[] errors;
            public bool success;
        }
    }
}
