"""Tests for normal map generation — CuPy vs PTX comparison."""

import cupy as cp
import numpy as np
import pytest

from textureworks.core.compare import compare_outputs
from textureworks.cupy_ref.normal import generate_normal as cupy_normal
from textureworks.ptx.normal import generate_normal as ptx_normal

TOLERANCE = 1  # Per algorithms.md


class TestNormalMap:
    def test_cupy_vs_ptx_match(self, test_texture):
        cupy_out = cupy_normal(test_texture)
        ptx_out = ptx_normal(test_texture)
        result = compare_outputs(cupy_out, ptx_out, tolerance=TOLERANCE)
        assert result["matches"], (
            f"Max diff {result['max_diff']} exceeds tolerance {TOLERANCE}"
        )

    def test_cupy_vs_ptx_small(self, small_texture):
        cupy_out = cupy_normal(small_texture)
        ptx_out = ptx_normal(small_texture)
        result = compare_outputs(cupy_out, ptx_out, tolerance=TOLERANCE)
        assert result["matches"], (
            f"Max diff {result['max_diff']} exceeds tolerance {TOLERANCE}"
        )

    def test_output_shape_matches_input(self, test_texture):
        out = cupy_normal(test_texture)
        h, w = test_texture.shape[:2]
        assert out.shape == (h, w, 3)

    def test_output_range(self, test_texture):
        out = cupy_normal(test_texture)
        assert float(cp.min(out)) >= 0.0
        assert float(cp.max(out)) <= 1.0

    def test_flat_surface_encodes_neutral(self):
        flat = cp.full((32, 32, 3), 0.5, dtype=cp.float32)
        out = cupy_normal(flat)
        center = cp.asnumpy(out[16, 16])
        np.testing.assert_allclose(center, [0.5, 0.5, 1.0], atol=0.01)

    def test_strength_parameter(self, small_texture):
        out_low = cupy_normal(small_texture, strength=0.5)
        out_high = cupy_normal(small_texture, strength=10.0)
        dev_low = float(cp.mean(cp.abs(out_low[:, :, :2] - 0.5)))
        dev_high = float(cp.mean(cp.abs(out_high[:, :, :2] - 0.5)))
        assert dev_high > dev_low
