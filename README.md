# ctxbench — decode-vs-context curves for local LLMs

**Peak tokens/sec is marketing. The curve is the truth.**

Every local-LLM benchmark you've seen quotes one number: peak decode t/s
at a tiny context. Real usage lives at 10k-130k context, where KV-cache
growth degrades throughput. Nobody publishes that curve. This project
does, with a reproducible methodology anyone can run.

## What this is

A standardized way to measure and share **how decode speed degrades as
context grows**, across models, hardware, and engines:

- One build (llama.cpp b10330), one quant (Q4_K_M), one machine per run
- Prompt/gen sweep (`-pg`) at multiple KV-cache depths (`-d 0 → 65536`)
- Full hardware fingerprint logged with every run (GPU, CPU, build commit,
  kv cache type, ngl, threads)
- SQLite-native output (llama-bench `-o sql`) → every run is one file
- Community submissions via pull request, validated by CI

## Quick start

```bash
# Run the benchmark on your machine (llama.cpp b10330+ required)
python bench.py --models models.json --db bench.db

# Export your results for submission
python export.py --db bench.db --out results/your-machine/

# Submit: open a PR with the results/ folder
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the submission schema.

## The schema (why you can trust the numbers)

Every result row carries its own hardware fingerprint:

| Column | Meaning |
|---|---|
| `build_commit` / `build_number` | exact llama.cpp build |
| `gpu_info` / `cpu_info` | full device strings |
| `backends` | CUDA / Metal / Vulkan / CPU |
| `n_prompt` / `n_gen` | the test: pp + tg sizes |
| `n_depth` | KV-cache depth (the curve x-axis) |
| `avg_ts` / `stddev_ts` | tokens/sec ± stddev |
| `type_k` / `type_v` | KV cache quant (q8_0 standard) |
| `n_gpu_layers` / `n_cpu_moe` | offload config |

## Methodology rules

1. **llama.cpp b10330 or newer.** Gemma 4 / MTP kernels require current
   builds; stale builds produce garbage curves. Pin your build, log it.
2. **Q4_K_M quant** as the comparison standard. Log the actual quant.
3. **`-ngl 99`** full GPU offload (or log the real number).
4. **KV cache q8_0** (`-ctk q8_0 -ctv q8_0`) — the standard for long
   context on consumer GPUs.
5. **Depths: 0, 4096, 16384, 32768, 65536.** The curve, not a point.
6. **`-r 3`** repetitions for stddev.
7. No warmup tricks, no cherry-picked runs. CI validates the format.

## Roadmap

- [x] Harness + SQLite ingestion
- [ ] Seed data: 23 models on RTX 5090 (Freya)
- [ ] CI validation for PR submissions
- [ ] LEADERBOARD.md renderer (auto-generated)
- [ ] Curve charts (plotly / matplotlib)
- [ ] vLLM / SGLang support via llama-benchy integration

## License

MIT
