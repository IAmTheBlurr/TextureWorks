# Next implementation session: detail, wear, and material layers

Paste the prompt below into a Codex session opened on this repository. Select
GPT-6 Astra in the session settings. The prompt requests a goal and implementation;
this document itself does not start another session.

## Prompt

Implement the first advanced material cluster in TextureWorks and its Unity
Material Lab: detail texturing and distance fading from Tier 2, useful wear masks
from Tier 5, and two-material composition from Tier 7. Create a goal for this
work. Continue through implementation, testing, visual correction, atomic commits,
push, PR review and merge to main until the acceptance criteria below are met or
a specific external dependency prevents progress. Use no fixed token budget.

Start by reading AGENTS.md, docs/algorithms.md, docs/dev/contributing.md,
docs/how-to/material-lab.md, and docs/dev/material-lab-validation.md. Inspect the
current source, git state and available GPU/editor before relying on previous
results. Preserve user work. The expanded advanced-tier markdown, if present,
is background research and proposals; verify its mathematics and renderer claims.
It is not a specification of available features. Read only the relevant sections.

The intended user is a solo game developer processing a texture collection with
the Python library or CLI, then importing usable materials into Unity 6.6 URP.
Deliver reusable material profiles and documented parameters. Use an LLM for
implementation and adaptation; ordinary material generation should not depend on
an LLM inventing and compiling a new shader for every image.

### Deliverable 1: a reliable material bundle

Extend the Python API and CLI with a versioned material bundle that records input
provenance, dimensions, color space, channel layout, normal convention, height
reference plane, physical texture size, relief depth, parameters and output hashes.
Accept existing authored height, normal, roughness, metallic and masks. Preserve
their precision and meaning. Keep the existing six-map API and CLI compatible.
Resolve map dependencies explicitly and avoid recomputing or inconsistently
normalizing a shared height field.

Provide deterministic named presets for a small asset collection, reproducible
batch processing and clear errors for unsupported dimensions, encodings or
incompatible metadata. Export linear scalar data separately from color where
appropriate. Retain a separate 16-bit height texture; channel packing must not
silently reduce its precision. A custom URP mask layout must identify every
channel and must not be advertised as a standard URP/HDRP layout unless it is one.

### Deliverable 2: detail from Tier 2

Implement documented frequency separation with a meaningful radius convention,
detail color/residual output and detail normals. Support an external detail source
when the base image lacks sufficient resolution. A high-pass filter extracts
existing frequencies; it cannot recover information absent from the input.

Blend detail normals with a verified reoriented normal method. Define the neutral
input and strength behavior. Blend color in linear space with a documented
encoding and neutral value. Expose tiling, strength, distance fade and optional
roughness modulation. At zero strength and beyond the fade range the base material
must be recovered without a visible transition. Use derivatives, mipmaps and
appropriate filtering to prevent shimmer during motion. Handle equal/reversed
fade bounds explicitly.

This first cluster requires detail and fading. Histogram-preserving stochastic
tiling is an optional extension after all required acceptance passes. Do not label
the full expanded Tier 2 complete if anti-repetition remains unimplemented.

### Deliverable 3: wear masks from Tier 5

Implement signed curvature, convex/exposed-edge and cavity masks derived from an
explicit height or normal field, plus deterministic wear composition controls.
Specify signs, physical or texel units, boundary handling, neutral value and
parameter ranges before implementing kernels. Establish the sign with analytic
bumps and depressions. Avoid interpreting any strong gradient as an exposed edge.

Make edge chipping and cavity grime independently controllable. Use a stable seed
for variation, preserving the original base material and allowing regeneration.
Accept authored masks so the developer can correct imperfect inference. UV-space
relief curvature does not describe the silhouette or mesh curvature. If a chipped
crate corner is shown, supply a real mesh-derived/authored mask for that corner.
Never imply an albedo image supplied this information automatically.

World-oriented dust or streak effects are optional and must take object/world
orientation or mesh data as input. They are not required for this first pass.
Wrapped convolution alone does not make arbitrary source imagery seamless.

### Deliverable 4: material layers from Tier 7

Implement a reusable two-material URP profile and the bundle inputs it consumes.
Demonstrate paint over metal with exposed substrate, and dirt/grime in masonry
recesses. The user must be able to adjust the coverage mask and blend width,
including exact all-A and all-B endpoints. Test zero-width behavior without NaNs
or division by zero. Blend albedo, roughness, metallic, AO and normals consistently.
Use reoriented normals for detail superposition; choose and justify the method for
transitions between material normals.

