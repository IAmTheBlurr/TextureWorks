// Perspective rasterization provides an independent visible-surface oracle:
// dense displaced triangles, depth tested by the GPU, with no POM in that path.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

public static class TextureWorksParallaxGeometry
{
    [Serializable] public class Fixture { public string name; public int width; public float depthWorld; }
    [Serializable] public class Fixtures { public float planeSizeWorld; public Fixture[] assets; }
    [Serializable] public class Measurement
    {
        public string material, quality;
        public float angle, meanTexels, p95Texels, p99Texels, maxTexels, overOneTexelFraction, flatMeanTexels;
        public int samples, coverageDisagreement;
    }
    [Serializable] public class Report
    {
        public string environment;
        public int meshSubdivisions, renderSize;
        public string filtering = "Bilinear LOD 0, anisotropy disabled; no height mipmaps";
        public List<Measurement> measurements = new List<Measurement>();
    }
    const int Size = 384;
    // An even multiple aligns both texel centers and interpolation breakpoints
    // with mesh vertices. Odd multiples straddle those slope discontinuities.
    const int Subdivisions = 1024;
    static Material material;
    static Camera camera;
    static float planeSize;
    static readonly string Output = Path.Combine(Directory.GetCurrentDirectory(), "geometry-validation");

    static Texture2D LoadHeight(Fixture fixture)
    {
        byte[] raw = File.ReadAllBytes(Path.Combine("Assets/TextureWorks/Fixtures", fixture.name + ".height-f32"));
        int size = fixture.width;
        if (raw.Length != size * size * sizeof(float)) throw new Exception("Invalid height data size");
        var colors = new Color[size * size];
        for (int y = 0; y < size; ++y)
            for (int x = 0; x < size; ++x)
                colors[y * size + x] = new Color(BitConverter.ToSingle(raw, ((size - 1 - y) * size + x) * 4), 0, 0, 1);
        var texture = new Texture2D(size, size, TextureFormat.RFloat, false, true);
        texture.SetPixels(colors);
        texture.filterMode = FilterMode.Bilinear;
        texture.anisoLevel = 0;
        texture.wrapMode = TextureWrapMode.Clamp;
        texture.Apply();
        return texture;
    }

    static Texture2D LoadAlbedo(string name)
    {
        var texture = new Texture2D(2, 2, TextureFormat.RGBA32, false, true);
        if (!texture.LoadImage(File.ReadAllBytes(Path.Combine("Assets/TextureWorks/Fixtures", name + ".png"))))
            throw new Exception("Cannot decode albedo " + name);
        var colors = texture.GetPixels();
        for (int i = 0; i < colors.Length; ++i) colors[i] = colors[i].linear;
        texture.SetPixels(colors);
        texture.filterMode = FilterMode.Bilinear;
        texture.anisoLevel = 0;
        texture.wrapMode = TextureWrapMode.Clamp;
        texture.Apply();
        return texture;
    }

    static Mesh Surface(Texture2D height, float depth, int subdivisions)
    {
        var heights = height == null ? null : height.GetPixels();
        int heightSize = height == null ? 0 : height.width;
        int row = subdivisions + 1;
        var vertices = new Vector3[row * row];
        var uvs = new Vector2[vertices.Length];
        var indices = new int[subdivisions * subdivisions * 6];
        for (int y = 0; y <= subdivisions; ++y)
            for (int x = 0; x <= subdivisions; ++x)
            {
                var uv = new Vector2((float)x / subdivisions, (float)y / subdivisions);
                int i = y * row + x;
                uvs[i] = uv;
                float h = height == null ? 1 : SampleHeight(heights, heightSize, uv);
                vertices[i] = new Vector3((uv.x - .5f) * planeSize, (uv.y - .5f) * planeSize, -depth * (1 - h));
                if (x == subdivisions || y == subdivisions) continue;
                int k = (y * subdivisions + x) * 6;
                indices[k] = i; indices[k+1] = i+1; indices[k+2] = i+row;
                indices[k+3] = i+1; indices[k+4] = i+row+1; indices[k+5] = i+row;
            }
        var mesh = new Mesh { indexFormat = IndexFormat.UInt32 };
        mesh.vertices = vertices; mesh.uv = uvs; mesh.triangles = indices;
        mesh.RecalculateBounds();
        return mesh;
    }

    static float SampleHeight(Color[] heights, int size, Vector2 uv)
    {
        // GPU bilinear filtering puts texel centers at (index + .5) / size.
        // Explicit interpolation avoids Texture2D.GetPixelBilinear's CPU offset.
        float x = uv.x * size - .5f, y = uv.y * size - .5f;
        int ix = Mathf.FloorToInt(x), iy = Mathf.FloorToInt(y);
        int x0 = Mathf.Clamp(ix, 0, size-1), x1 = Mathf.Clamp(ix+1, 0, size-1);
        int y0 = Mathf.Clamp(iy, 0, size-1), y1 = Mathf.Clamp(iy+1, 0, size-1);
        return Mathf.Lerp(Mathf.Lerp(heights[y0*size+x0].r, heights[y0*size+x1].r, x-ix),
                          Mathf.Lerp(heights[y1*size+x0].r, heights[y1*size+x1].r, x-ix), y-iy);
    }

