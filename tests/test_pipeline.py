"""CLI integration checks using the real CuPy and PTX generators."""

from click.testing import CliRunner
import numpy as np
from PIL import Image
import pytest

from textureworks.pipeline import MAP_TYPES, main


@pytest.mark.parametrize("backend", ["cupy", "ptx"])
@pytest.mark.parametrize("bits", [8, 16])
def test_height_precision_only_changes_height_file(tmp_path, backend, bits):
    source = tmp_path / "source.png"
    rng = np.random.default_rng(42)
    Image.fromarray(rng.integers(0, 256, (19, 23, 3), dtype=np.uint8)).save(source)
    output = tmp_path / "output"
    args = [str(source), "--backend", backend, "--output", str(output)]
    if bits == 16:
        args += ["--height-bits", "16"]
    result = CliRunner().invoke(main, args)
    assert result.exit_code == 0, result.output
    assert len(list(output.glob("*.png"))) == len(MAP_TYPES)
    for name in MAP_TYPES:
        path = output / f"source_{name}.png"
        header = path.read_bytes()
        assert header[24] == (bits if name == "height" else 8)
        assert header[25] == (2 if name == "normal" else 0)
        with Image.open(path) as img:
            assert img.size == (23, 19)


def test_invalid_height_bits(tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGB", (2, 2)).save(source)
    result = CliRunner().invoke(main, [str(source), "--height-bits", "12"])
    assert result.exit_code == 2
    assert "Invalid value for '--height-bits'" in result.output
