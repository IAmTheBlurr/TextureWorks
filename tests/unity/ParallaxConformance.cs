// Run in a disposable Unity project using scripts/test-unity-parallax.ps1.
// This renders the shipped Shader Graph function with real Unity texture structs.
using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

public static class TextureWorksParallaxConformance
{
    static readonly List<string> Passed = new List<string>();
    static Material material;

    static Texture2D Height(Func<float, float, float> sample, int size = 256)
    {
        var texture = new Texture2D(size, size, TextureFormat.RFloat, false, true);
        texture.filterMode = FilterMode.Bilinear;
        texture.wrapMode = TextureWrapMode.Clamp;
        var pixels = new Color[size * size];
        for (int y = 0; y < size; ++y)
            for (int x = 0; x < size; ++x)
                pixels[y * size + x] = new Color(sample((x + .5f) / size, (y + .5f) / size), 0, 0, 1);
        texture.SetPixels(pixels);
        texture.Apply();
        return texture;
    }

    static Texture2D Render(Texture2D height, int width = 4, int heightPixels = 4)
    {
        material.SetTexture("_HeightMap", height);
        material.SetVector("_HeightMap_TexelSize", new Vector4(1f / height.width, 1f / height.height, height.width, height.height));
        var target = RenderTexture.GetTemporary(width, heightPixels, 0, RenderTextureFormat.ARGBFloat, RenderTextureReadWrite.Linear);
        var previous = RenderTexture.active;
        try
        {
            RenderTexture.active = target;
            GL.Clear(false, true, Color.magenta);
            if (!material.SetPass(0)) throw new Exception("Conformance shader pass failed");
            Graphics.DrawProceduralNow(MeshTopology.Triangles, 3);
            var result = new Texture2D(width, heightPixels, TextureFormat.RGBAFloat, false, true);
            result.ReadPixels(new Rect(0, 0, width, heightPixels), 0, 0);
            result.Apply();
            return result;
        }
        finally
        {
            RenderTexture.active = previous;
            RenderTexture.ReleaseTemporary(target);
        }
    }

    static void Configure(Vector2 uv, Vector3 view, Vector2 scale, float distance = 0,
                          float fadeStart = 10, float fadeEnd = 20,
                          float minSteps = 16, float maxSteps = 64, float refinements = 6)
    {
        material.SetVector("_TestUV", new Vector4(uv.x, uv.y, 0, 0));
        material.SetVector("_ViewDirection", new Vector4(view.x, view.y, view.z, 0));
        material.SetVector("_HeightScale", new Vector4(scale.x, scale.y, 0, 0));
        material.SetVector("_Steps", new Vector4(minSteps, maxSteps, refinements, 0));
        material.SetVector("_Fade", new Vector4(distance, fadeStart, fadeEnd, 0));
        material.SetInt("_Preview", 0);
    }

    static void Check(string name, Texture2D height, Vector2 uv, float depth,
                      float inside = 1, float tolerance = 0.00003f)
    {
        var result = Render(height);
        try
        {
            var actual = result.GetPixel(2, 2);
            var expected = new Color(uv.x, uv.y, depth, inside);
            for (int channel = 0; channel < 4; ++channel)
                if (float.IsNaN(actual[channel]) || float.IsInfinity(actual[channel]) ||
                    Mathf.Abs(actual[channel] - expected[channel]) > tolerance)
                    throw new Exception($"{name}: channel {channel}, expected {expected}, got {actual}");
            Passed.Add(name);
        }
        finally { UnityEngine.Object.DestroyImmediate(result); }
    }

