#!/usr/bin/env python3
"""Resumable EV-GCN controlled matrix driver (45 cells) — modern stack."""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PY = REPO / ".venv" / "bin" / "python"
DATA_ROOT = Path(os.environ.get("PAPER_A_DATA_ROOT", "data/curated/abide1_canonical_variants/magp_abide1_v1_legacy_matched"))
SPLIT = REPO / "splits/mixed_site_dx_5fold_v2.csv"
UPSTREAM = REPO / "third_party/EV_GCN"
OUT = REPO / "results/evgcn"
CKPT = REPO / "checkpoints/evgcn"
LOG = REPO / "logs/evgcn_matrix"
SEEDS = [1024, 2024, 2025]
FOLDS = [0, 1, 2, 3, 4]
TRAIN_SEEDS = [11, 22, 33]
DEVICE = "cuda:1"

ENV = dict(os.environ)
ENV["PYTHONPATH"] = str(REPO)
for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    ENV[v] = "8"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True); CKPT.mkdir(parents=True, exist_ok=True); LOG.mkdir(parents=True, exist_ok=True)
    t0 = time.time(); ok = skip = fail = 0
    for ss in SEEDS:
        for fold in FOLDS:
            for ts in TRAIN_SEEDS:
                out = OUT / f"ev_{ss}_{fold}_{ts}.json"
                if out.is_file():
                    try:
                        json.loads(out.read_text()); skip += 1; continue
                    except Exception:
                        pass
                with (LOG / f"ev_{ss}_{fold}_{ts}.log").open("w", encoding="utf-8") as h:
                    rc = subprocess.run(
                        [str(PY), "scripts/evgcn_controlled.py",
                         "--data-root", str(DATA_ROOT), "--split-registry", str(SPLIT), "--upstream", str(UPSTREAM),
                         "--split-seed", str(ss), "--fold", str(fold), "--train-seed", str(ts),
                         "--device", DEVICE, "--out", str(out),
                         "--checkpoint", str(CKPT / f"ev_{ss}_{fold}_{ts}.pt"),
                         "--registry", str(OUT / "unused.csv")],
                        env=ENV, cwd=str(REPO), stdout=h, stderr=subprocess.STDOUT).returncode
                if rc == 0:
                    ok += 1
                else:
                    fail += 1
                print(f"[{time.time()-t0:7.0f}s] ev {ss}/{fold}/{ts}: rc={rc}", flush=True)
    print(f"DONE ok={ok} skip={skip} fail={fail} elapsed_s={round(time.time()-t0,1)}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
