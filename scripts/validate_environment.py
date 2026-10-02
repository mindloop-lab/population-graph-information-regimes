#!/usr/bin/env python3
"""Minimal environment check for the reproduction entries.

Confirms the interpreter version and the stdlib+yaml stack the entries rely on. The full
environment (torch &c.) is only needed for retraining, which no reproduction entry requires.
"""
from __future__ import annotations

import sys

def main() -> int:
    print(f"python {sys.version.split()[0]}")
    try:
        import yaml  # noqa: F401
        print("pyyaml: OK")
    except ImportError:
        print("pyyaml: MISSING (required)")
        return 1
    ok = sys.version_info >= (3, 9)
    print("RESULT:", "PASS" if ok else "FAIL (python >= 3.9 required)")
    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