    public static void Run()
    {
        try
        {
            if (SystemInfo.graphicsDeviceType == GraphicsDeviceType.Null)
                throw new Exception("A real graphics device is required; omit -nographics");
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            var shader = Shader.Find("Hidden/TextureWorks/ParallaxConformance");
            if (shader == null || !shader.isSupported || ShaderUtil.ShaderHasError(shader))
                throw new Exception("Shader missing, unsupported, or failed compilation");
            material = new Material(shader);
            var center = new Vector2(.5f, .5f);
            var view = new Vector3(.6f, .2f, 1);
            var scale = new Vector2(.2f, .3f);
            var ray = new Vector2(.12f, .06f);

            foreach (float h in new[] { 0f, .25f, .5f, 1f })
            {
                var plane = Height((x, y) => h);
                Configure(center, view, scale);
                Check($"constant height {h}", plane, center - ray * (1 - h), 1 - h);
                UnityEngine.Object.DestroyImmediate(plane);
            }
            var flat = Height((x, y) => .25f);
            // Adjacent 16-bit height codes must survive the runtime sampler.
            foreach (ushort code in new ushort[] { 32767, 32768 })
            {
                var precise = new Texture2D(4, 4, TextureFormat.R16, false, true);
                precise.SetPixelData(new ushort[] {
                    code, code, code, code, code, code, code, code,
                    code, code, code, code, code, code, code, code }, 0);
                precise.Apply();
                Configure(center, view, scale);
                float depth16 = 1 - code / 65535f;
                Check($"R16 code {code}", precise, center - ray * depth16, depth16, tolerance: .000002f);
                UnityEngine.Object.DestroyImmediate(precise);
            }
            Configure(center, Vector3.forward, scale);
            Check("normal incidence", flat, center, .75f);
            Configure(center, -view, scale);
            Check("back face bypass", flat, center, 0);
            Configure(center, Vector3.zero, scale);
            Check("zero view bypass", flat, center, 0);
            Configure(center, new Vector3(1, 0, .001f), scale);
            Check("grazing bypass", flat, center, 0);
            var grazingView = new Vector3(Mathf.Sqrt(1 - .06f * .06f), 0, .06f);
            Configure(center, grazingView, new Vector2(.02f, .02f));
            Check("angular fade halfway", flat,
                center - new Vector2(grazingView.x / grazingView.z * .01f * .75f, 0), .75f);
            Configure(center, view, Vector2.zero);
            Check("zero scale bypass", flat, center, 0);
            Configure(center, view, -scale);
            Check("negative scale bypass", flat, center, 0);
            Configure(center, view, scale, distance: 20);
            Check("distance bypass", flat, center, 0);
            Configure(center, view, scale, distance: 15);
            Check("distance halfway", flat, center - ray * .375f, .75f);
            Configure(center, view, scale, distance: 100, fadeStart: 5, fadeEnd: 5);
            Check("disabled distance fade", flat, center - ray * .75f, .75f);
            Configure(center, view, scale, minSteps: -10, maxSteps: 1000, refinements: 100);
            Check("bounded controls", flat, center - ray * .75f, .75f);
            Configure(center, view, scale, minSteps: 60, maxSteps: 2, refinements: 0);
            Check("reversed step controls", flat, center - ray * .75f, .75f);
            var edgeUV = new Vector2(.01f, .5f);
            Configure(edgeUV, view, scale);
            Check("UV leaves texture", flat, edgeUV - ray * .75f, .75f, inside: 0);

            // Independent analytic intersection: d = 1 - (a * (u - ray*d) + b).
            var ramp = Height((x, y) => .2f + .6f * x);
            float rampDepth = (1 - (.2f + .6f * center.x)) / (1 - .6f * ray.x);
            Configure(center, view, scale);
            Check("linear ramp intersection", ramp, center - ray * rampDepth, rampDepth);
            Configure(center, new Vector3(-.6f, -.2f, 1), scale);
            rampDepth = (1 - (.2f + .6f * center.x)) / (1 + .6f * ray.x);
            Check("reversed ray direction", ramp, center + ray * rampDepth, rampDepth);

            // Repeating texture sample at u=1.5 matches a sample at u=.5, with
            // the output coordinates intentionally outside [0,1].
            ramp.wrapMode = TextureWrapMode.Repeat;
            Configure(new Vector2(1.5f, .5f), view, scale);
            rampDepth = .5f / (1 - .6f * ray.x);
            Check("repeat sampler", ramp, new Vector2(1.5f, .5f) - ray * rampDepth, rampDepth, inside: 0);
            ramp.wrapMode = TextureWrapMode.Clamp;
            var outside = new Vector2(-.1f, .5f);
            Configure(outside, view, scale);
            float clampedDepth = 1 - (.2f + .6f * .5f / ramp.width);
            Check("clamp sampler", ramp, outside - ray * clampedDepth, clampedDepth, inside: 0);

            // At the rising ledge, the first visible surface is the filtered edge,
            // not the bottom plane behind it. The exact root is inside its texel.
            var ledge = Height((x, y) => x < .5f ? .85f : .15f);
            Configure(new Vector2(.6f, .5f), new Vector3(1, 0, 1), new Vector2(.4f, .4f));
            // Bilinear height at the edge: h = .5 - .7*256*(u-.5).
            float ledgeDepth = (.5f + .7f * 256 * .1f) / (1 + .7f * 256 * .4f);
            Check("first ledge intersection", ledge, new Vector2(.6f - .4f * ledgeDepth, .5f), ledgeDepth);

            var panels = Height((x, y) =>
            {
                float px = Mathf.Repeat(x * 5 + ((int)(y * 5) % 2) * .5f, 1);
                float py = Mathf.Repeat(y * 5, 1);
                float bevel = Mathf.Clamp01(Mathf.Min(Mathf.Min(px, 1-px), Mathf.Min(py, 1-py)) * 12);
                return .1f + .7f * bevel;
            });
            Configure(center, new Vector3(1.2f, .4f, 1), new Vector2(.12f, .12f));
            material.SetInt("_Preview", 1);
            var preview = Render(panels, 1024, 512);
            var rgb = new Texture2D(1024, 512, TextureFormat.RGB24, false, true);
            rgb.SetPixels(preview.GetPixels());
            rgb.Apply();
            File.WriteAllBytes("parallax-preview.png", rgb.EncodeToPNG());

            foreach (var message in ShaderUtil.GetShaderMessages(shader))
                if (message.severity == UnityEditor.Rendering.ShaderCompilerMessageSeverity.Error)
                    throw new Exception(message.message);
            File.WriteAllText("parallax-results.txt",
                $"Unity {Application.unityVersion}; {SystemInfo.graphicsDeviceName}; {SystemInfo.graphicsDeviceType}\n" +
                string.Join("\n", Passed) + $"\nPASS: {Passed.Count} GPU checks\n");
            Debug.Log($"TextureWorks: {Passed.Count} GPU checks passed");
            EditorApplication.Exit(0);
        }
        catch (Exception error)
        {
            File.WriteAllText("parallax-results.txt", "FAIL: " + error + "\n");
            Debug.LogException(error);
            EditorApplication.Exit(1);
        }
    }
}
