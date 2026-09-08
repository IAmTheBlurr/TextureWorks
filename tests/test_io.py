"""File precision and validation at the CPU/GPU boundary."""

import cupy as cp
import numpy as np
from PIL import Image
import pytest

from textureworks.core.io import load_texture, save_map


@pytest.mark.parametrize("bits", [8, 16])
def test_png_precision_and_round_trip(tmp_path, bits):
    values = np.linspace(0, 1, 4096, dtype=np.float32).reshape(32, 128)
    path = tmp_path / "maps" / "height.png"
    save_map(cp.asarray(values), path, bits=bits)
    # Read PNG IHDR directly: verify stored precision, not Pillow's mode alone.
    header = path.read_bytes()
    assert header[:8] == b"\x89PNG\r\n\x1a\n"
    assert (header[24], header[25]) == (bits, 0)  # grayscale
    with Image.open(path) as img:
        encoded = np.asarray(img)
    assert int(encoded.min()) == 0
    assert int(encoded.max()) == (1 << bits) - 1
    assert np.unique(encoded).size == (256 if bits == 8 else 4096)
    loaded = load_texture(path)
    assert loaded.dtype == cp.float32
    assert loaded.shape == values.shape
    error = 1 / 255 if bits == 8 else 0.5 / 65535 + 1e-7
    np.testing.assert_allclose(cp.asnumpy(loaded), values, atol=error, rtol=0)


@pytest.mark.parametrize("bits, expected", [(8, [0, 127, 255]), (16, [0, 32768, 65535])])
def test_quantization_and_clipping(tmp_path, bits, expected):
    path = tmp_path / "height.png"
    save_map(cp.asarray([[-1.0, 0.5, 2.0]], dtype=cp.float32), path, bits=bits)
    with Image.open(path) as img:
        np.testing.assert_array_equal(np.asarray(img), [expected])


def test_default_rgb_bytes_are_preserved(tmp_path):
    path = tmp_path / "normal.png"
    values = np.array([[[0.5, 0.5, 1.0], [0.0, 0.25, 0.75]]], dtype=np.float32)
    save_map(cp.asarray(values), path)
    with Image.open(path) as img:
        assert img.mode == "RGB"
        np.testing.assert_array_equal(np.asarray(img), (values * 255).astype(np.uint8))


def test_rgba_load_still_drops_alpha(tmp_path):
    path = tmp_path / "color.png"
    Image.fromarray(np.array([[[20, 40, 60, 0]]], dtype=np.uint8)).save(path)
    np.testing.assert_allclose(cp.asnumpy(load_texture(path)), [[[20/255, 40/255, 60/255]]])


@pytest.mark.parametrize("values, bits, suffix, message", [
    ([[0.5]], 12, ".png", "bits"),
    ([[[0.5, 0.5, 0.5]]], 16, ".png", "grayscale"),
    ([[0.5]], 16, ".jpg", ".png"),
    ([0.5], 8, ".png", "nonempty"),
    ([], 16, ".png", "nonempty"),
    ([[float("nan")]], 16, ".png", "finite"),
    ([[float("inf")]], 8, ".png", "finite"),
])
def test_invalid_output_is_rejected_before_writing(tmp_path, values, bits, suffix, message):
    path = tmp_path / ("invalid" + suffix)
    with pytest.raises(ValueError, match=message):
        save_map(cp.asarray(values), path, bits=bits)
    assert not path.exists()
