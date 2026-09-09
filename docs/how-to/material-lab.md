# Walk through the Unity Material Lab

The demo project is `demo/TextureWorksMaterialLab`. It uses Unity **6000.6.0f1**,
URP **17.6.0**, Input System **1.20.0**, and Unity Pipeline **0.6.0-exp.1**.
Its local package dependency points to `unity/` in this repository. Clone the
whole repository so that relative dependency resolves.

Open the project in Unity Hub, then open
`Assets/TextureWorks/Scenes/MaterialLab.unity` and press Play. On this Windows
installation, the new CLI is bundled with Hub but is not on PATH:

```powershell
$unityCli = 'C:\Program Files\Unity Hub\resources\cli\unity.exe'
& $unityCli open .\demo\TextureWorksMaterialLab
```

Unity may require you to review its first-launch editor terms before the
interactive editor opens. The repository does not automate acceptance.

## Controls

| Input | Effect |
| --- | --- |
| Click inside the game | Capture the mouse for walking |
| WASD / mouse | Walk / look |
| Left Shift | Walk faster |
| Escape | Release the mouse |
| 1 / 2 / 3 | Set all exhibit materials to base / height normal / POM |
| 0 | Restore the original comparison stages |
| F1 / F2 | Gallery overview / close oblique comparison |
| F3 / F4 | Workshop overview / cabinet close-up |
| L | Pause or resume the moving task light |
| H | Hide or show the interface |
| R | Return to the entrance |

The gallery contains four triptychs: limestone, brick, metal and wood. Every
triptych holds albedo, AO, roughness, physical relief depth and lighting constant.
Only normal shading and parallax change. “Base” here still includes roughness
and AO; it means the material without relief shading.

The doorway on the right leads into a workshop with cargo crates, a plank bench,
a metal cabinet, pipes, masonry and a curved UV stress specimen. Compare the
same objects with keys 1–3 while looking along their surfaces. Pause the amber
task light with L to distinguish view-dependent parallax from moving highlights.
The lighting includes fixed realtime lights and one animated realtime light.
This first scene does not contain baked lightmaps.

The shelf marked “Next / Surface history” reserves space for detail, wear and
layered materials. Those advanced features are specified in the
[next-session prompt](../dev/material-cluster-one-prompt.md); they are not
implemented by this demonstration foundation.

## Source and regeneration

Assets, package manifests, project settings and Unity `.meta` files are versioned.
Library, Temp, Logs, UserSettings, Builds and Evidence are local generated data.
The committed scene can be edited normally. The rebuild command explicitly
replaces that scene with the procedural layout, so use it only when regeneration
is intended and preserve manual edits first.

Regenerate the small material fixtures from the existing source images:

```powershell
.\.venv\Scripts\python.exe -m scripts.prepare_material_lab
```

The output manifest records source/output hashes and the generation settings.
Height and AO share the same 256×256 field; albedo and roughness are 512×512.
Height is exported as 16-bit PNG and explicitly imported as linear R16. The
sources and their image-generation provenance are under `textures/pom-validation`.
The demo remaps the estimated roughness through authored minimum values: 0.64
for limestone, 0.76 for brick, 0.36 for metal and 0.59 for wood. These are demo
material choices, not changes to the generator defaults or measured properties.

In the editor, choose **TextureWorks > Rebuild demonstration scene** to regenerate
the scene, its materials and import settings. With the editor closed, the CLI can
perform the same action:

```powershell
& $unityCli run .\demo\TextureWorksMaterialLab --timeout 420 -- `
  -executeMethod TextureWorks.MaterialLab.Editor.LabBuilder.Rebuild -force-d3d11
```

Use **TextureWorks > Build Windows player** to produce
`Builds/Windows/TextureWorksMaterialLab.exe` inside the project. Builds are ignored
by git and can be recreated from the committed source.

## Agent controls

The demo pins Unity's experimental Pipeline package. Its local editor commands
are available after the editor finishes importing:

```powershell
$project = (Resolve-Path .\demo\TextureWorksMaterialLab).Path
& $unityCli status --project-path $project --json
& $unityCli command editor_play --project-path $project --json
& $unityCli command lab_view --index 2 --stage 2 --project-path $project --json
& $unityCli command lab_validate --project-path $project --timeout 120 --json
& $unityCli command capture_game_view --source screen --save_path Evidence/hud.png `
  --project-path $project --json
& $unityCli command editor_stop --project-path $project --json
& $unityCli command lab_build_windows --project-path $project --timeout 420 --json
```

`lab_view` uses zero-based viewpoints and stages: stage -1 restores exhibit
defaults, 0 selects base, 1 normal, and 2 POM. `lab_validate` requires Play Mode;
it temporarily moves the visitor and freezes lighting, then returns to the
entrance. Normal Windows builds do not enable a Pipeline runtime server.
Use the CLI's command listing/help for its installed version.
Pipeline's capture command resolves its save path under `Assets`, so the example
above writes `Assets/Evidence/hud.png`. Custom lab reports use the project-root
`Evidence` directory. Both evidence locations are ignored by git.

## Shader profile and limits

`TextureWorks/URP/Parallax Lit` consumes the canonical
`unity/TextureWorksParallax.hlsl` through the local UPM package. It feeds URP's
PBR lighting with main/additional lights, mesh shadows, ambient spherical
harmonics, roughness and AO. The demo uses forward rendering, opaque materials,
4× MSAA and ACES tonemapping. This is a bounded demonstration profile; it does
not claim general URP Lit feature parity, baked lightmap support, decals, SSAO,
XR, deferred rendering or compatibility with graphics APIs beyond the recorded
Direct3D11/Direct3D12 Windows checks.

The shader recovers meters per UV unit from screen derivatives of position and
UV. Relief therefore follows object scale and positive texture tiling on the
orthogonal UV layouts used here. Supply valid tangents. Skewed UV axes, poles and
arbitrary mirrored charts need separate validation before game integration.
Normals are derived from the same filtered height as POM. Real game meshes should
place UV seams thoughtfully and use suitable border sampling.

POM changes sampled appearance inside the mesh silhouette. It does not alter
geometry, collision, depth-buffer position or cast shadows, and it has no relief
self-shadowing. The source heights and roughness are estimates from color, not
measurements. Bright mortar can become raised. Metallic values are authored
material choices. The demo makes these limits visible so they can be judged.

See [validation and evidence](../dev/material-lab-validation.md) for the tested
environment and the distinction between numerical checks and visual review.