Keep height units and reference planes consistent. POM must intersect the same
composed height field that determines layer appearance and shading. For runtime
coverage changes, evaluate the common composition function during the ray trace,
then evaluate all channels at the resulting UV. Tracing only the substrate and
blending a different height afterward is not acceptable. A separately named bake
profile may compose offline, but it does not establish runtime composition.

Use the existing parallax include as the regression baseline. Preserve its
physical depth scaling, distance/grazing behavior, original-gradient sampling,
finite output and height precision. Profile the actual cost of layered POM and
provide a practical lower-cost quality setting. Three or more layers and texture
arrays may follow after this two-layer path is complete and tested.

### Deliverable 5: import and real Unity demonstration

Extend the local Unity package in unity/ with the reusable shader components and
an importer/setup workflow for bundles. The importer must enforce sRGB/linear,
normal encoding, wrap, filtering and precision settings, and create materials
with reproducible defaults. Keep the reusable core independent of the demo scene.
Avoid advertising unsupported render pipelines or graphics APIs.

Use demo/TextureWorksMaterialLab as the interactive test environment. Extend its
workshop fixtures with progressive stages: existing base/normal/POM, added detail,
wear visualization, and final material layers. Keep comparisons on identical
geometry, camera and lighting. Preserve walk controls, viewpoint shortcuts and
moving-light pause. Explain the active effects and remaining limitations in the
scene. Include clear mask/height debug views as well as lit materials.

Use at least four materially different inputs and appropriate game-like fixtures:
masonry, wood, painted metal and a fine-detail surface. Existing generated sources
are available under textures/pom-validation. Generate additional inputs when they
improve coverage, retaining prompts and actual generator provenance. Synthetic
analytic fixtures establish ground truth; generated albedo images demonstrate
appearance and cannot establish physical reconstruction accuracy.

Use the installed Unity CLI and pinned Pipeline package for scene control,
captures and checks. Inspect command help and package APIs before guessing them.
Save captures to disk rather than printing image base64 into the conversation.
Keep development automation local; do not enable a runtime command server in a
normal player build.

### Quality and acceptance

For each new numerical generator, provide the specification, CuPy reference,
matching PTX implementation, API/CLI integration and meaningful tests together.
Keep Python 3.10 compatibility. Do not relax an existing tolerance to conceal a
regression. If a different precision is justified, document the measured error
and its effect on the exported/rendered result.

Required numerical coverage includes flat inputs, bumps/depressions, ramps,
non-square/odd dimensions, supported boundary modes, parameter extrema, seed
repeatability, neutral detail, mask endpoints and bundle round trips. Test output
semantics in addition to backend agreement. Verify composed height and normal
orientation against independent analytic or geometric references. Verify both
the Python library and CLI through a complete material-generation example.

Required Unity evidence includes actual shader compilation, imported precision,
correct neutral/base behavior, fixed comparison views, close/grazing and distant
camera motion, moving illumination, seams and transitions. Inspect the images
and animations yourself and correct defects. Do not equate absence of magenta
pixels or backend agreement with visual acceptance. Include a player build and
runtime smoke test on the available Windows target. Record other targets as
unvalidated. Re-run the existing POM GPU conformance/geometric harness when its
shader path changes.

Record GPU, Unity/URP version, graphics API, resolution, quality preset and scene
conditions alongside performance measurements. Separate editor observations from
player measurements. Explain the quality/performance tradeoff and keep the demo
walkable on the available machine. No arbitrary FPS claim without measurement.

Run the full Python suite before merge. Review the final source/diff and applicable
GitHub checks. Preserve atomic history with coherent commits, push, create a PR to
main, merge once relevant tests and review pass, then synchronize local main.
Absent CI is not a CI pass. Keep generated caches/builds ignored; retain the small
fixtures, representative visual evidence and reproducible scripts needed by the
next session.

Report the exact capabilities shipped, the exact portions of Tiers 2/5/7 still
deferred, the verification results, and how to walk the scene and regenerate a
material. Continue correcting required failures instead of stopping after the
first plausible render. A real external blocker should identify what failed,
what was tried, what remains intact and the minimal input needed to resume.

## Why this cluster

These features share scalar fields and composition rules and improve the same
assets. The bundle/import workflow makes subsequent effects easier to add. The
first pass intentionally covers useful portions of three tiers with observable
acceptance criteria. It does not promise the full expanded contents of those tiers
in one session.

The prompt's scope, persistence and evidence requirements follow the
[GPT-6 Astra guide](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-6-astra).
Unity's local editor automation is described in the
[Unity CLI announcement](https://unity.com/blog/meet-the-unity-cli).
