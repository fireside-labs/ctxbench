#!/usr/bin/env python3
"""
ctxbench curves — render decode-vs-context curves from a validated
results/ directory. Emits PNG charts into charts/.

Usage:
  python curves.py results/ [--out charts/] [--dpi 150]
"""
import argparse, json, os, sys

def gather(root):
    """Return {machine: {model_key: {depth: avg_ts}}}."""
    data = {}
    for mach in sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))):
        runs_dir = os.path.join(root, mach, "runs")
        if not os.path.isdir(runs_dir):
            continue
        data[mach] = {}
        for fn in sorted(os.listdir(runs_dir)):
            if not fn.endswith(".json"):
                continue
            with open(os.path.join(runs_dir, fn)) as f:
                r = json.load(f)
            model = r.get("model_name", r.get("model_key", fn))
            data[mach][model] = {
                t["depth"]: t["avg_ts"] for t in r.get("tests", [])
                if t.get("n_prompt", 0) > 0 and t.get("n_gen", 0) > 0
            }
    return data

def render(data, out_dir, dpi):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib required: pip install matplotlib", file=sys.stderr)
        sys.exit(1)
    os.makedirs(out_dir, exist_ok=True)
    for mach, models in data.items():
        fig, ax = plt.subplots(figsize=(10, 6))
        for model, curve in models.items():
            if len(curve) < 2:
                continue
            depths = sorted(curve)
            xs = [d / 1000 for d in depths]  # k-tokens
            ax.plot(xs, [curve[d] for d in depths], marker="o", ms=4, label=model)
        ax.set_xlabel("KV-cache depth (k tokens)")
        ax.set_ylabel("decode t/s (pp2048+tg128)")
        ax.set_title(f"decode vs context — {mach}")
        ax.legend(fontsize=7, ncol=2)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        path = os.path.join(out_dir, f"curves_{mach}.png")
        fig.savefig(path, dpi=dpi)
        plt.close(fig)
        print(f"  {path}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("--out", default="charts")
    ap.add_argument("--dpi", type=int, default=150)
    args = ap.parse_args()
    data = gather(args.results)
    if not data:
        print("no data found", file=sys.stderr)
        sys.exit(1)
    render(data, args.out, args.dpi)

if __name__ == "__main__":
    main()
