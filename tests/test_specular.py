"""Tests for specular map generation -- CuPy vs PTX comparison."""

import cupy as cp
import numpy as np
import pytest

from textureworks.core.compare import compare_outputs
from textureworks.cupy_ref.specular import generate_specular as cupy_specular
from textureworks.ptx.specular import generate_specular as ptx_specular

TOLERANCE = 2  # Per algorithms.md


class TestSpecularMap:
    def test_cupy_vs_ptx_match(self, test_texture):
        cupy_out = cupy_specular(test_texture)
        ptx_out = ptx_specular(test_texture)
        result = compare_outputs(cupy_out, ptx_out, tolerance=TOLERANCE)
        assert result["matches"], (
            f"Max diff {result['max_diff']} exceeds tolerance {TOLERANCE}"
        )

    def test_cupy_vs_ptx_small(self, small_texture):
        cupy_out = cupy_specular(small_texture)
        ptx_out = ptx_specular(small_texture)
        result = compare_outputs(cupy_out, ptx_out, tolerance=TOLERANCE)
        assert result["matches"], (
            f"Max diff {result['max_diff']} exceeds tolerance {TOLERANCE}"
        )

    def test_output_shape(self, test_texture):
        out = cupy_specular(test_texture)
        h, w = test_texture.shape[:2]
        assert out.shape == (h, w)

    def test_output_range(self, test_texture):
        out = cupy_specular(test_texture)
        assert float(cp.min(out)) >= 0.0
        assert float(cp.max(out)) <= 1.0

    def test_bright_vs_dark_specularity(self):
        # Bright unsaturated region should be more specular than dark region
        tex = cp.zeros((32, 32, 3), dtype=cp.float32)
        tex[:16, :, :] = 0.9   # bright top half
        tex[16:, :, :] = 0.1   # dark bottom half
        out = cupy_specular(tex)
        bright_mean = float(cp.mean(out[:16, :]))
        dark_mean = float(cp.mean(out[16:, :]))
        assert bright_mean > dark_mean
