using UnityEngine;
using UnityEngine.InputSystem;

namespace TextureWorks.MaterialLab
{
    /// <summary>Walk, compare the same assets, and visit repeatable observation points.</summary>
    [RequireComponent(typeof(CharacterController))]
    public sealed class LabController : MonoBehaviour
    {
        public Camera viewCamera;
        public LabLighting movingLight;
        public Material[] comparisonMaterials;
        public int[] originalStages;
        public bool showInterface = true;
        public bool acceptInput = true;
        public int selectedStage = -1;
        private CharacterController body;
        private float yaw, pitch, verticalSpeed;
        private GUIStyle title, bodyText, small;
        public static readonly Vector3[] ViewPositions = {
            new Vector3(0, 1.7f, -4), new Vector3(-6.1f, 1.75f, 7.35f),
            new Vector3(12.0f, 1.7f, -2), new Vector3(20.4f, 1.7f, 4.2f)
        };
        public static readonly Vector3[] ViewTargets = {
            new Vector3(0, 2.2f, 9), new Vector3(-7.15f, 2.4f, 9.7f),
            new Vector3(19, 1.4f, 5.6f), new Vector3(23, 1.5f, 6.8f)
        };

        private void Awake() { body = GetComponent<CharacterController>(); SetView(0); }
        private void OnDisable() { SetStage(-1); Cursor.lockState = CursorLockMode.None; Cursor.visible = true; }

        public void SetStage(int stage)
        {
            selectedStage = Mathf.Clamp(stage, -1, 2);
            for (int i = 0; i < comparisonMaterials.Length; ++i)
                if (comparisonMaterials[i] != null)
                    comparisonMaterials[i].SetFloat("_Stage", stage < 0 ? originalStages[i] : selectedStage);
        }

        public void SetView(int index)
        {
            index = Mathf.Clamp(index, 0, ViewPositions.Length - 1);
            if (body == null) body = GetComponent<CharacterController>();
            body.enabled = false;
            transform.position = ViewPositions[index] - Vector3.up * 1.65f;
            Vector3 angles = Quaternion.LookRotation(ViewTargets[index] - ViewPositions[index]).eulerAngles;
            yaw = angles.y; pitch = Mathf.DeltaAngle(0, angles.x); verticalSpeed = 0;
            transform.rotation = Quaternion.Euler(0, yaw, 0);
            viewCamera.transform.localRotation = Quaternion.Euler(pitch, 0, 0);
            body.enabled = true;
            Physics.SyncTransforms();
        }

        private void Update()
        {
            if (!acceptInput) return;
            Keyboard keyboard = Keyboard.current; Mouse mouse = Mouse.current;
            if (keyboard == null) return;
            if (keyboard.escapeKey.wasPressedThisFrame) { Cursor.lockState = CursorLockMode.None; Cursor.visible = true; }
            if (mouse != null && mouse.leftButton.wasPressedThisFrame && GUIUtility.hotControl == 0)
            { Cursor.lockState = CursorLockMode.Locked; Cursor.visible = false; }
            if (keyboard.digit0Key.wasPressedThisFrame) SetStage(-1);
            if (keyboard.digit1Key.wasPressedThisFrame) SetStage(0);
            if (keyboard.digit2Key.wasPressedThisFrame) SetStage(1);
            if (keyboard.digit3Key.wasPressedThisFrame) SetStage(2);
            if (keyboard.lKey.wasPressedThisFrame && movingLight != null) movingLight.animate = !movingLight.animate;
            if (keyboard.hKey.wasPressedThisFrame) showInterface = !showInterface;
            if (keyboard.f1Key.wasPressedThisFrame) SetView(0);
            if (keyboard.f2Key.wasPressedThisFrame) SetView(1);
            if (keyboard.f3Key.wasPressedThisFrame) SetView(2);
            if (keyboard.f4Key.wasPressedThisFrame) SetView(3);
            if (keyboard.rKey.wasPressedThisFrame || transform.position.y < -5) SetView(0);
            if (Cursor.lockState != CursorLockMode.Locked) return;
            if (mouse != null)
            {
                Vector2 delta = mouse.delta.ReadValue();
                yaw += delta.x * 0.085f; pitch = Mathf.Clamp(pitch - delta.y * 0.085f, -80, 80);
                transform.rotation = Quaternion.Euler(0, yaw, 0);
                viewCamera.transform.localRotation = Quaternion.Euler(pitch, 0, 0);
            }
            Vector2 movement = new Vector2((keyboard.dKey.isPressed ? 1 : 0) - (keyboard.aKey.isPressed ? 1 : 0),
                (keyboard.wKey.isPressed ? 1 : 0) - (keyboard.sKey.isPressed ? 1 : 0));
            Vector3 horizontal = transform.TransformDirection(new Vector3(movement.x, 0, movement.y).normalized);
            verticalSpeed = body.isGrounded && verticalSpeed < 0 ? -2 : verticalSpeed - 18 * Time.deltaTime;
            body.Move((horizontal * (keyboard.leftShiftKey.isPressed ? 5 : 2.6f) + Vector3.up * verticalSpeed) * Time.deltaTime);
        }

        private void OnGUI()
        {
            if (!showInterface) return;
            if (title == null)
            {
                title = new GUIStyle(GUI.skin.label) { fontSize = 25, fontStyle = FontStyle.Bold };
                bodyText = new GUIStyle(GUI.skin.label) { fontSize = 15 };
                small = new GUIStyle(GUI.skin.label) { fontSize = 13, wordWrap = true };
                title.normal.textColor = new Color(.9f,.95f,.91f);
                bodyText.normal.textColor = Color.white;
                small.normal.textColor = new Color(.72f,.80f,.81f);
            }
            float factor = Mathf.Min(Screen.width / 1440f, Screen.height / 900f);
            GUI.matrix = Matrix4x4.Scale(new Vector3(factor, factor, 1));
            float width = Screen.width / factor, height = Screen.height / factor;
            Color old = GUI.color; GUI.color = new Color(.055f,.075f,.08f,.96f);
            GUI.DrawTexture(new Rect(22, 20, 555, 102), Texture2D.whiteTexture);
            GUI.DrawTexture(new Rect(22, height-118, width-44, 94), Texture2D.whiteTexture);
            GUI.color = old;
            GUI.Label(new Rect(40,30,520,34), "TEXTUREWORKS  /  MATERIAL LAB", title);
            string room = transform.position.x < 10 ? "01  Surface gallery · fixed lighting" : "02  Workshop · moving task light";
            GUI.Label(new Rect(40,69,520,27), room, bodyText);
            string stage = selectedStage < 0 ? "Per-exhibit comparison" : new[] {"Base shading", "Height-derived normals", "Parallax occlusion mapping"}[selectedStage];
            GUI.Label(new Rect(40,height-108,1100,26), "VIEW  " + stage + "     |     1 Base   2 Normal   3 POM   0 Exhibit defaults", bodyText);
            GUI.Label(new Rect(40,height-78,1200,45), "Click to walk · WASD / mouse · Shift faster · Esc release cursor · F1–F4 viewpoints · L pause light · H hide UI · R reset\nHeight and roughness are image-derived estimates. POM leaves silhouettes and cast shadows at the mesh surface.", small);
            if (Cursor.lockState == CursorLockMode.Locked)
                GUI.Label(new Rect(width / 2 - 5, height / 2 - 12, 20, 24), "+", bodyText);
        }
    }
}
