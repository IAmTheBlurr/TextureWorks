# Claude Code Plan Mode Prompt — TextureWorks

Use this prompt in Claude Code with Plan Mode enabled. Point Claude Code at the
project directory before pasting this prompt.

---

## PROMPT START

I have a project called TextureWorks, a GPU-accelerated library for generating
PBR texture maps from diffuse/albedo input images. The project directory is
already scaffolded with a CLAUDE.md file, algorithm specifications, core
utilities, and package structure. Read CLAUDE.md first, then docs/algorithms.md,
then review all existing files before making any plan.

The project has a critical architectural requirement: every algorithm ships as
dual implementations. A CuPy reference implementation (Python, GPU-accelerated)
and a hand-written PTX implementation (NVIDIA GPU assembly). CuPy validates
correctness. PTX is the primary learning artifact and performance target. The
PTX kernels are loaded into Python via cupy.RawKernel, meaning both
implementations share the same Python test harness and pipeline.

A Python virtual environment is active. All pip installs should use the active
venv. CuPy is already installed for the host CUDA version.

A test texture (textures/test_texture3.png) is available: a sci-fi metallic
panel with clear geometric features, ideal for validating all map types.

### What I need you to plan

Plan the implementation of all six map types in this order:

1. **Normal map** (Sobel gradient to normal encoding)
2. **Height map** (luminance extraction with contrast enhancement)
3. **Ambient Occlusion** (height-field horizon mapping via ray marching)
4. **Roughness map** (local variance plus edge density analysis)
5. **Metallic map** (HSV saturation/value thresholding)
6. **Specular map** (luminance-weighted saturation inversion)

For each map type, the plan must cover these deliverables:

**A. CuPy reference implementation** in `textureworks/cupy_ref/<map_type>.py`
   - A single public function: `generate_<map_type>(texture, **params) -> cp.ndarray`
   - Parameters match docs/algorithms.md with the specified defaults
   - Uses shared utilities from `textureworks/core/io.py` (to_grayscale, rgb_to_hsv)
   - Internal computation in float32, output in [0, 1] range

**B. PTX kernel** in `textureworks/ptx/kernels/<map_type>.ptx`
   - Hand-written PTX assembly (do not just compile CUDA C to PTX)
   - Target sm_75 or higher, PTX ISA 7.0+
   - Heavily commented: every register allocation, memory access pattern,
     and arithmetic operation should have a comment explaining its purpose
   - Block comment header: purpose, grid/block layout, parameter order,
     memory access pattern
   - Use descriptive register names (px_ for pixel, grad_ for gradient, etc.)
   - Boundary checking: threads beyond image dimensions must exit early

**C. Python PTX wrapper** in `textureworks/ptx/<map_type>.py`
   - Loads the .ptx file via cupy.RawKernel
   - Same public function signature as the CuPy version
   - Handles grid/block dimension calculation using core/gpu.py utilities
   - Allocates output arrays, launches kernel, returns result

**D. Test** in `tests/test_<map_type>.py`
   - Loads the test texture via the conftest fixture
   - Generates output via CuPy path
   - Generates output via PTX path
   - Asserts pixel-wise agreement using core/compare.py within the tolerance
     specified in docs/algorithms.md
   - Validates output shape matches input shape
   - Validates output values are in valid range
   - Also runs on the synthetic small_texture fixture for fast CI

**E. Visual verification**
   - After implementing each map type, save the output from both CuPy and PTX
     to the output/ directory using core/io.save_map
   - Naming: <input_name>_<map_type>_cupy.png and <input_name>_<map_type>_ptx.png

### After all six map types

**F. Pipeline orchestrator** in `textureworks/pipeline.py`
   - CLI via click: accepts input image path, output directory, optional
     --map flag to select specific map types, --backend flag (cupy/ptx/both)
   - Generates all requested maps and saves them
   - When --backend=both, also runs comparison and prints the report

**G. Benchmarks** in `benchmarks/bench.py`
   - Time each map type at 1024, 2048, and 4096 resolutions
   - Compare CuPy vs PTX execution time
   - Use cupyx.time.repeat for proper GPU synchronization
   - Print a formatted table of results

### Implementation strategy

Work through the map types sequentially. For each one:
1. Implement the CuPy version first
2. Run it against the test texture and save the output to verify visually
3. Write the PTX kernel
4. Write the PTX Python wrapper
5. Run the comparison test
6. Fix any discrepancies until the test passes

Start with the normal map. It is the simplest algorithm (two 3x3 convolutions
and a normalize step), making it the ideal template for establishing the
CuPy-to-PTX workflow. Every subsequent map type follows the same structure.

### Important constraints

- Do not generate PTX by compiling CUDA C through nvcc. Write PTX directly.
  The educational value of understanding the instruction-level operations is
  the entire point of the PTX path.
- Every PTX kernel must include enough comments for someone unfamiliar with
  PTX to follow the logic.
- The CuPy implementations should be clean and idiomatic. Use CuPy's array
  operations, avoid Python loops over pixels.
- Shared utilities (Gaussian blur, boundary clamping) should be implemented
  once in core/ and reused. For PTX, these can be inline within each kernel
  (PTX does not have a convenient cross-file linking mechanism), with a
  comment noting the shared algorithm.
- All file paths and module references must match the existing project
  structure. Read the existing files to understand the patterns before
  writing new code.

Give me the plan. Do not implement anything yet.

## PROMPT END
