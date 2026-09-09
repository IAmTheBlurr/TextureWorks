using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using UnityEditor;
using UnityEngine;

namespace TextureWorks.Editor
{
    // A typed enum avoids the fixed argument limit of MaterialEnumDrawer.
    public enum MaterialDebugView
    { Lit, Height, Mask, Curvature, Edge, Cavity, Weight, Normal, Albedo, Roughness, Metallic, AO }

    [Serializable] public sealed class BundleTexture
    {
        public int layer, width, height, bits;
        public string role, path, sha256, channels, color_space, encoding, normal_convention, origin;
    }
    [Serializable] public sealed class BundleLayer { public string name; public bool normal_authored; }
    [Serializable] public sealed class BundleDetail
    {
        public string boundary;
        public float[] physical_size;
        public float tiling, color_strength, normal_strength, roughness_strength, fade_start, fade_end;
    }
    [Serializable] public sealed class BundleComposition
    {
        public float coverage, blend_width, height_bias;
        public string quality;
    }
    [Serializable] public sealed class MaterialBundle
    {
        public int schema_version, width, height, anisotropy;
        public string profile, name, boundary, filter;
        public float height_reference, relief_depth;
        public float[] physical_size;
        public BundleLayer[] layers;
        public BundleTexture[] textures;
        public BundleDetail detail;
        public BundleComposition composition;
    }

    /// <summary>Explicit setup of versioned bundles. Independent of the Material Lab.</summary>
    public static class TextureWorksBundleImporter
    {
        public const string ShaderName = "TextureWorks/URP/Layered Lit";
        private static readonly HashSet<string> ScalarRoles = new HashSet<string> {
            "height","roughness","metallic","ao","curvature","edge","cavity","mask","preview_height","preview_weight"};
        private static readonly HashSet<string> ColorRoles = new HashSet<string> {
            "albedo","normal","detail_color","detail_normal","wear"};

        [MenuItem("TextureWorks/Set up selected material bundle")]
        public static void SetupSelection()
        {
            string path = AssetDatabase.GetAssetPath(Selection.activeObject);
            Material material = Import(path);
            Selection.activeObject = material;
            EditorGUIUtility.PingObject(material);
        }

        private static bool Finite(float value) => !float.IsNaN(value) && !float.IsInfinity(value);
        private static void Require(bool condition, string message)
        { if (!condition) throw new InvalidDataException("TextureWorks bundle: " + message); }
        private static void Range(float value,float minimum,float maximum,string name) =>
            Require(Finite(value) && value >= minimum && value <= maximum,"invalid " + name);
        private static void Size(float[] value,string name)
        {
            Require(value != null && value.Length == 2,name + " requires width and height in meters");
            foreach(float v in value) Range(v,.0001f,10000,name);
        }
        private static uint BigEndian(byte[] bytes,int offset) =>
            ((uint)bytes[offset]<<24)|((uint)bytes[offset+1]<<16)|((uint)bytes[offset+2]<<8)|bytes[offset+3];

