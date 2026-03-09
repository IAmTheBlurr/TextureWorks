"""GPU device detection, selection, and capability reporting."""

import cupy as cp


def get_device_info(device_id: int = 0) -> dict:
    """Report GPU capabilities for the specified device.

    Returns:
        Dict with name, compute_capability, total_memory_mb, free_memory_mb.
    """
    with cp.cuda.Device(device_id):
        props = cp.cuda.runtime.getDeviceProperties(device_id)
        free, total = cp.cuda.runtime.memGetInfo()
    return {
        "name": props["name"].decode(),
        "compute_capability": f"{props['major']}.{props['minor']}",
        "total_memory_mb": total / (1024 * 1024),
        "free_memory_mb": free / (1024 * 1024),
        "sm_count": props["multiProcessorCount"],
        "max_threads_per_block": props["maxThreadsPerBlock"],
    }


def print_device_info(device_id: int = 0) -> None:
    """Print GPU info to stdout."""
    info = get_device_info(device_id)
    print(f"GPU: {info['name']}")
    print(f"  Compute capability: {info['compute_capability']}")
    print(f"  SMs: {info['sm_count']}")
    print(f"  VRAM: {info['total_memory_mb']:.0f} MB total, {info['free_memory_mb']:.0f} MB free")
    print(f"  Max threads/block: {info['max_threads_per_block']}")


def recommended_block_size() -> tuple[int, int]:
    """Return a reasonable 2D block size for image processing kernels.

    Returns:
        Tuple of (block_x, block_y). Typically (16, 16) = 256 threads.
    """
    return (16, 16)


def grid_size(width: int, height: int, block: tuple[int, int] = (16, 16)) -> tuple[int, int]:
    """Compute grid dimensions to cover an image.

    Args:
        width: Image width in pixels.
        height: Image height in pixels.
        block: Block dimensions (threads_x, threads_y).

    Returns:
        Tuple of (grid_x, grid_y).
    """
    gx = (width + block[0] - 1) // block[0]
    gy = (height + block[1] - 1) // block[1]
    return (gx, gy)
