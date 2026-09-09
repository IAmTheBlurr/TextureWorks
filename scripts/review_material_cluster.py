"""Arrange Unity's saved captures for human review; never substitute for assertions.

Run after test-material-lab.ps1 and test-material-cluster-player.ps1. Full motion
contact sheets stay in ignored output; representative evidence goes into docs.
"""

import json
from pathlib import Path
import shutil

from PIL import Image, ImageDraw


def grid(paths: list[Path], labels: list[str], columns: int, size: tuple[int, int], output: Path) -> None:
    width, height = size
    result = Image.new("RGB", (width*columns, (height+24)*((len(paths)+columns-1)//columns)), "#162329")
    draw = ImageDraw.Draw(result)
    for i, (path, label) in enumerate(zip(paths, labels)):
        x, y = (i % columns)*width, (i//columns)*(height+24)
        with Image.open(path) as frame:
            result.paste(frame.convert("RGB").resize(size, Image.Resampling.LANCZOS), (x, y+24))
        draw.text((x+7, y+5), label, fill="white")
    result.save(output)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    evidence = root/"demo/TextureWorksMaterialLab/Evidence/cluster"
    retained = root/"docs/dev/assets/material-cluster"
    review = root/"output/material-cluster-review"
    retained.mkdir(parents=True, exist_ok=True)
    review.mkdir(parents=True, exist_ok=True)
    names = ("masonry", "wood", "painted-metal", "fine-detail")
    stages = ("base", "normal", "POM", "detail", "wear", "layers")
    paths = [evidence/f"{name}-stage{stage}.png" for name in names for stage in range(6)]
    labels = [f"{name}: {stage}" for name in names for stage in stages]
    grid(paths, labels, 6, (320, 200), retained/"stages.png")
    for name in names:
        frames = sorted((evidence/f"{name}-motion").glob("*.png"))
        if len(frames) != 48:
            raise ValueError(f"Expected 48 current motion frames for {name}")
        grid(frames, [f"{name} / frame {i:02}" for i in range(48)], 8, (240, 150), review/f"{name}-motion.png")
        if name in ("painted-metal", "fine-detail"):
            images = []
            for path in frames:
                with Image.open(path) as frame:
                    images.append(frame.convert("RGB").resize((480, 300), Image.Resampling.LANCZOS))
            images[0].save(retained/f"{name}-motion.webp", save_all=True, append_images=images[1:],
                           duration=100, loop=0, quality=85, method=4)
    for filename in ("validation.json", "editor-performance.json"):
        shutil.copyfile(evidence/filename, retained/filename)
    shutil.copyfile(evidence.parent/"player-build.json", retained/"player-build.json")
    shutil.copyfile(evidence.parent/"validation.json", retained/"lab-validation.json")
    player = evidence/"player-d3d11"
    for filename in ("player-smoke.json", "player-performance.json"):
        shutil.copyfile(player/filename, retained/filename)
    for source, name in ((player/"player-cluster-4.png", "workshop.png"),
                         (player/"player-cluster-3.png", "cabinet.png"),
                         (evidence/"masonry-debug1.png", "composed-height.png"),
                         (evidence/"painted-metal-debug6.png", "layer-weight.png")):
        shutil.copyfile(source, retained/name)
    benchmark = json.loads((root/"output/material-cluster-field-benchmarks.json").read_text())
    benchmark["conditions"] = "Unity editor out of Play Mode; GPU field generators only, 100 repeats after warmup, input validation included."
    (retained/"field-benchmarks.json").write_text(json.dumps(benchmark, indent=2)+"\n", encoding="utf-8")
    print(f"Review all four motion contact sheets in {review}")
    print(f"Representative evidence in {retained}")


if __name__ == "__main__":
    main()
