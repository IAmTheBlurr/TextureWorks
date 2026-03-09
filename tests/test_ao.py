"""Tests for ambient occlusion map generation — CuPy vs PTX comparison."""

import cupy as cp
import numpy as np
import pytest

from textureworks.core.compare import compare_outputs
from textureworks.cupy_ref.ao import generate_ao as cupy_ao
from textureworks.cupy_ref.height import generate_height as cupy_height
from textureworks.ptx.ao import generate_ao as ptx_ao

TOLERANCE = 3  # Per algorithms.md


class TestAOMap:
    def test_cupy_vs_ptx_match(self, test_texture):
        # Use same height map for both to isolate AO comparison
        hmap = cupy_height(test_texture)
        cupy_out = cupy_ao(test_texture, height_map=hmap)
        ptx_out = ptx_ao(test_texture, height_map=hmap)
        result = compare_outputs(cupy_out, ptx_out, tolerance=TOLERANCE)
        assert result["matches"], (
            f"Max diff {result['max_diff']} exceeds tolerance {TOLERANCE}"
        )

    def test_cupy_vs_ptx_small(self, small_texture):
        hmap = cupy_height(small_texture)
        cupy_out = cupy_ao(small_texture, height_map=hmap)
        ptx_out = ptx_ao(small_texture, height_map=hmap)
        result = compare_outputs(cupy_out, ptx_out, tolerance=TOLERANCE)
        assert result["matches"], (
            f"Max diff {result['max_diff']} exceeds tolerance {TOLERANCE}"
        )

    def test_output_shape(self, test_texture):
        out = cupy_ao(test_texture)
        h, w = test_texture.shape[:2]
        assert out.shape == (h, w)

    def test_output_range(self, test_texture):
        out = cupy_ao(test_texture)
        assert float(cp.min(out)) >= 0.0
        assert float(cp.max(out)) <= 1.0

    def test_auto_height_generation(self, small_texture):
        # Should work without explicit height map
        out = cupy_ao(small_texture)
        assert out.shape == small_texture.shape[:2]

    def test_flat_surface_bright(self):
        # A perfectly flat height map should produce high AO (bright)
        flat_hmap = cp.full((32, 32), 0.5, dtype=cp.float32)
        flat_tex = cp.full((32, 32, 3), 0.5, dtype=cp.float32)
        out = cupy_ao(flat_tex, height_map=flat_hmap)
        assert float(cp.mean(out)) > 0.8
