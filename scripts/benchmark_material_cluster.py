"""Measure only the new material fields using the canonical benchmark runner.

Keep Unity out of Play Mode and avoid concurrent GPU workloads for this run.
"""

import json
from pathlib import Path

import cupy as cp

from benchmarks.bench import MATERIAL_FIELDS, RESOLUTIONS, bench_map, make_texture
from textureworks.core.gpu import get_device_info


def main() -> None:
    report = {"device": get_device_info(), "cupy": cp.__version__,
              "conditions": "Unity editor out of Play Mode; GPU field generators only, 100 repeats after warmup, input validation included.",
              "measurements": []}
    for resolution in RESOLUTIONS:
        texture = make_texture(resolution)
        for generator in MATERIAL_FIELDS:
            row = {"resolution": resolution, "generator": generator}
            for backend in ("cupy", "ptx"):
                row[backend] = bench_map(generator, texture, backend)
            report["measurements"].append(row)
            print(json.dumps(row), flush=True)
        del texture
        cp.get_default_memory_pool().free_all_blocks()
    output = Path(__file__).resolve().parents[1]/"output/material-cluster-field-benchmarks.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
