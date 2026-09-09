"""Assemble Unity renders into labeled comparisons and camera sweeps."""

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def font(size: int) -> ImageFont.ImageFont:
    for path in ("C:/Windows/Fonts/segoeui.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def panel(folder: Path, names: list[str], title: str, labels: list[str]) -> Image.Image:
    image = Image.new("RGB", (384 * len(names), 450), "#13171d")
    draw = ImageDraw.Draw(image)
    draw.text((18, 8), title, fill="#eef1f5", font=font(20))
    for i, (name, label) in enumerate(zip(names, labels)):
        draw.text((i * 384 + 18, 40), label, fill="#b9c4d2", font=font(14))
        with Image.open(folder / (name + ".png")) as source:
            image.paste(source.convert("RGB"), (i * 384, 66))
    return image


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    report = json.loads((args.folder / "report.json").read_text())
    names = list(dict.fromkeys(m["material"] for m in report["measurements"]))
    labels = ["Flat + height normals", "Parallax Occlusion Mapping", "Displaced mesh reference"]
    rows = []
    for name in names:
        title = name.replace("-", " ").title()
        row = panel(args.folder, [f"{name}-60-{mode}" for mode in ("flat", "pom", "mesh")],
                    title + " | 60 degree camera", labels)
        row.save(args.folder / f"{name}-comparison.png")
        rows.append(row)
        frames = [panel(args.folder, [f"{name}-motion-{frame:02}-{mode}" for mode in range(3)],
                        title + " | camera sweep", labels) for frame in range(25)]
        # Use a fixed palette over the complete sweep to avoid palette flicker.
        palette_source = Image.new("RGB", (1152, 450 * 5))
        for i, f in enumerate(frames[::6]):
            palette_source.paste(f, (0, i * 450))
        palette = palette_source.quantize(colors=255)
        frames = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]
        sequence = frames + frames[-2:0:-1]
        sequence[0].save(args.folder / f"{name}-motion.gif", save_all=True,
                         append_images=sequence[1:], duration=90, loop=0)
    overview = Image.new("RGB", (1152, 450 * len(rows)))
    for i, row in enumerate(rows):
        overview.paste(row, (0, i * 450))
    overview.save(args.folder / "overview.png")
    print(report["environment"])
    for m in report["measurements"]:
        if m["quality"] == "motion-default":
            continue
        print(f"{m['material']:18} {m['angle']:5g} deg {m['quality']}: mean {m['meanTexels']:.5f}, "
              f"p99 {m['p99Texels']:.5f} height texels; >1 texel {m['overOneTexelFraction']:.3%}")
    motion = [m for m in report["measurements"] if m["quality"] == "motion-default"]
    if motion:
        print(f"{len(motion)} motion frames: worst p99 {max(m['p99Texels'] for m in motion):.5f} height texels")
    print(f"Overview: {args.folder / 'overview.png'}")


if __name__ == "__main__":
    main()
