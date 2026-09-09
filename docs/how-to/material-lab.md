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
| 4 / 5 / 6 | Cluster detail with fade / wear masks / final material layers |
| [ / ] | Decrease / increase B coverage, with exact 0 and 1 endpoints |
| - / = | Decrease / increase blend width, including zero |
| V / Q | Cycle debug channel / low, balanced and high POM quality |
| 0 | Restore the original comparison stages |
| F1 / F2 | Gallery overview / close oblique comparison |
| F3 / F4 | Workshop overview / cabinet close-up |
| F5 / F6 / F7 / F8 | Surface history overview / masonry / fine weave / inspection mat |
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

The south workshop wall holds masonry, wood, painted metal and fine weave. Each
has three matching boards for added detail, wear masks and final layers. Keys 1–6 let
you compare all six stages on the same geometry. The workshop wall, crates,
bench, cabinet and woven inspection mat use these bundles as game fixtures.
The original gallery keeps its three-stage comparison; keys 4–6 leave those
materials at POM. Key 5 shows red edge chipping, green cavity grime and blue
encoded curvature.
V cycles lit, composed height, coverage mask, signed curvature, edge, cavity,
blend weight, normal, linear albedo, roughness, metallic and AO.

The cabinet's chips use an authored mask of its cube-face UV borders. Wood
shows removal of surface finish. UV relief curvature does not supply mesh
silhouette knowledge. Fine detail uses a separate source and the demo recipes
fade it from 2 to 6 meters. Equal or reversed fade bounds disable distance fading.
The [bundle reference](../reference/material-bundles.md) explains the reusable
profile and its parameter ranges.

## Source and regeneration

Assets, package manifests, project settings and Unity `.meta` files are versioned.
Library, Temp, Logs, UserSettings, Builds and Evidence are local generated data.
The committed scene can be edited normally. The rebuild command explicitly
replaces that scene with the procedural layout, so use it only when regeneration
is intended and preserve manual edits first.

Regenerate the small material fixtures from the existing source images:

```powershell
.\.venv\Scripts\python.exe -m scripts.prepare_material_lab
.\.venv\Scripts\python.exe -m scripts.prepare_material_cluster
```

The output manifest records source/output hashes and the generation settings.
Height and AO share the same 256×256 field; albedo and roughness are 512×512.
Height is exported as 16-bit PNG and explicitly imported as linear R16. The
sources and their image-generation provenance are under `textures/pom-validation`.
The demo remaps the estimated roughness through authored minimum values: 0.64
for limestone, 0.76 for brick, 0.36 for metal and 0.59 for wood. These are demo
material choices, not changes to the generator defaults or measured properties.

The cluster script writes four explicit recipes and authored PNG fields under
`textures/material-cluster`, then processes their batch into
`Assets/TextureWorks/Bundles`. Their material maps are 128×128 and external detail
is 256×256. To regenerate an existing recipe without recreating those sources:

```powershell
.\.venv\Scripts\python.exe -m textureworks.bundle generate textures/material-cluster/masonry.json `
  --output output/material-cluster-masonry --backend ptx
```

For another project, copy that whole output folder into its `Assets`, select
`material.json`, then choose **TextureWorks > Set up selected material bundle**.
This validates hashes, enforces import settings and creates the material.

In the editor, choose **TextureWorks > Rebuild demonstration scene** to regenerate
the scene, its materials and import settings. With the editor closed, the CLI can
perform the same action:

```powershell
& $unityCli run .\demo\TextureWorksMaterialLab --timeout 420 -- `
  -executeMethod TextureWorks.MaterialLab.Editor.LabBuilder.Rebuild -force-d3d11
```

In an open editor, `unity command cluster_rebuild --project-path $project --json`
performs this rebuild. Dirty scenes are saved as backup copies in
`Assets/Evidence/SceneBackups` before the generated scene is replaced. Keep any
manual changes in a separate scene if you want to reuse them after regeneration.

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
& $unityCli command cluster_controls --coverage 0.5 --blend_width 0.2 --debug 0 --quality 1 --project-path $project --json
& $unityCli command cluster_validate --project-path $project --timeout 420 --json
& $unityCli command cluster_profile --project-path $project --json
& $unityCli command capture_game_view --source screen --save_path Evidence/hud.png `
  --project-path $project --json
& $unityCli command editor_stop --project-path $project --json
& $unityCli command lab_build_windows --project-path $project --timeout 420 --json
```

`lab_view` uses zero-based viewpoints and stages: stage -1 restores exhibit
defaults, 0 selects base, 1 normal, 2 POM, 3 detail, 4 wear, and 5 layers.
After a Play Mode transition, poll `lab_ready` until ready and in the desired
mode; Pipeline briefly disconnects during domain reload. The reproducible
`scripts/test-material-lab.ps1 -UseOpenEditor` handles this transition and runs
the build and both validation commands. `-Rebuild` also regenerates the scene.
`lab_validate` requires Play Mode;
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

The cluster uses `TextureWorks/URP/Layered Lit` and
`TextureWorksMaterialLayers.hlsl`. Every POM sample composes both heights with
the runtime mask and controls. The final intersection supplies all material
channels. Detail uses reoriented normals; material transitions preserve the
normal of the composed height and interpolate authored slope residuals.
Low quality uses 8–24 march samples and 2 refinements, balanced 16–64/4, and high
32–128/6. Low can miss thin relief. All settings use mipmaps and original UV
gradients. This cluster adds no stochastic anti-repetition, world-oriented dust,
three-layer materials or texture arrays.

See [cluster validation](../dev/material-cluster-validation.md) and
[foundation evidence](../dev/material-lab-validation.md) for the tested
environment and the distinction between numerical checks and visual review.
