# Benchmark Analysis: CuPy vs PTX Performance

This document explains the performance characteristics of the CuPy and PTX implementations, why different map types show different speedup ratios, and when each backend is the better choice.

## Benchmark Methodology

TextureWorks benchmarks use `cupyx.profiler.benchmark` for GPU timing. This function handles CUDA synchronization automatically, ensuring measurements reflect actual GPU execution time rather than just kernel launch overhead.

Each benchmark runs:
- 5 warmup iterations (discarded) to populate caches and trigger JIT compilation
- 100 timed iterations for statistical significance
- Measurements at three resolutions: 1024x1024, 2048x2048, 4096x4096
- Reports median and 95th percentile GPU time in milliseconds

Run the benchmarks with:

```bash
python benchmarks/bench.py
```

The benchmark script tests all six map types across both backends at each resolution, then computes the PTX speedup ratio (CuPy median / PTX median).

## Performance Patterns by Map Type

### AO: Largest PTX Advantage

Ambient occlusion shows the most dramatic speedup because the CuPy implementation contains nested Python-level loops. For each pixel, the CuPy version iterates over `num_directions` (default 16) directions, and within each direction iterates over `max_steps` (default 20) steps. Each loop body launches a separate CuPy kernel for the vectorized pixel operations.

```python
# CuPy AO: two nested Python loops = 16 * 20 = 320 kernel launches per frame
for d in range(num_directions):      # 16 iterations
    for s in range(1, max_steps + 1): # 20 iterations
        # Each line here is a separate GPU kernel launch
        sx = x_coords + cos_a[d] * s * step_scale
        sy = y_coords + sin_a[d] * s * step_scale
        ...
```

The PTX kernel performs the entire computation in a single kernel launch. Every thread handles all 16 directions and all 20 steps internally. This eliminates kernel launch overhead and keeps the GPU fully occupied.

At 4096x4096, the difference becomes stark. CuPy launches 320+ separate kernels with Python interpreter overhead between each. PTX launches one kernel where each of the 16 million threads runs the complete algorithm.

### Roughness: Moderate PTX Advantage

Roughness uses three PTX kernels (variance, Sobel edge, blend) compared to CuPy's sequence of vectorized operations. The advantage comes from:

1. The variance kernel computes local mean and variance in a single pass over the neighborhood window. CuPy uses separate array operations for mean and squared-difference accumulation.
2. Normalization and blending happen in a single kernel pass rather than multiple CuPy element-wise operations.

Post-processing steps (Gaussian blur, contrast) use CuPy's `cupyx.scipy.ndimage.convolve1d` in both backends, so those phases show no speed difference.

### Normal: Moderate PTX Advantage

The normal map kernel performs a 3x3 Sobel convolution, gradient computation, normalization, and RGB encoding in a single kernel. Each thread loads 9 neighbor values, applies the Sobel weights, normalizes the result, and stores 3 output channels.

CuPy uses `cupyx.scipy.ndimage.convolve` for the Sobel pass, which is already an optimized GPU kernel. The PTX advantage comes from fusing the convolution, normalization, and encoding into a single pass, avoiding intermediate memory writes.

### Height: Moderate PTX Advantage

The height pipeline runs four sequential PTX kernels: normalize, horizontal blur, vertical blur, and contrast. CuPy performs similar steps through separate operations. The PTX kernels are individually tight, but the multi-kernel pipeline reduces the margin compared to fused single-kernel maps.

### Metallic and Specular: Near Parity

These maps are already element-wise operations in CuPy. The metallic kernel classifies each pixel based on saturation and value thresholds. The specular kernel computes a weighted luminance-saturation score. CuPy handles element-wise operations efficiently because they map naturally to GPU parallelism.

Both backends also share the same Gaussian blur post-processing step (CuPy's `convolve1d`). The PTX kernel only replaces the classification or scoring phase, which is a small fraction of the total computation.

## Resolution Scaling

Performance differences tend to grow with resolution. At 1024x1024, kernel launch overhead is a larger fraction of total execution time for both backends. At 4096x4096 (16 million pixels), the per-pixel computation dominates, and algorithmic efficiency matters more.

Maps with nested loops (AO) show the strongest resolution scaling in PTX speedup. Element-wise maps (metallic, specular) maintain near-parity across all resolutions because both backends already saturate the GPU's compute units.

## When to Use Each Backend

### Choose PTX when:
- Processing large textures (2048x2048 and above) where execution time matters
- Running AO generation, which shows the largest performance gap
- Batch-processing many textures in a pipeline
- Building production asset pipelines where throughput is a priority

### Choose CuPy when:
- Prototyping new algorithms before writing PTX
- Debugging output correctness (CuPy is the correctness oracle)
- Working with small textures where the difference is negligible
- Generating metallic or specular maps where both backends perform similarly
- Modifying algorithm parameters frequently during development (CuPy code is easier to edit)

### Default recommendation

The CLI defaults to `--backend=ptx` for a reason: it is faster or equivalent for all map types at all resolutions. The CuPy backend exists as the correctness reference and as a more readable implementation for learning.

## Understanding Benchmark Output

The benchmark script prints a table like this:

```
--- Resolution: 2048x2048 ---
Map Type      CuPy med   CuPy p95    PTX med    PTX p95  Speedup
--------------------------------------------------------------------
normal          X.XXms     X.XXms     X.XXms     X.XXms    X.XXx
height          X.XXms     X.XXms     X.XXms     X.XXms    X.XXx
ao              X.XXms     X.XXms     X.XXms     X.XXms    X.XXx
roughness       X.XXms     X.XXms     X.XXms     X.XXms    X.XXx
metallic        X.XXms     X.XXms     X.XXms     X.XXms    X.XXx
specular        X.XXms     X.XXms     X.XXms     X.XXms    X.XXx
```

**Median** is the most representative timing. It filters out outlier iterations caused by GPU frequency scaling, system interrupts, or thermal throttling.

**P95** (95th percentile) shows worst-case behavior. A large gap between median and p95 suggests inconsistent GPU scheduling or thermal throttle events.

**Speedup** is `CuPy median / PTX median`. Values above 1.0 mean PTX is faster. Values near 1.0 mean the backends perform similarly.

## Further Reading

- [Architecture](architecture.md) for the dual-implementation design philosophy
- [PTX Kernel Reference](../reference/ptx-kernels.md) for kernel-level optimization details
- [API Reference](../reference/api.md) for benchmark function signatures
