# TextureWorks in Unity

TextureWorks includes an optional Unity Material Lab and a reusable URP material
package. The Python library still handles texture generation independently;
Unity gives those textures somewhere to show what they can do.

## Why a room full of textures?

The lab grew out of wanting to see generated maps working together on actual
surfaces. A normal map can look convincing in isolation, yet the material can
feel flat when you move past it. Height, roughness, lighting, and viewing distance
all affect that impression. Being able to walk up to a wall, move the camera,
and compare the same material under the same light makes those differences
easier to judge.

That is why the project has both numerical checks and a place to look around.
The gallery makes controlled comparisons; the workshop puts materials on crates,
a bench, a cabinet, masonry, and curved geometry. As TextureWorks gains more
capabilities, this gives us a shared scene for inspecting their contribution and
catching visual problems. It is also a fun way to show off the output.

## What's included

| Part | What it provides |
| --- | --- |
| [Material Lab project](../../demo/TextureWorksMaterialLab/) | A walkable gallery comparing base shading, height normals, and POM across limestone, brick, metal, and wood; a workshop demonstrating detail, wear, and two-material layers under fixed and moving realtime lights. |
| [Unity material package](../../unity/) | Parallax Lit and Layered Lit URP shaders, reusable POM HLSL for Shader Graph, and a material-bundle importer that applies texture conventions. |
| [Retained validation](../dev/material-cluster-validation.md) | Render comparisons, player captures, numerical checks, and recorded performance for the supported configuration. |

The scene, textures, materials, scripts, package manifests, project settings,
and Unity `.meta` files are committed. Unity recreates local caches during import.
Builds, logs, and raw evidence are ignored; selected captures and reports live
under `docs/dev/assets/`.

## What you need

- **The whole repository**, keeping `demo/TextureWorksMaterialLab` and `unity/`
  in their original locations. The demo resolves its local material package
  through that relative folder layout.
- **Unity Hub and Unity Editor 6000.6.0f1**, with a working Unity license. Use the
  pinned editor for the documented setup; other editor versions are unverified.
- **URP 17.6.0**, declared in the package manifests. The demo also declares
  Input System 1.20.0 and Unity Pipeline 0.6.0-exp.1 for its controls and editor
  automation. Let Unity resolve the committed dependencies; the initial import
  needs access to their package registries.
- **A machine capable of running the Unity editor and URP.** Recorded lab work
  used Windows and an RTX 5070; the current layered materials have Windows
  Direct3D11 player validation. This is the tested configuration, not a measured
  minimum GPU requirement. See Unity's
  [system requirements](https://docs.unity3d.com/6000.6/Documentation/Manual/system-requirements.html)
  for the editor's baseline.

The committed demo textures are ready to use. **Python, CUDA, and CuPy are only
needed when generating or regenerating textures**, not for walking around the
existing scene. Windows build support is needed if you want to build a Windows
player; pressing Play in the editor uses the editor installation.

## Open the lab or reuse the materials

Add `demo/TextureWorksMaterialLab` to Unity Hub, allow the import to finish,
then open `Assets/TextureWorks/Scenes/MaterialLab.unity` and press Play.
Unity's [project management guide](https://docs.unity.com/en-us/hub/project-manage)
explains adding an existing project from disk. The
[lab guide](../how-to/material-lab.md) covers movement, comparisons, lighting
controls, and regeneration.

For your own compatible URP project, the repository's `unity/` directory is a
local UPM package. Follow Unity's
[install a package from disk instructions](https://docs.unity3d.com/6000.0/Documentation/Manual/upm-ui-local.html)
and select its `package.json`. Keep that package folder available at the path
your project references. Then follow the
[bundle import reference](../reference/material-bundles.md) or the
[POM Shader Graph guide](../how-to/parallax-occlusion-mapping.md) for material setup.
The included package targets URP; Built-in and HDRP support is unvalidated.

The recorded checks cover this development machine and its player builds.
A fresh clone on a separate machine has not yet been verified. POM provides
surface relief through shading; silhouettes, collision, and cast shadows still
follow the mesh. The validation records describe the remaining rendering limits.

## Where to go next

- [Walk the lab](../how-to/material-lab.md): scene setup, controls, and fixtures.
- [Use POM in Unity](../how-to/parallax-occlusion-mapping.md): height export,
  import precision, and Shader Graph connections.
- [Import material bundles](../reference/material-bundles.md): inputs, metadata,
  and the reusable layered material profile.
- [Review the evidence](../dev/material-cluster-validation.md): rendered results,
  performance, supported targets, and limitations.
- [All TextureWorks documentation](../index.md).
