#!/usr/bin/env python3
"""
ctxbench export — dump SQLite bench db into per-model JSON files for
submission, plus a manifest.json describing the machine and method.

Usage:
  python export.py --db bench.db --out results/freya \
      --machine freya --gpu "NVIDIA GeForce RTX 5090" \
      --cpu "Intel(R) Core(TM) Ultra 9 285K" --vram 32606 --ram 63.4 \
      --os "Windows 11" --build 10330 --commit 687e77892
"""
import argparse, json, os, sqlite3, sys, datetime

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--machine", required=True)
    ap.add_argument("--gpu", required=True)
    ap.add_argument("--cpu", required=True)
    ap.add_argument("--vram", type=int, required=True)
    ap.add_argument("--ram", type=float, required=True)
    ap.add_argument("--os", default="Windows 11")
    ap.add_argument("--build", type=int, default=10330)
    ap.add_argument("--commit", default="")
    ap.add_argument("--backend", default="CUDA",
                    help="compute backend: CUDA, ROCm, METAL, CPU, Vulkan (used when DB lacks it)")
    ap.add_argument("--quant", default="Q4_K_M")
    ap.add_argument("--ngl", type=int, default=99)
    ap.add_argument("--kv", default="q8_0")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--depths", default="0,4096,16384,32768,65536")
    ap.add_argument("--models-json", default="models.json",
                    help="manifest for model metadata (key/name/family/params)")
    args = ap.parse_args()

    db = sqlite3.connect(args.db)
    model_meta = {}
    if os.path.exists(args.models_json):
        with open(args.models_json) as f:
            for m in json.load(f)["models"]:
                model_meta[m["key"]] = m

    out_dir = os.path.join(args.out, "runs")
    os.makedirs(out_dir, exist_ok=True)

    # group rows by model_type (llama-bench's model label) — but we want our
    # model_key. Map by model_filename → key from models.json.
    path_to_key = {}
    for m in model_meta.values():
        path_to_key[m["path"].lower()] = m["key"]

    rows = db.execute("""
        SELECT model_filename, n_prompt, n_gen, n_depth, avg_ts, stddev_ts,
               avg_ns, stddev_ns, test_time, gpu_info, cpu_info, build_number,
               build_commit, type_k, type_v, n_gpu_layers, backends
        FROM llama_bench
        ORDER BY model_filename, n_depth, n_prompt, n_gen
    """).fetchall()

    by_model = {}
    for r in rows:
        fn, pp, tg, depth, ts, std, ns, stdns, t, gpu, cpu, bn, bc, tk, tv, ngl, be = r
        key = path_to_key.get(fn.lower())
        if not key:
            # fall back to a slug from the filename
            key = os.path.splitext(os.path.basename(fn))[0][:60]
        by_model.setdefault(key, []).append(r)

    if not by_model:
        print("No rows found in db — run bench.py first.", file=sys.stderr)
        sys.exit(1)

    for key, rows in by_model.items():
        meta = model_meta.get(key, {})
        tests = []
        backends = set()
        for r in rows:
            fn, pp, tg, depth, ts, std, ns, stdns, t, gpu, cpu, bn, bc, tk, tv, ngl, be = r
            if be:
                backends.add(be)
            tests.append({
                "depth": depth,
                "n_prompt": pp,
                "n_gen": tg,
                "avg_ts": round(ts, 3),
                "stddev_ts": round(std, 3),
                "avg_ns": ns,
                "stddev_ns": stdns,
            })
        run = {
            "model_key": key,
            "model_name": meta.get("name", key),
            "family": meta.get("family", ""),
            "params_b": meta.get("params_b", ""),
            "quant": meta.get("quant", args.quant),
            "backend": sorted(backends) or [args.backend],
            "test_date": rows[0][8] or datetime.datetime.utcnow().isoformat(),
            "tests": tests,
        }
        safe = key.replace("/", "_").replace(":", "_")
        with open(os.path.join(out_dir, f"{rows[0][8][:10]}_{safe}.json"), "w") as f:
            json.dump(run, f, indent=2)

    manifest = {
        "machine": args.machine,
        "submitter": os.environ.get("CTXBENCH_SUBMITTER", ""),
        "date": datetime.date.today().isoformat(),
        "hardware": {
            "gpu": args.gpu,
            "vram_mib": args.vram,
            "cpu": args.cpu,
            "ram_gb": args.ram,
            "os": args.os,
        },
        "engine": {
            "name": "llama.cpp",
            "backend": args.backend,
            "build_commit": args.commit,
            "build_number": args.build,
        },
        "method": {
            "quant": args.quant,
            "ngl": args.ngl,
            "kv_cache": args.kv,
            "reps": args.reps,
            "depths": [int(x) for x in args.depths.split(",")],
            "pg_headline": "128,32",
            "pg_depth": "2048,128",
        },
    }
    with open(os.path.join(args.out, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Exported {len(by_model)} models → {args.out}")

if __name__ == "__main__":
    main()
