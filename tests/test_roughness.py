"""Tests for roughness map generation — CuPy vs PTX comparison."""

import cupy as cp
import numpy as np
import pytest

from textureworks.core.compare import compare_outputs
from textureworks.cupy_ref.roughness import generate_roughness as cupy_roughness
from textureworks.ptx.roughness import generate_roughness as ptx_roughness

TOLERANCE = 3  # Per algorithms.md


class TestRoughnessMap:
    def test_cupy_vs_ptx_match(self, test_texture):
        cupy_out = cupy_roughness(test_texture)
        ptx_out = ptx_roughness(test_texture)
        result = compare_outputs(cupy_out, ptx_out, tolerance=TOLERANCE)
        assert result["matches"], (
            f"Max diff {result['max_diff']} exceeds tolerance {TOLERANCE}"
        )

    def test_cupy_vs_ptx_small(self, small_texture):
        cupy_out = cupy_roughness(small_texture)
        ptx_out = ptx_roughness(small_texture)
        result = compare_outputs(cupy_out, ptx_out, tolerance=TOLERANCE)
        assert result["matches"], (
            f"Max diff {result['max_diff']} exceeds tolerance {TOLERANCE}"
        )

    def test_output_shape(self, test_texture):
        out = cupy_roughness(test_texture)
        h, w = test_texture.shape[:2]
        assert out.shape == (h, w)

    def test_output_range(self, test_texture):
        out = cupy_roughness(test_texture)
        assert float(cp.min(out)) >= 0.0
        assert float(cp.max(out)) <= 1.0

    def test_uniform_texture_low_roughness(self):
        # Uniform texture should have very low variance/edges -> low roughness
        uniform = cp.full((64, 64, 3), 0.5, dtype=cp.float32)
        out = cupy_roughness(uniform)
        assert float(cp.max(out)) < 0.6
