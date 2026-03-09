# Why Dual Implementations?

TextureWorks implements every algorithm twice: once in CuPy (Python GPU arrays) and once in hand-written PTX (NVIDIA GPU assembly). This document explains the reasoning behind this design.

## The Core Idea

CuPy is the **correctness oracle**. PTX is the **learning artifact and performance target**.

The CuPy implementation is written in high-level Python using GPU array operations. It is easy to read, easy to verify against the mathematical specification, and hard to get wrong. When you need to understand what an algorithm does, read the CuPy version.

The PTX implementation rewrites the same algorithm in NVIDIA's low-level virtual assembly language. It is harder to write, harder to debug, and more verbose. But it teaches GPU programming at the instruction level and can outperform CuPy on algorithms with complex control flow.

## How CuPy and PTX Connect

CuPy provides `cupy.cuda.function.Module`, a mechanism for loading and executing raw PTX source code from Python. The PTX wrappers in `textureworks/ptx/` follow a consistent pattern:

1. Read the `.ptx` source file from `ptx/kernels/`
2. Create a `Module` object and load the PTX bytes
3. Get a kernel function handle via `module.get_function("kernel_name")`
4. Allocate output arrays using CuPy
5. Launch the kernel with grid/block dimensions and argument pointers
6. Return the output as a regular CuPy array

This means PTX kernels integrate seamlessly with CuPy code. You can pass a PTX-generated array to a CuPy operation and vice versa. Several PTX wrappers use CuPy's `gaussian_blur` utility for post-processing, demonstrating this interoperability.

## Why CuPy Over Other Options

**Why not NumPy?** NumPy runs on the CPU. Texture map generation involves per-pixel computation on images with millions of pixels. GPU acceleration provides 10-100x speedups over CPU-only code.

**Why not PyTorch?** PyTorch is designed for deep learning. Its autograd system, module abstractions, and dynamic graph overhead add complexity without benefit for fixed image-processing pipelines. CuPy provides direct GPU array operations with minimal overhead.

**Why not raw CUDA C?** CUDA C requires a separate compilation step, a C toolchain, and loses Python's interactive development workflow. CuPy loads PTX at runtime from source strings, enabling rapid iteration. The Python wrapper handles memory allocation, grid/block sizing, and I/O, keeping the PTX kernels focused on the core algorithm.

## The Tolerance-Based Comparison System

CuPy and PTX implementations produce slightly different results because:

- CuPy uses IEEE-compliant floating-point operations. PTX uses approximate instructions (`rsqrt.approx.f32`, `cos.approx.f32`, `lg2.approx.f32`) for performance.
- The AO kernel uses a polynomial atan2 approximation instead of an exact implementation.
- Floating-point operation ordering differs between vectorized CuPy code and sequential PTX instructions.

The test suite accounts for these differences with per-map-type tolerance values:

| Map Type | Tolerance | Reason |
|----------|-----------|--------|
| Normal | 1 | Rounding only (simple Sobel + normalize) |
| Height | 2 | Blur floating-point variance |
| AO | 3 | Trigonometric approximation in atan2 and power functions |
| Roughness | 3 | Combined variance, edge, and normalization differences |
| Metallic | 2 | Division and clamping precision |
| Specular | 2 | Power function approximation |

Tolerances are measured on the uint8 scale [0, 255]. A tolerance of 2 means the CuPy and PTX outputs may differ by at most 2 intensity levels per pixel, per channel. The `compare_outputs` function in `textureworks/core/compare.py` enforces these bounds.

## Performance Implications

The performance difference between CuPy and PTX varies by algorithm complexity:

**Largest PTX advantage: Ambient Occlusion.** The CuPy implementation uses nested Python `for` loops (one over directions, one over steps). Each iteration launches separate GPU operations. The PTX kernel handles both loops entirely on the GPU in a single launch, eliminating per-iteration launch overhead.

**Near parity: Metallic and Specular.** These algorithms are element-wise operations (load pixel, compute, store). CuPy already executes these efficiently on the GPU. PTX adds minimal improvement.

**Middle ground: Normal, Height, Roughness.** These involve convolution or windowed operations. PTX kernels fuse multiple steps into single launches, providing moderate speedups.

See [Performance: CuPy vs PTX](benchmark-analysis.md) for detailed benchmark analysis.
