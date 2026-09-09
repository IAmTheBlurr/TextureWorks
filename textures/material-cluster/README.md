# Material cluster fixtures

Regenerate these inputs and the Unity bundles with
`python -m scripts.prepare_material_cluster` through the project interpreter.
The script records its seed, dimensions and source hashes in `provenance.json`.

Masonry, wood and steel use existing generated color imagery with the original
prompts and actual image-generator provenance in [pom-validation](../pom-validation/README.md).
The new height fields, mortar layout, coverage masks and fine weave are authored
analytic constructions. They provide controlled known geometry; they are not
evidence that the source albedo was reconstructed physically.

Painted metal uses a mask authored for the [0,1] UV borders of each cabinet cube
face. It supplies actual face-boundary knowledge for the visible chipped corners.
Wood masks remove surface finish and do not claim silhouette curvature. All
recipes keep paint/substrate and stone/grime identities explicit.