    static void SetCamera(float angle, float depth)
    {
        float rad = angle * Mathf.Deg2Rad;
        camera.transform.position = new Vector3(Mathf.Sin(rad) * 3.6f, .55f, Mathf.Cos(rad) * 3.6f);
        camera.transform.LookAt(new Vector3(0, 0, -depth * .4f));
        camera.fieldOfView = 45;
        camera.aspect = 1;
        camera.nearClipPlane = .1f;
        camera.farClipPlane = 20;
        material.SetMatrix("_ObjectToClip", GL.GetGPUProjectionMatrix(camera.projectionMatrix, true) * camera.worldToCameraMatrix);
        material.SetVector("_CameraPosition", camera.transform.position);
    }

    static Texture2D Render(Mesh mesh, int mode, bool diagnostic)
    {
        material.SetInt("_Mode", mode);
        material.SetInt("_Diagnostic", diagnostic ? 1 : 0);
        var target = RenderTexture.GetTemporary(Size, Size, 24, RenderTextureFormat.ARGBFloat, RenderTextureReadWrite.Linear);
        var previous = RenderTexture.active;
        try
        {
            RenderTexture.active = target;
            GL.Clear(true, true, diagnostic ? Color.clear : new Color(.075f, .09f, .115f, 0));
            if (!material.SetPass(0)) throw new Exception("Geometry shader pass failed");
            Graphics.DrawMeshNow(mesh, Matrix4x4.identity);
            var result = new Texture2D(Size, Size, TextureFormat.RGBAFloat, false, true);
            result.ReadPixels(new Rect(0, 0, Size, Size), 0, 0);
            result.Apply();
            return result;
        }
        finally { RenderTexture.active = previous; RenderTexture.ReleaseTemporary(target); }
    }

    static void Save(Texture2D image, string name)
    {
        var rgb = new Texture2D(Size, Size, TextureFormat.RGB24, false, true);
        rgb.SetPixels(image.GetPixels()); rgb.Apply();
        File.WriteAllBytes(Path.Combine(Output, name + ".png"), rgb.EncodeToPNG());
        UnityEngine.Object.DestroyImmediate(rgb);
        UnityEngine.Object.DestroyImmediate(image);
    }

    static bool Interior(Color color)
    {
        return color.a > .5f && color.r > .08f && color.r < .92f && color.g > .08f && color.g < .92f;
    }

    static Measurement Compare(Fixture fixture, float angle, string quality, Texture2D flat, Texture2D pom, Texture2D reference)
    {
        var p = pom.GetPixels(); var g = reference.GetPixels(); var f = flat.GetPixels();
        var errors = new List<float>();
        var heat = new Color[p.Length];
        double total = 0, flatTotal = 0;
        int overOne = 0, disagreement = 0;
        for (int i = 0; i < p.Length; ++i)
        {
            if ((p[i].a > .5f) != (g[i].a > .5f)) ++disagreement;
            heat[i] = new Color(.075f, .09f, .115f);
            // Crop the shared UV interior because POM cannot extend a silhouette.
            // Count all coverage disagreements separately, including those edges.
            if (!Interior(g[i]) || !Interior(p[i]) || f[i].a < .5f) continue;
            float e = Vector2.Distance(new Vector2(p[i].r, p[i].g), new Vector2(g[i].r, g[i].g)) * fixture.width;
            float fe = Vector2.Distance(new Vector2(f[i].r, f[i].g), new Vector2(g[i].r, g[i].g)) * fixture.width;
            if (float.IsNaN(e) || float.IsInfinity(e)) throw new Exception("Non-finite render");
            errors.Add(e); total += e; flatTotal += fe;
            if (e > 1) ++overOne;
            heat[i] = Color.Lerp(new Color(.02f, .16f, .2f), new Color(1, .14f, .035f), Mathf.Clamp01(e));
        }
        if (errors.Count < 1000) throw new Exception("Insufficient shared surface coverage");
        errors.Sort();
        var m = new Measurement { material = fixture.name, quality = quality, angle = angle, samples = errors.Count,
            meanTexels = (float)(total / errors.Count), p95Texels = errors[(int)(errors.Count * .95)],
            p99Texels = errors[(int)(errors.Count * .99)], maxTexels = errors[errors.Count - 1],
            overOneTexelFraction = (float)overOne / errors.Count, flatMeanTexels = (float)(flatTotal / errors.Count),
            coverageDisagreement = disagreement };
        var heatImage = new Texture2D(Size, Size, TextureFormat.RGBAFloat, false, true);
        heatImage.SetPixels(heat); heatImage.Apply();
        Save(heatImage, fixture.name + "-" + angle + "-" + quality + "-error");
        UnityEngine.Object.DestroyImmediate(flat); UnityEngine.Object.DestroyImmediate(pom); UnityEngine.Object.DestroyImmediate(reference);
        Debug.Log($"Geometry {fixture.name} {angle} {quality}: mean {m.meanTexels:F4} px, p99 {m.p99Texels:F4}, >1px {m.overOneTexelFraction:P3}");
        return m;
    }

