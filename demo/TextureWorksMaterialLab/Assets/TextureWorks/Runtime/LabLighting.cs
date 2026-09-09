using UnityEngine;

namespace TextureWorks.MaterialLab
{
    public sealed class LabLighting : MonoBehaviour
    {
        public bool animate = true;
        public float phase;
        public Vector3 center = new Vector3(18, 3.8f, 4);
        public Vector3 target = new Vector3(18, 1, 6);
        private void Update() { if (animate) phase += Time.deltaTime * .42f; ApplyPhase(phase); }
        public void ApplyPhase(float value)
        {
            phase = value;
            transform.position = center + new Vector3(Mathf.Sin(value) * 3.4f, 0, Mathf.Cos(value) * 1.2f);
            transform.LookAt(target);
        }
    }
}