        public static MaterialBundle Validate(string manifestPath)
        {
            Require(File.Exists(manifestPath),"select material.json inside a complete bundle");
            MaterialBundle bundle = JsonUtility.FromJson<MaterialBundle>(File.ReadAllText(manifestPath));
            Require(bundle != null && bundle.schema_version == 1 && bundle.profile == "textureworks-urp-two-material-v1",
                "unsupported schema version or profile");
            Require(bundle.layers != null && bundle.layers.Length >= 1 && bundle.layers.Length <= 2,"one or two layers required");
            Require(bundle.width >= 2 && bundle.width <= 8192 && bundle.height >= 2 && bundle.height <= 8192,"unsupported dimensions");
            Require(bundle.height_reference == 1,"height reference must be white at the mesh plane");
            Size(bundle.physical_size,"physical_size"); Range(bundle.relief_depth,0,100,"relief_depth");
            Require(bundle.boundary == "clamp" || bundle.boundary == "wrap","boundary must be clamp or wrap");
            Require(bundle.filter == "trilinear" && bundle.anisotropy == 4,"expected trilinear filtering with anisotropy 4");
            Require(bundle.detail != null && bundle.composition != null,"missing detail or composition settings");
            Size(bundle.detail.physical_size,"detail physical size");
            Require(bundle.detail.boundary == "clamp" || bundle.detail.boundary == "wrap","detail boundary must be clamp or wrap");
            Range(bundle.detail.tiling,.01f,128,"detail tiling");
            Range(bundle.detail.color_strength,0,2,"detail color strength");
            Range(bundle.detail.normal_strength,0,4,"detail normal strength");
            Range(bundle.detail.roughness_strength,0,1,"detail roughness strength");
            Range(bundle.detail.fade_start,0,10000,"detail fade start"); Range(bundle.detail.fade_end,0,10000,"detail fade end");
            Range(bundle.composition.coverage,0,1,"coverage"); Range(bundle.composition.blend_width,0,1,"blend width");
            Range(bundle.composition.height_bias,0,1,"height bias");
            Require(new[]{"low","balanced","high"}.Contains(bundle.composition.quality),"unknown quality preset");
            Require(bundle.textures != null,"missing textures");
            var roles = new HashSet<string>(); var paths = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            string directory = Path.GetFullPath(Path.GetDirectoryName(manifestPath));
            foreach (BundleTexture texture in bundle.textures)
            {
                Require(texture != null && texture.layer >= -1 && texture.layer < bundle.layers.Length,"invalid layer index");
                bool scalar = ScalarRoles.Contains(texture.role);
                Require(scalar || ColorRoles.Contains(texture.role),"unknown texture role");
                Require(roles.Add(texture.layer + ":" + texture.role) && paths.Add(texture.path),"duplicate texture role or path");
                Require(!string.IsNullOrEmpty(texture.path) && Path.GetFileName(texture.path) == texture.path
                    && !texture.path.Contains("/") && !texture.path.Contains("\\"),"texture path must be a filename");
                string path = Path.Combine(directory,texture.path);
                Require(File.Exists(path),"missing " + texture.path);
                byte[] bytes = File.ReadAllBytes(path);
                using (SHA256 hash = SHA256.Create())
                    Require(BitConverter.ToString(hash.ComputeHash(bytes)).Replace("-","").ToLowerInvariant() == texture.sha256,
                        "hash mismatch for " + texture.path);
                Require(bytes.Length >= 29 && bytes[0] == 137 && bytes[1] == 80 && bytes[2] == 78 && bytes[3] == 71,
                    "only PNG input is supported");
                Require(BigEndian(bytes,16) == texture.width && BigEndian(bytes,20) == texture.height && bytes[24] == texture.bits,
                    "PNG dimensions or precision disagree with metadata");
                Require(texture.width >= 2 && texture.width <= 8192 && texture.height >= 2 && texture.height <= 8192,"unsupported texture dimensions");
                Require(scalar ? bytes[25] == 0 && (texture.bits == 8 || texture.bits == 16) && texture.channels == "R"
                    : bytes[25] == 2 && texture.bits == 8 && texture.channels == "RGB","unsupported PNG encoding");
                if (!texture.role.StartsWith("detail_",StringComparison.Ordinal))
                    Require(texture.width == bundle.width && texture.height == bundle.height,"material dimensions differ");
                Require(texture.color_space == "linear" || (texture.role == "albedo" && texture.color_space == "srgb"),"incompatible color space");
                string encoding = texture.role == "height" ? "white-top" : texture.role == "detail_color" ? "residual-centered-unorm8" : "unorm";
                if (texture.role == "normal" || texture.role == "detail_normal")
                {
                    Require(texture.encoding == "xyz-unorm" || texture.encoding == "xyz-centered-unorm8","unsupported normal encoding");
                    Require(texture.normal_convention == "opengl" || texture.normal_convention == "directx","unknown normal convention");
                }
                else Require(texture.encoding == encoding,"incompatible encoding for " + texture.role);
            }
            for (int i = 0; i < bundle.layers.Length; ++i)
            {
                Require(bundle.layers[i] != null,"missing layer metadata");
                foreach(string role in new[]{"albedo","height","normal","roughness","metallic","ao","curvature"})
                    Require(roles.Contains(i + ":" + role),"missing layer " + i + " " + role);
                BundleTexture normal=bundle.textures.First(t=>t.layer==i && t.role=="normal");
                Require(normal.origin=="authored" || normal.origin=="generated","missing normal provenance");
                Require(bundle.layers[i].normal_authored==(normal.origin=="authored"),"normal_authored disagrees with normal provenance");
            }
            foreach(string role in new[]{"mask","edge","cavity","wear","detail_color","detail_normal"})
                Require(roles.Contains("-1:" + role),"missing " + role);
            BundleTexture detailColor=bundle.textures.First(t=>t.layer==-1 && t.role=="detail_color");
            BundleTexture detailNormal=bundle.textures.First(t=>t.layer==-1 && t.role=="detail_normal");
            Require(detailColor.width==detailNormal.width && detailColor.height==detailNormal.height,"detail color and normal dimensions differ");
            return bundle;
        }

