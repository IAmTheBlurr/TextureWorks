"""Regenerate the checked-in Unity lab fixtures from TextureWorks source images."""

import hashlib
import json
from pathlib import Path

import cupy as cp
import numpy as np
from PIL import Image

from textureworks.core.io import save_map
from textureworks.ptx.ao import generate_ao
from textureworks.ptx.height import generate_height
from textureworks.ptx.roughness import generate_roughness


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    destination = root / "demo/TextureWorksMaterialLab/Assets/TextureWorks/Textures"
    destination.mkdir(parents=True, exist_ok=True)
    materials = []
    for name, depth in [("limestone-blocks", 0.06), ("red-brick", 0.04),
                        ("machined-metal", 0.025), ("oak-planks", 0.035)]:
        source = root / "textures/pom-validation" / f"{name}.png"
        with Image.open(source) as image:
            color = image.convert("RGB").resize((512, 512), Image.Resampling.LANCZOS)
            color.save(destination / f"{name}-albedo.png")
            gpu = cp.asarray(np.asarray(color, dtype=np.float32) / 255)
            low = color.resize((256, 256), Image.Resampling.LANCZOS)
            height_input = cp.asarray(np.asarray(low, dtype=np.float32) / 255)
        height = generate_height(height_input, blur_sigma=1.5)
        save_map(height, destination / f"{name}-height.png", bits=16)
        save_map(generate_roughness(gpu), destination / f"{name}-roughness.png")
        save_map(generate_ao(height_input, height_map=height), destination / f"{name}-ao.png")
        materials.append({"name": name, "depthMeters": depth,
                          "sourceSha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                          "outputs": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                      for p in sorted(destination.glob(f"{name}-*.png"))}})
    manifest = {"schemaVersion": 1, "backend": "ptx", "albedoSize": 512,
                "heightSize": 256, "heightBits": 16, "heightBlurSigma": 1.5,
                "heightContrast": 1.2,
                "sourceProvenance": "textures/pom-validation/README.md",
                "limitations": "Height, AO and roughness are image-derived estimates. "
                "Metallic is authored per material. Bright mortar can become raised. "
                "Normal shading is derived from the same sampled height field as POM.",
                "materials": materials}
    (destination / "fixtures.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {len(materials)} material sets in {destination}")


if __name__ == "__main__":
    main()
