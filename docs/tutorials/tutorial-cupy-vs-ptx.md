# Tutorial: Comparing the CuPy and PTX Backends

This tutorial demonstrates the dual-implementation design of TextureWorks. You will generate the same map with both backends, compare the outputs, and understand why small numerical differences are expected.

## Prerequisites

Complete the [First Map Tutorial](tutorial-first-map.md) before starting this one. You should have a working TextureWorks installation with GPU access.

## Step 1: Generate with CuPy

Generate a normal map using the CuPy reference backend:

```bash
python -m textureworks.pipeline textures/test_texture3.png --map normal --backend cupy --output output_cupy/
```

This produces `output_cupy/test_texture3_normal.png`.

## Step 2: Generate with PTX

Generate the same map using the PTX backend:

```bash
python -m textureworks.pipeline textures/test_texture3.png --map normal --backend ptx --output output_ptx/
```

This produces `output_ptx/test_texture3_normal.png`.

## Step 3: Visual Comparison

Open both images side by side. They should look identical to the naked eye. Both backends implement the same Sobel convolution algorithm and produce the same normal map encoding.

The visual match is intentional. The CuPy implementation serves as the correctness oracle. The PTX implementation must produce matching output within a defined tolerance.

## Step 4: Numerical Comparison

Use the comparison CLI to measure the exact pixel-level differences:

```bash
python -m textureworks.core.compare cupy_ref.normal ptx.normal textures/test_texture3.png
```

The report shows four metrics:

- **PASS/FAIL**: whether the maximum difference is within tolerance
- **Max pixel difference**: the largest per-pixel deviation on the 0-255 scale
- **Mean pixel difference**: average deviation across all pixels
- **Within tolerance**: percentage of pixels within the acceptable threshold

For normal maps, the tolerance is 1. A max difference of 1 means a single unit on the 0-255 scale, invisible in the final rendered image.

## Step 5: Understand Why Differences Exist

Both implementations compute the same algorithm, but floating-point arithmetic is not perfectly reproducible across different execution paths. Sources of small differences include:

**Instruction ordering.** CuPy uses optimized library routines for convolution. PTX computes the Sobel convolution manually per-thread. Different operation ordering produces different floating-point rounding.

**Approximate math functions.** The PTX kernels use hardware-accelerated approximate functions like `rsqrt.approx.f32` (reciprocal square root) and `cos.approx.f32`. These trade a few bits of precision for significant speed gains. CuPy uses full-precision equivalents.

**Quantization.** Both backends produce float32 intermediate results, but the final uint8 quantization step (multiply by 255, round, clip) can differ by 1 when a value lands near a rounding boundary.

## Step 6: Compare Other Map Types

Try the comparison with different map types:

```bash
python -m textureworks.core.compare cupy_ref.height ptx.height textures/test_texture3.png
python -m textureworks.core.compare cupy_ref.ao ptx.ao textures/test_texture3.png
python -m textureworks.core.compare cupy_ref.roughness ptx.roughness textures/test_texture3.png
```

Each map type has a different tolerance, reflecting the complexity of its algorithm:

| Map Type | Tolerance | Why |
|----------|-----------|-----|
| Normal | 1 | Simple rounding differences |
| Height | 2 | Gaussian blur floating-point variance |
| AO | 3 | Trigonometric approximations, nested sampling |
| Roughness | 3 | Windowed variance computation differences |
| Metallic | 2 | Division and clamping rounding |
| Specular | 2 | Power function approximation |

AO has the highest tolerance because its PTX kernel uses polynomial approximations for `atan2`, `cos`, `sin`, and power functions (`exp2`/`lg2`), while CuPy uses full-precision `cp.arctan2`, `cp.cos`, and `cp.power`.

## Step 7: Generate with Both Backends Programmatically

The CLI does not have a `--backend=both` flag. For programmatic comparison, use the Python API:

```python
from textureworks.core.io import load_texture
from textureworks.core.compare import compare_and_report
from textureworks.cupy_ref.normal import generate_normal as cupy_normal
from textureworks.ptx.normal import generate_normal as ptx_normal

texture = load_texture("textures/test_texture3.png")
cupy_result = cupy_normal(texture, strength=2.0)
ptx_result = ptx_normal(texture, strength=2.0)

compare_and_report(cupy_result, ptx_result, "normal", tolerance=1)
```

This gives you full control over parameters and tolerance values.

## Key Takeaways

- Both backends produce visually identical output
- Small numerical differences are expected and quantified per map type
- The CuPy implementation is the correctness oracle
- The PTX implementation is the performance target
- The comparison system validates both implementations stay in agreement

## What Next?

- [Tuning Parameters](tutorial-custom-params.md) to customize map output via the Python API
- [Architecture](../explanation/architecture.md) for the design philosophy behind dual implementations
- [Benchmark Analysis](../explanation/benchmark-analysis.md) for performance differences between backends
