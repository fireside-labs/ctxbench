#!/usr/bin/env python3
"""
ctxbench — decode-vs-context curve benchmark harness.

Runs llama-bench (llama.cpp b10330+) per model across a prompt/gen sweep
at multiple KV-cache depths, capturing the -o sql output directly into
a SQLite database. One machine, one build, one quant: comparable curves.

Usage:
  python bench.py --models models.json --db bench.db [--reps 3]
  python bench.py --list-db bench.db          # quick summary of what's logged
"""
import argparse, json, os, re, sqlite3, subprocess, sys, time, datetime

BENCH = os.environ.get("LLAMA_BENCH", r"C:\llama-b10330\llama-bench.exe")
DEFAULT_DEPTHS = [0, 4096, 16384, 32768, 65536]
DEFAULT_PG = "2048,128"      # pp,tg used at every depth
HEADLINE_PG = "128,32"       # short prompt for headline pp/tg numbers

def load_manifest(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_db(path):
    db = sqlite3.connect(path)
    db.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT,
            model_key TEXT,
            model_path TEXT,
            model_name TEXT,
            family TEXT,
            params_b TEXT,
            quant TEXT,
            depth INTEGER,
            pg TEXT,
            exit_code INTEGER,
            rows INTEGER,
            error TEXT
        )
    """)
    db.commit()
    return db

def run_bench(model_path, pg, depth, reps, ctk="q8_0", ctv="q8_0"):
    cmd = [
        BENCH,
        "-m", model_path,
        "-pg", pg,
        "-d", str(depth),
        "-ngl", "99",
        "-r", str(reps),
        "-ctk", ctk, "-ctv", ctv,
        "-fa", "auto",
        "-o", "sql",
    ]
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        sql = proc.stdout
        err = proc.stderr[-2000:] if proc.stderr else ""
        return proc.returncode, sql, err, time.time() - t0
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT after 1800s", time.time() - t0
    except Exception as e:
        return -2, "", str(e), time.time() - t0

def ingest_sql(db, sql):
    """Execute llama-bench -o sql output into the db. Returns row count."""
    if not sql or "INSERT INTO llama_bench" not in sql:
        return 0
    try:
        cur = db.cursor()
        cur.executescript(sql)
        db.commit()
        return cur.rowcount
    except Exception as e:
        print(f"  [sql ingest error: {e}]", file=sys.stderr)
        return 0

def summarize(db):
    print(f"{'model':<28} {'quant':<8} {'depth':>7} {'tg t/s':>9}  test")
    cur = db.execute("""
        SELECT model_type, n_depth, n_prompt, n_gen, avg_ts
        FROM llama_bench
        WHERE n_prompt > 0 AND n_gen > 0
        ORDER BY model_type, n_depth, n_prompt, n_gen
        LIMIT 400
    """)
    for model_type, depth, pp, tg, ts in cur.fetchall():
        print(f"{model_type[:28]:<28} {'':8} {depth:>7} {ts:>9.1f}  pp{pp}+tg{tg}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="models.json")
    ap.add_argument("--db", default="bench.db")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--depth", default=",".join(map(str, DEFAULT_DEPTHS)))
    ap.add_argument("--headline-only", action="store_true")
    ap.add_argument("--model-key", default=None, help="only bench this model key")
    ap.add_argument("--list-db", action="store_true")
    args = ap.parse_args()

    if args.list_db:
        summarize(get_db(args.db))
        return

    depths = [int(x) for x in args.depth.split(",")]
    manifest = load_manifest(args.models)
    db = get_db(args.db)
    started = datetime.datetime.utcnow().isoformat()

    for m in manifest["models"]:
        key = m["key"]
        if args.model_key and key != args.model_key:
            continue
        path = m["path"]
        if not os.path.exists(path):
            print(f"[SKIP] {key}: missing {path}")
            db.execute("INSERT INTO runs (started_at, model_key, model_path, model_name, error) VALUES (?,?,?,?,?)",
                       (started, key, path, m.get("name", key), "missing file"))
            db.commit()
            continue

        print(f"\n=== {key} ({m.get('name','')}) ===", flush=True)

        # 1) headline short-prompt numbers
        rc, sql, err, dt = run_bench(path, HEADLINE_PG, 0, args.reps)
        n = ingest_sql(db, sql) if rc == 0 else 0
        print(f"  headline {HEADLINE_PG} d0: rc={rc} rows={n} ({dt:.0f}s)"
              + (f" err={err[-120:]}" if (rc != 0 and err) else ""), flush=True)
        db.execute("INSERT INTO runs (started_at, model_key, model_path, model_name, family, params_b, quant, depth, pg, exit_code, rows, error) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                   (started, key, path, m.get("name", key), m.get("family", ""), m.get("params_b", ""), m.get("quant", ""), 0, HEADLINE_PG, rc, n, err[-500:] if err else ""))
        db.commit()

        # 2) depth sweep for the degradation curve
        for d in depths:
            rc, sql, err, dt = run_bench(path, DEFAULT_PG, d, args.reps)
            n = ingest_sql(db, sql) if rc == 0 else 0
            print(f"  depth {d:>6}: rc={rc} rows={n} ({dt:.0f}s)"
                  + (f" err={err[-150:]}" if (rc != 0 and err) else ""), flush=True)
            db.execute("INSERT INTO runs (started_at, model_key, model_path, model_name, family, params_b, quant, depth, pg, exit_code, rows, error) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                       (started, key, path, m.get("name", key), m.get("family", ""), m.get("params_b", ""), m.get("quant", ""), d, DEFAULT_PG, rc, n, err[-500:] if err else ""))
            db.commit()

    db.close()
    print("\nDone. Summary:")
    summarize(sqlite3.connect(args.db))

if __name__ == "__main__":
    main()
