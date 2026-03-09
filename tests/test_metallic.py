"""Tests for metallic map generation -- CuPy vs PTX comparison."""

import cupy as cp
import numpy as np
import pytest

from textureworks.core.compare import compare_outputs
from textureworks.cupy_ref.metallic import generate_metallic as cupy_metallic
from textureworks.ptx.metallic import generate_metallic as ptx_metallic

TOLERANCE = 2  # Per algorithms.md


class TestMetallicMap:
    def test_cupy_vs_ptx_match(self, test_texture):
        cupy_out = cupy_metallic(test_texture)
        ptx_out = ptx_metallic(test_texture)
        result = compare_outputs(cupy_out, ptx_out, tolerance=TOLERANCE)
        assert result["matches"], (
            f"Max diff {result['max_diff']} exceeds tolerance {TOLERANCE}"
        )

    def test_cupy_vs_ptx_small(self, small_texture):
        cupy_out = cupy_metallic(small_texture)
        ptx_out = ptx_metallic(small_texture)
        result = compare_outputs(cupy_out, ptx_out, tolerance=TOLERANCE)
        assert result["matches"], (
            f"Max diff {result['max_diff']} exceeds tolerance {TOLERANCE}"
        )

    def test_output_shape(self, test_texture):
        out = cupy_metallic(test_texture)
        h, w = test_texture.shape[:2]
        assert out.shape == (h, w)

    def test_output_range(self, test_texture):
        out = cupy_metallic(test_texture)
        assert float(cp.min(out)) >= 0.0
        assert float(cp.max(out)) <= 1.0

    def test_hard_edges(self, small_texture):
        soft = cupy_metallic(small_texture, hard_edges=False)
        hard = cupy_metallic(small_texture, hard_edges=True)
        # Hard edges should only contain 0.0 or 1.0
        unique_vals = cp.unique(hard)
        for v in unique_vals.get():
            assert v == 0.0 or v == 1.0
