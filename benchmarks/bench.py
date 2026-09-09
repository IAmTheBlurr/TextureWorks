"""GPU benchmarks comparing CuPy vs PTX map generation performance."""

import gc

import cupy as cp
import numpy as np
from cupyx.profiler import benchmark

MAP_TYPES = ("normal", "height", "ao", "roughness", "metallic", "specular")
MATERIAL_FIELDS = ("detail", "surface_normal", "curvature", "wear", "layer_weight")
RESOLUTIONS = (1024, 2048, 4096)
N_ITERS = 100


def _get_generator(map_type: str, backend: str):
    """Lazy-import the generate function for a given map type and backend."""
    if map_type in MATERIAL_FIELDS:
        prefix = "cupy_ref" if backend == "cupy" else "ptx"
        module = __import__(f"textureworks.{prefix}.material_fields",fromlist=["generate_"+map_type])
        return getattr(module,"generate_"+map_type)
    if backend == "cupy":
        mod = __import__(f"textureworks.cupy_ref.{map_type}", fromlist=[f"generate_{map_type}"])
    else:
        mod = __import__(f"textureworks.ptx.{map_type}", fromlist=[f"generate_{map_type}"])
    return getattr(mod, f"generate_{map_type}")


def make_texture(res: int) -> cp.ndarray:
    """Create a synthetic test texture on GPU."""
    rng = np.random.default_rng(42)
    arr = rng.random((res, res, 3), dtype=np.float32)
    return cp.asarray(arr)


def bench_map(map_type: str, texture: cp.ndarray, backend: str) -> dict:
    """Benchmark a single map type and return timing stats.

    Returns:
        Dict with keys: median_ms, p95_ms.
    """
    gen = _get_generator(map_type, backend)

    args = (texture,) if map_type not in MATERIAL_FIELDS or map_type == "detail" else (cp.ascontiguousarray(texture[:,:,0]),)
    if map_type == "layer_weight": args = (args[0],1-args[0],args[0])
    # Warmup
    _ = gen(*args)
    cp.cuda.Device().synchronize()

    # Timed runs
    perf = benchmark(gen, args=args, n_repeat=N_ITERS, n_warmup=5)
    gpu_times = perf.gpu_times * 1000  # seconds -> ms
    median = float(np.median(gpu_times))
    p95 = float(np.percentile(gpu_times, 95))

    return {"median_ms": median, "p95_ms": p95}


def run_benchmarks():
    """Run full benchmark suite and print results."""
    print("=" * 72)
    print("TextureWorks Benchmark: CuPy vs PTX")
    print("=" * 72)

    for res in RESOLUTIONS:
        print(f"\n--- Resolution: {res}x{res} ---")
        texture = make_texture(res)

        header = f"{'Map Type':<12} {'CuPy med':>10} {'CuPy p95':>10} {'PTX med':>10} {'PTX p95':>10} {'Speedup':>8}"
        print(header)
        print("-" * len(header))

        for mt in MAP_TYPES + MATERIAL_FIELDS:
            try:
                cupy_stats = bench_map(mt, texture, "cupy")
                ptx_stats = bench_map(mt, texture, "ptx")
                speedup = cupy_stats["median_ms"] / ptx_stats["median_ms"] if ptx_stats["median_ms"] > 0 else float("inf")

                print(
                    f"{mt:<12} "
                    f"{cupy_stats['median_ms']:>9.2f}ms "
                    f"{cupy_stats['p95_ms']:>9.2f}ms "
                    f"{ptx_stats['median_ms']:>9.2f}ms "
                    f"{ptx_stats['p95_ms']:>9.2f}ms "
                    f"{speedup:>7.2f}x"
                )
            except Exception as e:
                print(f"{mt:<12} ERROR: {e}")

        # Free GPU memory between resolution tiers
        del texture
        cp._default_memory_pool.free_all_blocks()
        gc.collect()

    print("\n" + "=" * 72)
    print("Benchmark complete.")


if __name__ == "__main__":
    run_benchmarks()