        /// <summary>Validate hashes, enforce import settings, and create reproducible material defaults.</summary>
        public static Material Import(string manifestPath)
        {
            manifestPath = manifestPath.Replace('\\','/');
            string full = Path.GetFullPath(manifestPath);
            string assets = Path.GetFullPath(Application.dataPath) + Path.DirectorySeparatorChar;
            Require(full.StartsWith(assets,StringComparison.OrdinalIgnoreCase),"copy the complete bundle under Assets before setup");
            manifestPath = "Assets/" + full.Substring(assets.Length).Replace('\\','/');
            MaterialBundle bundle = Validate(manifestPath);
            Shader shader = Shader.Find(ShaderName);
            Require(shader != null,"Layered Lit shader is missing; install the local TextureWorks package");
            string directory = Path.GetDirectoryName(manifestPath).Replace('\\','/');
            var textures = new Dictionary<string,Texture2D>();
            foreach(BundleTexture texture in bundle.textures)
            {
                string path = directory + "/" + texture.path;
                AssetDatabase.ImportAsset(path,ImportAssetOptions.ForceSynchronousImport);
                var importer = AssetImporter.GetAtPath(path) as TextureImporter;
                Require(importer != null,"PNG importer unavailable: " + path);
                importer.textureType = TextureImporterType.Default; // Raw XYZ, decoded explicitly by this profile.
                importer.sRGBTexture = texture.color_space == "srgb";
                importer.alphaSource = TextureImporterAlphaSource.None;
                importer.textureCompression = TextureImporterCompression.Uncompressed;
                importer.npotScale = TextureImporterNPOTScale.None;
                importer.maxTextureSize = Mathf.NextPowerOfTwo(Mathf.Max(texture.width,texture.height));
                importer.mipmapEnabled = true; importer.filterMode = FilterMode.Trilinear;
                string boundary = texture.role.StartsWith("detail_",StringComparison.Ordinal) ? bundle.detail.boundary : bundle.boundary;
                importer.wrapMode = boundary == "wrap" ? TextureWrapMode.Repeat : TextureWrapMode.Clamp;
                importer.anisoLevel = 4; importer.isReadable = ScalarRoles.Contains(texture.role);
                TextureImporterFormat format = texture.channels == "R"
                    ? (texture.bits == 16 || texture.role == "height" ? TextureImporterFormat.R16 : TextureImporterFormat.R8)
                    : TextureImporterFormat.RGB24;
                var defaults = importer.GetDefaultPlatformTextureSettings();
                defaults.format = format; defaults.maxTextureSize = importer.maxTextureSize;
                importer.SetPlatformTextureSettings(defaults);
                var windows = importer.GetPlatformTextureSettings("Standalone");
                windows.overridden = true; windows.format = format; windows.maxTextureSize = importer.maxTextureSize;
                windows.textureCompression = TextureImporterCompression.Uncompressed;
                importer.SetPlatformTextureSettings(windows); importer.SaveAndReimport();
                Texture2D imported = AssetDatabase.LoadAssetAtPath<Texture2D>(path);
                Require(imported != null && imported.width == texture.width && imported.height == texture.height,"import resized texture: " + path);
                Require(format != TextureImporterFormat.R16 || imported.format == TextureFormat.R16,"R16 precision was not retained: " + path);
                textures[texture.layer + ":" + texture.role] = imported;
            }
            string materialPath = directory + "/" + bundle.name + ".mat";
            Material material = AssetDatabase.LoadAssetAtPath<Material>(materialPath);
            if (material == null) { material = new Material(shader); AssetDatabase.CreateAsset(material,materialPath); }
            material.shader = shader;
            var names = new Dictionary<string,string> { {"albedo","BaseMap"},{"height","Height"},{"normal","Normal"},
                {"roughness","Roughness"},{"metallic","Metallic"},{"ao","AO"} };
            var normalEncoding = Vector4.one; var authoredNormals = Vector4.zero;
            for(int slot=0;slot<2;++slot)
            {
                int layer = Mathf.Min(slot,bundle.layers.Length-1);
                foreach(var pair in names) material.SetTexture("_" + pair.Value + (slot == 0 ? "A" : "B"),textures[layer + ":" + pair.Key]);
                BundleTexture normal = bundle.textures.First(entry=>entry.layer == layer && entry.role == "normal");
                normalEncoding[slot] = normal.encoding == "xyz-centered-unorm8" ? 1 : 0;
                normalEncoding[slot+2] = normal.normal_convention == "directx" ? -1 : 1;
                authoredNormals[slot] = bundle.layers[layer].normal_authored ? 1 : 0;
            }
            foreach(var pair in new Dictionary<string,string> {{"mask","Mask"},{"edge","Edge"},{"cavity","Cavity"},
                        {"detail_color","DetailColor"},{"detail_normal","DetailNormal"}})
                material.SetTexture("_" + pair.Value,textures["-1:"+pair.Key]);
            material.SetTexture("_Curvature",textures["0:curvature"]);
            material.SetVector("_NormalEncoding",normalEncoding); material.SetVector("_AuthoredNormals",authoredNormals);
            material.SetVector("_TextureSize",new Vector4(bundle.physical_size[0],bundle.physical_size[1],0,0));
            material.SetVector("_DetailSize",new Vector4(bundle.detail.physical_size[0],bundle.detail.physical_size[1],0,0));
            material.SetTextureScale("_BaseMapA",Vector2.one); material.SetTextureOffset("_BaseMapA",Vector2.zero);
            material.SetFloat("_DepthMeters",bundle.relief_depth);
            material.SetFloat("_Coverage",bundle.layers.Length == 1 ? 0 : bundle.composition.coverage);
            material.SetFloat("_BlendWidth",bundle.composition.blend_width); material.SetFloat("_HeightBias",bundle.composition.height_bias);
            material.SetFloat("_DetailTiling",bundle.detail.tiling);
            material.SetFloat("_DetailColorStrength",bundle.detail.color_strength);
            material.SetFloat("_DetailNormalStrength",bundle.detail.normal_strength);
            material.SetFloat("_DetailRoughness",bundle.detail.roughness_strength);
            material.SetFloat("_DetailFadeStart",bundle.detail.fade_start); material.SetFloat("_DetailFadeEnd",bundle.detail.fade_end);
            material.SetFloat("_FadeStart",12); material.SetFloat("_FadeEnd",20);
            material.SetFloat("_Quality",bundle.composition.quality == "low" ? 0 : bundle.composition.quality == "high" ? 2 : 1);
            material.SetFloat("_Stage",5); material.SetFloat("_Debug",0);
            EditorUtility.SetDirty(material); AssetDatabase.SaveAssets();
            return material;
        }
    }
}
