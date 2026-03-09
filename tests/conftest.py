"""Shared pytest fixtures for TextureWorks tests."""

from pathlib import Path

import cupy as cp
import pytest

from textureworks.core.io import load_texture


TEXTURE_DIR = Path(__file__).parent.parent / "textures"


@pytest.fixture
def test_texture() -> cp.ndarray:
    """Load the primary test texture as a float32 GPU array.

    Expects textures/test_texture3.png to exist.
    """
    path = TEXTURE_DIR / "test_texture3.png"
    if not path.exists():
        pytest.skip(f"Test texture missing: {path}")
    return load_texture(path)


@pytest.fixture
def small_texture() -> cp.ndarray:
    """Generate a small synthetic texture for fast unit tests.

    Returns a 64x64 RGB float32 GPU array with a gradient pattern
    and some hard edges (simulates panel geometry).
    """
    import numpy as np

    h, w = 64, 64
    # Horizontal gradient in R, vertical in G, constant B
    r = np.tile(np.linspace(0, 1, w, dtype=np.float32), (h, 1))
    g = np.tile(np.linspace(0, 1, h, dtype=np.float32), (w, 1)).T
    b = np.full((h, w), 0.5, dtype=np.float32)

    # Add hard edges (simulating panel lines)
    r[28:36, :] = 0.1
    g[:, 28:36] = 0.1

    rgb = np.stack([r, g, b], axis=2)
    return cp.asarray(rgb)
