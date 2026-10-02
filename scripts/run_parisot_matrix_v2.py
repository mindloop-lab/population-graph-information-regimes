#!/usr/bin/env python3
"""Resumable Parisot controlled matrix driver, extended scope (WP7).

Two jobs, selected by --scaling-scope:
  cohort  -> complete the frozen matrix for the two remaining split seeds
             (2024, 2025); existing 15 cells under results/parisot are reused.
  f-only  -> re-run all 45 cells with the B12#1 fix (sigma and lambda_max
             derived from the fit partition only) into results/parisot_fonly.

No new model / dataset / hyper-parameter: the only change is the scope from
which the two graph-scaling constants are derived.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PY = REPO / ".venv" / "bin" / "python"
DATA_ROOT = Path(os.environ.get("PAPER_A_DATA_ROOT", "data/curated/abide1_canonical_variants/magp_abide1_v1_legacy_matched"))
SPLIT = REPO / "splits/mixed_site_dx_5fold_v2.csv"
SEEDS = [1024, 2024, 2025]
FOLDS = [0, 1, 2, 3, 4]
TRAIN_SEEDS = [11, 22, 33]

ENV = dict(os.environ)
ENV["PYTHONPATH"] = str(REPO)
for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    ENV[v] = "8"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scaling-scope", choices=["cohort", "f-only"], default="cohort")
    ap.add_argument("--device", default="cuda:1")
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--checkpoint-dir", type=Path, default=None)
    args = ap.parse_args()

    out_dir = args.out_dir or (REPO / "results/parisot" if args.scaling_scope == "cohort"
                               else REPO / "results/parisot_fonly")
    ckpt_dir = args.checkpoint_dir or (REPO / "checkpoints/parisot" if args.scaling_scope == "cohort"
                                       else REPO / "checkpoints/parisot_fonly")
    log_dir = REPO / "logs" / f"parisot_matrix_{args.scaling_scope.replace('-', '')}"
    for d in (out_dir, ckpt_dir, log_dir):
        d.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    ok = skip = fail = 0
    for ss in SEEDS:
        for fold in FOLDS:
            for ts in TRAIN_SEEDS:
                out = out_dir / f"pa_{ss}_{fold}_{ts}.json"
                if out.is_file():
                    try:
                        json.loads(out.read_text())
                        skip += 1
                        continue
                    except Exception:
                        pass
                with (log_dir / f"pa_{ss}_{fold}_{ts}.log").open("w", encoding="utf-8") as h:
                    rc = subprocess.run(
                        [str(PY), "scripts/parisot_controlled.py",
                         "--data-root", str(DATA_ROOT), "--split-registry", str(SPLIT),
                         "--split-seed", str(ss), "--fold", str(fold), "--train-seed", str(ts),
                         "--device", args.device, "--scaling-scope", args.scaling_scope,
                         "--out", str(out), "--checkpoint", str(ckpt_dir / f"pa_{ss}_{fold}_{ts}.pt")],
                        env=ENV, cwd=str(REPO), stdout=h, stderr=subprocess.STDOUT).returncode
                ok += 1 if rc == 0 else 0
                fail += 1 if rc != 0 else 0
                print(f"[{time.time()-t0:7.0f}s] pa[{args.scaling_scope}] {ss}/{fold}/{ts}: rc={rc}", flush=True)
    print(f"DONE scope={args.scaling_scope} ok={ok} skip={skip} fail={fail} "
          f"elapsed_s={round(time.time()-t0,1)}", flush=True)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
