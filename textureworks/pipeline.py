"""Pipeline CLI for generating PBR texture maps from a single input image."""

from pathlib import Path

import click
import cupy as cp

from textureworks.core.io import load_texture, save_map

MAP_TYPES = ("normal", "height", "ao", "roughness", "metallic", "specular")
BACKENDS = ("cupy", "ptx")


def _get_generator(map_type: str, backend: str):
    """Lazy-import the generate function for a given map type and backend."""
    if backend == "cupy":
        mod = __import__(f"textureworks.cupy_ref.{map_type}", fromlist=["generate_" + map_type])
    else:
        mod = __import__(f"textureworks.ptx.{map_type}", fromlist=["generate_" + map_type])
    return getattr(mod, f"generate_{map_type}")


def generate_maps(
    texture: cp.ndarray,
    map_types: tuple[str, ...] = MAP_TYPES,
    backend: str = "ptx",
) -> dict[str, cp.ndarray]:
    """Generate PBR maps from a loaded texture.

    Args:
        texture: (H, W, 3) float32 cupy array.
        map_types: Which maps to generate.
        backend: 'cupy' or 'ptx'.

    Returns:
        Dict mapping map type name to output array.
    """
    results = {}
    height_map = None

    for mt in map_types:
        gen = _get_generator(mt, backend)
        if mt == "ao" and height_map is not None:
            results[mt] = gen(texture, height_map=height_map)
        else:
            results[mt] = gen(texture)
        # Cache height map for AO reuse
        if mt == "height":
            height_map = results[mt]

    return results


@click.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.option("--output", "-o", default="output", help="Output directory.")
@click.option(
    "--map", "-m", "map_type", default="all",
    help="Map type to generate (normal, height, ao, roughness, metallic, specular, or all).",
)
@click.option(
    "--backend", "-b", default="ptx", type=click.Choice(BACKENDS),
    help="Backend: cupy or ptx.",
)
@click.option(
    "--height-bits", default="8", type=click.Choice(("8", "16")), show_default=True,
    help="PNG bit depth for the height map. Other maps remain 8-bit.",
)
def main(input_path: str, output: str, map_type: str, backend: str, height_bits: str):
    """Generate PBR texture maps from INPUT_PATH."""
    input_path = Path(input_path)
    output_dir = Path(output)
    stem = input_path.stem

    click.echo(f"Loading {input_path}...")
    texture = load_texture(input_path)
    click.echo(f"  Texture shape: {texture.shape}, backend: {backend}")

    if map_type == "all":
        types = MAP_TYPES
    else:
        if map_type not in MAP_TYPES:
            raise click.BadParameter(f"Unknown map type: {map_type}. Choose from {MAP_TYPES}")
        types = (map_type,)

    results = generate_maps(texture, types, backend)

    for name, data in results.items():
        out_path = output_dir / f"{stem}_{name}.png"
        save_map(data, out_path, bits=int(height_bits) if name == "height" else 8)
        click.echo(f"  Saved {name} -> {out_path}")

    click.echo("Done.")


if __name__ == "__main__":
    main()