    public static void Run()
    {
        CultureInfo.CurrentCulture = CultureInfo.InvariantCulture;
        Directory.CreateDirectory(Output);
        // A geometric height field corresponds to bilinear LOD 0. Forced
        // anisotropy changes that field with view angle even without mipmaps.
        QualitySettings.anisotropicFiltering = AnisotropicFiltering.Disable;
        var fixtures = JsonUtility.FromJson<Fixtures>(File.ReadAllText("Assets/TextureWorks/Fixtures/fixtures.json"));
        planeSize = fixtures.planeSizeWorld;
        var shader = Shader.Find("Hidden/TextureWorks/ParallaxGeometry");
        if (shader == null || !shader.isSupported || ShaderUtil.ShaderHasError(shader)) throw new Exception("Geometry shader unavailable");
        material = new Material(shader);
        camera = new GameObject("POM validation camera").AddComponent<Camera>();
        camera.enabled = false;
        material.SetFloat("_PlaneSize", planeSize);
        material.SetFloat("_MinSteps", 16); material.SetFloat("_MaxSteps", 64);
        var plane = Surface(null, 0, 1);
        var report = new Report { environment = $"Unity {Application.unityVersion}; {SystemInfo.graphicsDeviceName}; {SystemInfo.graphicsDeviceType}",
            meshSubdivisions = Subdivisions, renderSize = Size };
        foreach (var fixture in fixtures.assets)
        {
            var height = LoadHeight(fixture); var albedo = LoadAlbedo(fixture.name);
            material.SetTexture("_HeightMap", height); material.SetTexture("_Albedo", albedo);
            material.SetVector("_HeightMap_TexelSize", new Vector4(1f / height.width, 1f / height.height, height.width, height.height));
            material.SetFloat("_DepthWorld", fixture.depthWorld);
            var mesh = Surface(height, fixture.depthWorld, Subdivisions);
            foreach (float angle in new[] { 0f, 35f, 60f, 75f, -60f })
            {
                SetCamera(angle, fixture.depthWorld);
                foreach (int maximum in new[] { 64, 128 })
                {
                    material.SetFloat("_MinSteps", maximum / 4); material.SetFloat("_MaxSteps", maximum);
                    var m = Compare(fixture, angle, maximum == 64 ? "default" : "high",
                        Render(plane, 0, true), Render(plane, 1, true), Render(mesh, 2, true));
                    report.measurements.Add(m);
                }
                material.SetFloat("_MinSteps", 16); material.SetFloat("_MaxSteps", 64);
                foreach (int mode in new[] { 0, 1, 2 })
                    Save(Render(mode == 2 ? mesh : plane, mode, false), fixture.name + "-" + angle + "-" + new[] { "flat", "pom", "mesh" }[mode]);
            }
            // A camera sweep exposes stepping and view-direction mistakes that a
            // single still can hide. Each frame has independently rendered paths.
            for (int frame = 0; frame < 25; ++frame)
            {
                float angle = -65 + frame * (130f / 24);
                SetCamera(angle, fixture.depthWorld);
                report.measurements.Add(Compare(fixture, angle, "motion-default",
                    Render(plane, 0, true), Render(plane, 1, true), Render(mesh, 2, true)));
                for (int mode = 0; mode < 3; ++mode)
                    Save(Render(mode == 2 ? mesh : plane, mode, false), $"{fixture.name}-motion-{frame:D2}-{mode}");
            }
            UnityEngine.Object.DestroyImmediate(mesh); UnityEngine.Object.DestroyImmediate(height); UnityEngine.Object.DestroyImmediate(albedo);
        }
        File.WriteAllText(Path.Combine(Output, "report.json"), JsonUtility.ToJson(report, true));
        foreach (var message in ShaderUtil.GetShaderMessages(shader))
            if (message.severity == UnityEditor.Rendering.ShaderCompilerMessageSeverity.Error) throw new Exception(message.message);
        foreach (var m in report.measurements)
            if (m.meanTexels > .05f || m.p99Texels > .25f || m.overOneTexelFraction > .001f)
                throw new Exception($"Geometry mismatch: {m.material}, {m.angle} degrees, {m.quality}; inspect report.json");
        UnityEngine.Object.DestroyImmediate(plane); UnityEngine.Object.DestroyImmediate(material); UnityEngine.Object.DestroyImmediate(camera.gameObject);
    }
}
