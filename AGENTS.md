# TextureWorks agent guide

## Scope and working approach

This is the primary repository guide for Codex using GPT-6 Astra. Follow the
user's current instructions within system and developer constraints. Use this
file for repository workflow; treat [CLAUDE.md](CLAUDE.md) as historical context
where it disagrees with this guide. Verify behavior against source and tests.
Resolve discrepancies with the algorithm specifications before changing their
contract. Planning documents describe proposals until implementation is verified.

- Carry the requested effort through implementation, validation, commits, push,
  and any applicable PR merge. Make routine decisions using project context.
- Ask only when missing information materially affects scope, correctness, or
  authorization. Continue independent work while clarification is pending.
- Preserve the active objective when the user adds a correction or side question.
  Read only the context needed for the work; keep useful findings across turns.
- If a skill instruction blocks progress, identify the file and exact instruction,
  explain its effect, and check whether the user already authorized the action.
- Batch independent reads and checks. Use subagents only when session instructions
  authorize them and there is a bounded task that can run independently.
- Keep validation proportional to the change. Once applicable checks pass, repeat
  or broaden them only to resolve a new change, failure, or remaining concern.

These choices follow the [official GPT-6 Astra guidance](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-6-astra).
This file guides agent behavior; model selection belongs to the Codex session.

## Repository and delivery workflow

Repository: <https://github.com/IAmTheBlurr/TextureWorks>. Use `git` for local
history and `gh` for GitHub operations. The integration branch is `main`.

1. Start with `git status --short --branch`, `git remote -v`, `git fetch origin`,
   and relevant history. Confirm the remote and upstream before publishing.
   Inspect existing edits and untracked files; preserve work outside the effort.
2. Prefer a focused `codex/<effort>` branch based on current `origin/main` for
   new efforts, unless the user specifies a branch or work is already underway.
   Branches and PRs should provide useful historical context for future agents.
3. Make atomic commits on every branch, including `main`: one coherent change
   per commit, with a message that explains its purpose. Stage owned paths
   explicitly and inspect the staged diff. Keep unrelated files out of commits.
4. Push completed commits to `origin` at meaningful checkpoints and before
   reporting completion. Use `git push -u origin <branch>` for a new branch.
   If publishing fails, retain the commits and report the specific blocker.
5. For a new branch, create a PR targeting `main` when the effort is complete.
   Explain the problem, resulting behavior, relevant design decisions, and actual
   validation, including skips or limitations. Use a temporary file outside the
   repository with `gh pr create --body-file` for multiline descriptions.
6. Review the final diff, check PR reviews and applicable CI with `gh`, and resolve
   issues. Merge when relevant tests and required checks pass and no unresolved
   issue remains. The user has authorized routine pushes, PR creation, and these
   merges; another confirmation is unnecessary. Respect repository protections.
   Prefer a merge commit (`gh pr merge --merge --match-head-commit <sha>`) to
   preserve atomic commits and branch context. Do not bypass failing checks.
7. After merging, fetch and bring local `main` forward with `git pull --ff-only`
   when it is safe to switch. Verify local `main` and `origin/main` agree. If local
   work prevents switching or updating, preserve it and explain the remaining step.

Never discard user edits, rewrite published history, or use destructive resets
to make the workspace clean. Keep credentials, virtual environments, temporary
reports, and generated outputs out of commits unless the user requests an asset.
Report local test evidence and GitHub checks separately; absent CI is not a CI pass.

## Project map and contracts

TextureWorks is a headless Python library and CLI that derives six PBR maps from
diffuse/albedo images: `normal`, `height`, `ao`, `roughness`, `metallic`, and
`specular`. Each algorithm has a CuPy reference and a handwritten PTX implementation.
CuPy provides the correctness oracle; PTX supports GPU learning and performance.

| Area | Responsibility |
| --- | --- |
| `textureworks/core/` | Image I/O, blur, comparison, GPU device and launch helpers |
| `textureworks/cupy_ref/` | Reference `generate_<map_type>()` functions |
| `textureworks/ptx/` | Matching Python wrappers and cached CUDA modules |
| `textureworks/ptx/kernels/` | Readable, commented PTX source |
| `textureworks/pipeline.py` | CLI, backend selection, map registration and orchestration |
| `tests/` | Backend parity, shape, range, and semantic checks |
| `benchmarks/bench.py` | GPU timing for both implementations |
| `unity/` | Reusable HLSL for consuming generated maps in Unity |
| `docs/algorithms.md` | Mathematical specifications and comparison tolerances |

Read [contributing](docs/dev/contributing.md) and [testing](docs/dev/testing.md)
for implementation work. Consult [API reference](docs/reference/api.md),
[output conventions](docs/reference/output-conventions.md), and
[architecture](docs/explanation/architecture.md) as needed. Keep documentation in
the existing tutorial, how-to, reference, and explanation structure.

- Maintain Python 3.10 compatibility, public type hints and concise docstrings.
  Prefer functions; introduce classes when state warrants them.
- Keep backend function names, parameters, defaults, and return contracts aligned.
  Add a map's specification, both implementations, tests, pipeline registration,
  benchmark registration, and relevant documentation together.
