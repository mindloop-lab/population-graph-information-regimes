#!/usr/bin/env python3
"""Verify pinned third-party repositories without modifying them."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from pathlib import Path


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def normalize_origin(value: str) -> str:
    return value.removesuffix(".git").rstrip("/")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--third-party", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    with args.lock.open(newline="", encoding="utf-8") as handle:
        locked = list(csv.DictReader(handle, delimiter="\t"))
    checks = []
    failures = []
    for row in locked:
        repo = args.third_party / row["name"]
        current_head = git(repo, "rev-parse", "HEAD") if repo.is_dir() else "MISSING"
        current_origin = git(repo, "remote", "get-url", "origin") if repo.is_dir() else "MISSING"
        dirty = git(repo, "status", "--porcelain=v1") if repo.is_dir() else "MISSING"
        head_ok = current_head == row["commit"]
        origin_ok = normalize_origin(current_origin) == normalize_origin(row["origin"])
        clean_ok = dirty == ""
        result = {
            "name": row["name"],
            "expected_head": row["commit"],
            "current_head": current_head,
            "head_ok": head_ok,
            "origin_ok": origin_ok,
            "clean_ok": clean_ok,
            "license": row["license"],
        }
        checks.append(result)
        if not (head_ok and origin_ok and clean_ok):
            failures.append(row["name"])
    report = {"status": "PASS" if not failures else "FAIL", "failures": failures, "repositories": checks}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "repositories": len(checks), "failures": failures}))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
