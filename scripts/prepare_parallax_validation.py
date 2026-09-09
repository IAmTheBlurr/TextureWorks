"""Prepare reproducible POM fixtures from the generated source textures."""

import argparse
import hashlib
import json
from pathlib import Path

import cupy as cp
import numpy as np
from PIL import Image

from textureworks.core.io import load_texture, save_map
from textureworks.cupy_ref.height import generate_height as reference_height
from textureworks.ptx.height import generate_height as ptx_height


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("output/pom-inputs"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    args.output.mkdir(parents=True, exist_ok=True)
    entries = []
    depths = {"limestone-blocks": 0.06, "red-brick": 0.04,
              "machined-metal": 0.025, "oak-planks": 0.035}
    for name, depth in depths.items():
        source = root / "textures/pom-validation" / f"{name}.png"
        with Image.open(source) as image:
            rgb = image.convert("RGB")
            rgb.resize((512, 512), Image.Resampling.LANCZOS).save(args.output / f"{name}.png")
            height_input = np.asarray(rgb.resize((256, 256), Image.Resampling.LANCZOS), dtype=np.float32) / 255
        gpu = cp.asarray(height_input)
        # A 256x256 field with sigma=1.5 isolates macroscopic relief from color
        # grain. This is a recorded test preset, not a pipeline default change.
        ref = reference_height(gpu, blur_sigma=1.5)
        actual = ptx_height(gpu, blur_sigma=1.5)
        error = float(cp.max(cp.abs(ref - actual)))
        if error * 255 > 2:
            raise AssertionError(f"{name}: height backend difference {error}")
        png = args.output / f"{name}-height.png"
        save_map(actual, png, bits=16)
        restored = cp.asnumpy(load_texture(png))
        # Explicit little-endian float32, top row first. Unity flips once on load.
        restored.astype("<f4").tofile(args.output / f"{name}.height-f32")
        entries.append({"name": name, "width": 256, "depthWorld": depth,
                        "sourceSha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                        "heightSha256": hashlib.sha256(png.read_bytes()).hexdigest(),
                        "backendMaxDifference": error})
        print(f"{name}: 16-bit height, backend max difference {error:.9g}")
    report = {"planeSizeWorld": 2, "heightBlurSigma": 1.5, "heightContrast": 1.2,
              "heightBits": 16, "assets": entries}
    (args.output / "fixtures.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