- Use `cupy.ndarray` for GPU computation and `numpy.ndarray` for CPU data. Make
  transfers explicit with `cp.asarray`, `cp.asnumpy`, or `.get()`. Avoid loops over
  pixels in the reference path and unnecessary GPU synchronization or transfers.
- The standard input is float32 RGB `(H, W, 3)` in `[0, 1]`. The loader drops RGBA
  alpha and retains grayscale as `(H, W)`; check each generator's input contract
  before assuming grayscale works throughout the pipeline.
- Generator outputs are float32 in `[0, 1]`: RGB normals or scalar `(H, W)` maps.
  `save_map` defaults to 8-bit output; `bits=16` rounds scalar maps to 16-bit PNG.
  The CLI selects height precision with `--height-bits 8|16`. Filenames remain
  `<input_stem>_<map_type>.png`; loading 16-bit grayscale preserves its precision.
  Normals encode XYZ in RGB; the neutral float value is `(0.5, 0.5, 1.0)`.
  Preserve actual quantization behavior when checking encoded bytes.
- The pipeline defaults to `ptx`. AO can reuse a height map generated earlier in
  the requested map order. Preserve this dependency and verify order-sensitive
  behavior when changing orchestration.
- PTX currently uses `.version 7.0`, `.target sm_75`, 64-bit addresses, and 16x16
  blocks via shared launch helpers. Keep compatibility unless a change calls for
  another target. Document purpose, launch geometry, parameters, memory access,
  and non-obvious instructions. Guard image bounds and match reference edge rules.
- Existing wrappers load PTX through `cp.cuda.function.Module`, `mod.load`, and
  `get_function`, with cached modules and explicit pointer/scalar arguments.
  Follow this pattern; the `RawKernel(..., backend="nvptx")` example in `CLAUDE.md`
  does not describe the current implementation.

## Environment and commands

Work from the repository root. On Windows, prefer the explicit project interpreter
`.\.venv\Scripts\python.exe` rather than assuming an
activated environment. On other systems use the equivalent virtual environment.
Check interpreter, CUDA, and CuPy availability before relying on older setup notes.
CuPy is installed separately because its package must match the CUDA environment.
Use `python -m pip` through the selected interpreter for dependency installation.

```powershell
# GPU access
.\.venv\Scripts\python.exe -c "from textureworks.core.gpu import print_device_info; print_device_info()"

# All tests, or one affected map
.\.venv\Scripts\python.exe -m pytest tests/ -v
.\.venv\Scripts\python.exe -m pytest tests/test_normal.py -v

# CLI help and map generation
.\.venv\Scripts\python.exe -m textureworks.pipeline --help
.\.venv\Scripts\python.exe -m textureworks.pipeline textures/test_texture3.png --backend ptx --output output/
.\.venv\Scripts\python.exe -m textureworks.pipeline textures/test_texture3.png --backend cupy --map normal --output output/

# Benchmarks; module invocation keeps the repository root on the import path
.\.venv\Scripts\python.exe -m benchmarks.bench
```

`textureworks.core.compare` exposes working comparison functions, but its CLI
currently prints a placeholder. Use pytest or call `compare_outputs` directly.
There is no configured lint/type-check command or GitHub Actions workflow at
onboarding; inspect configuration again before selecting future checks.

## Validation and completion

- For algorithm or kernel changes, test affected behavior and backend parity,
  including boundaries and parameter effects where relevant. Run the full pytest
  suite before merging executable changes. Both backends require a working GPU.
- Existing maximum differences on the 0-255 scale are normal `1`, height `2`, AO
  `3`, roughness `3`, metallic `2`, and specular `2`. Keep tolerances consistent
  with specifications; investigate divergence before considering a tolerance change.
- Real texture tests use `textures/test_texture3.png`; synthetic tests use a 64x64
  fixture. Missing real assets cause skips. Report skips and environment failures
  explicitly. Backend agreement alone does not establish visual quality; inspect
  generated maps when a change affects appearance.
- For documentation changes, inspect the diff, verify paths and command claims,
  and run `git diff --check`. Add tests when behavior needs coverage. Avoid tests
  that merely repeat documentation or implementation details.
- Run benchmarks for performance work or an explicit request. The current runner
  uses `cupyx.profiler.benchmark`, warmup, and 100 repeats at 1024, 2048, and 4096,
  reporting median and p95 GPU time. Inspect its output for per-map errors even
  if the process exits successfully. Record hardware and environment for claims.
- For Parallax Occlusion Mapping shader changes, use the Unity GPU harness in
  `scripts/test-unity-parallax.ps1` and inspect its preview. The integration guide
  is `docs/how-to/parallax-occlusion-mapping.md`. Report HLSL conformance separately
  from acceptance of a consuming Shader Graph material or target platform build.

Use concise, connected prose in updates and final responses. Lead with the result,
then relevant evidence and limitations. Explain what changed and why. Avoid canned
conclusions, invented compound labels, contrastive framing, and phrases such as
"Bottom Line," "delve," "foster," "leverage," "it's worth noting," "importantly,"
"genuinely," "In short," or "The simplest mental model is." Provide the commit or
PR link and synchronization status when reporting a completed change effort.
