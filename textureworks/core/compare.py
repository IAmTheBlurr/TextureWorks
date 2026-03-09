"""Pixel-wise comparison between CuPy and PTX implementations."""

import sys
from pathlib import Path

import cupy as cp
import numpy as np


def compare_outputs(
    cupy_result: cp.ndarray,
    ptx_result: cp.ndarray,
    tolerance: int = 2,
) -> dict:
    """Compare two GPU arrays and report agreement metrics.

    Args:
        cupy_result: Reference output from CuPy implementation.
        ptx_result: Output from PTX implementation.
        tolerance: Maximum acceptable per-pixel absolute difference (uint8 scale).

    Returns:
        Dict with keys: matches (bool), max_diff, mean_diff, pct_within_tol.
    """
    # Move to CPU for comparison
    a = cp.asnumpy(cupy_result)
    b = cp.asnumpy(ptx_result)

    # Scale to uint8 range for comparison
    if a.dtype == np.float32 or a.dtype == np.float64:
        a = np.clip(a * 255.0, 0, 255)
        b = np.clip(b * 255.0, 0, 255)

    diff = np.abs(a.astype(np.float32) - b.astype(np.float32))
    max_diff = float(np.max(diff))
    mean_diff = float(np.mean(diff))
    within_tol = float(np.mean(diff <= tolerance) * 100)

    return {
        "matches": max_diff <= tolerance,
        "max_diff": max_diff,
        "mean_diff": mean_diff,
        "pct_within_tolerance": within_tol,
    }


def compare_and_report(
    cupy_result: cp.ndarray,
    ptx_result: cp.ndarray,
    map_name: str,
    tolerance: int = 2,
) -> bool:
    """Compare outputs and print a human-readable report.

    Returns:
        True if outputs match within tolerance.
    """
    result = compare_outputs(cupy_result, ptx_result, tolerance)
    status = "PASS" if result["matches"] else "FAIL"
    print(f"[{status}] {map_name}")
    print(f"  Max pixel difference:    {result['max_diff']:.1f}")
    print(f"  Mean pixel difference:   {result['mean_diff']:.3f}")
    print(f"  Within tolerance ({tolerance}):  {result['pct_within_tolerance']:.2f}%")
    return result["matches"]


if __name__ == "__main__":
    # CLI usage: python -m textureworks.core.compare cupy_ref.normal ptx.normal texture.png
    if len(sys.argv) != 4:
        print("Usage: python -m textureworks.core.compare <cupy_module> <ptx_module> <texture_path>")
        sys.exit(1)

    # Dynamic import and comparison would go here once implementations exist
    print("Comparison CLI ready. Implementations pending.")
