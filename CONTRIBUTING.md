# Contributing — the submission schema

This project lives or dies on one thing: **numbers that can't be cheated
by accident.** Every submission is a folder of JSON exports plus a
`manifest.json`. CI validates everything before merge.

## How to submit

1. Install llama.cpp **b10330 or newer** (Windows CUDA zip, or build it).
2. Run the harness on your machine:
   ```bash
   python bench.py --models models.json --db bench.db
   ```
3. Export your runs:
   ```bash
   python export.py --db bench.db --out results/<your-machine-name>
   ```
4. Open a pull request with the new `results/<your-machine-name>/` folder.

## Directory layout

```
results/
  freya/
    manifest.json          # one per machine, hardware fingerprint
    runs/
      2026-08-08_qwen3.6-35b-a3b.json
      2026-08-08_gemma-4-31b.json
      ...
```

## manifest.json (required)

```json
{
  "machine": "freya",
  "submitter": "github-username-or-anon",
  "date": "2026-08-08",
  "hardware": {
    "gpu": "NVIDIA GeForce RTX 5090",
    "vram_mib": 32606,
    "cpu": "Intel(R) Core(TM) Ultra 9 285K",
    "ram_gb": 63.4,
    "os": "Windows 11"
  },
  "engine": {
    "name": "llama.cpp",
    "backend": "CUDA",
    "build_commit": "687e77892",
    "build_number": 10330
  },
  "method": {
    "quant": "Q4_K_M",
    "ngl": 99,
    "kv_cache": "q8_0",
    "reps": 3,
    "depths": [0, 4096, 16384, 32768, 65536],
    "pg_headline": "128,32",
    "pg_depth": "2048,128"
  }
}
```

## Per-run JSON (required)

One file per model. The tool generates this from the SQLite db. Each
entry must include:

```json
{
  "model_key": "qwen3.6-35b-a3b",
  "model_name": "Qwen3.6-35B-A3B",
  "family": "qwen",
  "params_b": "35",
  "quant": "Q4_K_M",
  "backend": ["CUDA"],
  "test_date": "2026-08-08T04:52:02Z",
  "tests": [
    {
      "depth": 0,
      "n_prompt": 2048,
      "n_gen": 128,
      "avg_ts": 123.4,
      "stddev_ts": 1.2,
      "avg_ns": 1234567,
      "stddev_ns": 12000
    }
  ]
}
```

## What CI rejects

- Missing or unparseable `manifest.json`
- Hardware fingerprint mismatches between manifest and run files
- `build_number < 10330` (stale builds = garbage curves)
- Unknown `engine.backend` (must be CUDA, ROCm, METAL, CPU, Vulkan, MLX, ...)
- Tests not covering the base depth set `[0, 4096, 16384, 32768, 65536]`
  (deeper depths are welcome — a model benched to 131072 is strictly better)
- `avg_ts <= 0` or `stddev_ts < 0`
- Duplicate `model_key` within a submission

## Multi-vendor / multi-backend

The leaderboard is engine- and backend-aware on purpose:

- **`engine.name`**: llama.cpp, vLLM, MLX, Ollama, ... whatever actually ran
  the inference.
- **`engine.backend`**: the compute backend — CUDA (NVIDIA), ROCm (AMD),
  METAL (Apple), CPU, Vulkan, OPENCL, SYCL, MLX.
- **`runs.backend`**: same value per run file, so rows are filterable by
  stack in the leaderboard.

AMD (ROCm) and Apple (METAL/MLX) submissions are first-class. If your
runner isn't llama-bench, keep the depth set and `pg 2048,128` protocol
where your engine supports it, and document any divergence in the PR
description so the curve stays comparable.

## Rules of the road

- **No cherry-picking.** Submit everything the harness produced.
- **No cross-machine mixing** in one folder. One manifest per machine.
- **Honest hardware.** Don't rename your GPU. The curve will out you.
- **No opinions in data files.** Keep commentary in the PR description.
