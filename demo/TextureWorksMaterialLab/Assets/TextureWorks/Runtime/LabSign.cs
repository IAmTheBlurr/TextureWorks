using UnityEngine;

namespace TextureWorks.MaterialLab
{
    /// <summary>Bind the dynamic font atlas to a depth-tested world-space sign.</summary>
    [ExecuteAlways, RequireComponent(typeof(TextMesh))]
    public sealed class LabSign : MonoBehaviour
    {
        public Shader shader;
        private Material material;
        private TextMesh text;
        private void OnEnable()
        {
            text = GetComponent<TextMesh>();
            if (shader == null || text.font == null) return;
            material = new Material(shader) {hideFlags = HideFlags.HideAndDontSave};
            GetComponent<MeshRenderer>().sharedMaterial = material;
        }
        private void OnWillRenderObject()
        {
            if (material != null && text.font != null) material.mainTexture = text.font.material.mainTexture;
        }
        private void OnDisable()
        {
            if (material == null) return;
            if (text != null && text.font != null) GetComponent<MeshRenderer>().sharedMaterial = text.font.material;
            if (Application.isPlaying) Destroy(material); else DestroyImmediate(material);
            material = null;
        }
    }
}
