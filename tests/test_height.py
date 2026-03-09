"""Tests for height map generation — CuPy vs PTX comparison."""

import cupy as cp
import numpy as np
import pytest

from textureworks.core.compare import compare_outputs
from textureworks.cupy_ref.height import generate_height as cupy_height
from textureworks.ptx.height import generate_height as ptx_height

TOLERANCE = 2  # Per algorithms.md


class TestHeightMap:
    def test_cupy_vs_ptx_match(self, test_texture):
        cupy_out = cupy_height(test_texture)
        ptx_out = ptx_height(test_texture)
        result = compare_outputs(cupy_out, ptx_out, tolerance=TOLERANCE)
        assert result["matches"], (
            f"Max diff {result['max_diff']} exceeds tolerance {TOLERANCE}"
        )

    def test_cupy_vs_ptx_small(self, small_texture):
        cupy_out = cupy_height(small_texture)
        ptx_out = ptx_height(small_texture)
        result = compare_outputs(cupy_out, ptx_out, tolerance=TOLERANCE)
        assert result["matches"], (
            f"Max diff {result['max_diff']} exceeds tolerance {TOLERANCE}"
        )

    def test_output_shape(self, test_texture):
        out = cupy_height(test_texture)
        h, w = test_texture.shape[:2]
        assert out.shape == (h, w)

    def test_output_range(self, test_texture):
        out = cupy_height(test_texture)
        assert float(cp.min(out)) >= 0.0
        assert float(cp.max(out)) <= 1.0

    def test_invert(self, small_texture):
        normal = cupy_height(small_texture, invert=False)
        inverted = cupy_height(small_texture, invert=True)
        diff = cp.asnumpy(normal + inverted)
        np.testing.assert_allclose(diff, 1.0, atol=0.01)

    def test_contrast_effect(self, small_texture):
        low = cupy_height(small_texture, contrast=0.5)
        high = cupy_height(small_texture, contrast=3.0)
        # Higher contrast should spread values more toward 0 and 1
        std_low = float(cp.std(low))
        std_high = float(cp.std(high))
        assert std_high > std_low
