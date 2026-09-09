# TextureWorks Unity materials

`TextureWorksParallax.hlsl` remains the reusable Shader Graph custom-function
include. See the [integration guide](../docs/how-to/parallax-occlusion-mapping.md)
for its inputs and conventions.

This directory is also a local UPM package, `com.textureworks.materials`, targeting
Unity 6000.6 / URP 17.6 for the `TextureWorks/URP/Parallax Lit` demonstration shader.
The original include has its own earlier Unity validation history; the package
manifest's minimum version applies to this packaged integration.

The [Material Lab](../docs/how-to/material-lab.md) demonstrates this profile with
real URP lighting. It lists the supported features and limitations. The package
does not require the lab's Input System or experimental editor automation package.
