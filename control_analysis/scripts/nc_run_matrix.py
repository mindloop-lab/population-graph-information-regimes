#!/usr/bin/env python3
"""Run the full negative-control matrix (2 splits x 5 folds x 3 seeds x 2 regimes).

Each cell is a separate process (separate output file); P0 and P1 never share state.
Add --dropout 0.2 for the stochastic diagnostic (written to a separate cells dir).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get("PAPERA_REPO", ".")).resolve()
PY = Path(os.environ.get("PAPERA_PYTHON", sys.executable))
SPLIT = Path(os.environ.get("PAPERA_SPLITS", REPO / "splits/mixed_site_dx_5fold_v2.csv"))


def one(args):
    ss, fold, ts, regime, dropout, cells_dir = args
    out = cells_dir / f"{regime}_s{ss}_f{fold}_t{ts}.json"
    if out.is_file():
        try:
            json.loads(out.read_text())
            return f"skip {out.name}"
        except Exception:
            pass
    cmd = [str(PY), str(HERE / "nc_cell.py"), "--features-dir", str(HERE),
           "--split-registry", str(SPLIT), "--split-seed", str(ss), "--fold", str(fold),
           "--train-seed", str(ts), "--regime", regime, "--dropout", str(dropout),
           "--out", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        (HERE / "logs" / f"{out.stem}.err").write_text(r.stdout + "\n" + r.stderr)
        return f"FAIL {out.name}"
    return f"ok   {out.name}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dropout", type=float, default=0.0)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    cells_dir = HERE / ("cells" if args.dropout == 0 else "cells_dropout")
    cells_dir.mkdir(exist_ok=True)
    (HERE / "logs").mkdir(exist_ok=True)
    jobs = [(ss, f, t, reg, args.dropout, cells_dir)
            for ss in (1024, 2024) for f in range(5) for t in (11, 22, 33) for reg in ("P0", "P1")]
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        for i, msg in enumerate(ex.map(one, jobs), 1):
            print(f"[{i:2d}/{len(jobs)}] {msg}", flush=True)
    print(f"done in {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
