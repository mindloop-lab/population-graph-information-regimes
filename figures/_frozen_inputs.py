#!/usr/bin/env python3
"""Paper A — verified access to the frozen numeric chain, for every figure script.

One implementation, imported by all figure scripts, so no two of them can disagree about
what "the frozen inputs" are. Reading happens only through this module:

    S1_FREEZE.yaml  ->  H3 derived CSVs (deterministically generated from it)

Two verification modes, chosen by what is present:

  * internal control tree (`paperA-control/` present): every input is pinned twice, in
    PROJECT_STATE.yaml and in SOURCE_REGISTRY.yaml, and the two records must agree;
  * public checkout (no `paperA-control/`): inputs are verified against
    `frozen_results/SHA256SUMS`, the only pin shipped publicly. Governance checks that need
    the control plane stay internal and are not reproduced here.

Every recorded SHA-256 is checked against the file on disk and against the record that pins
it; a mismatch raises instead of returning data. Nothing is read from manuscript prose and
no result value is ever typed by hand.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import os
from pathlib import Path

import yaml

# matplotlib writes a creation date into PDF and SVG metadata, so the same code produced
# different bytes on every run and a committed hash could never be re-verified. Honouring
# SOURCE_DATE_EPOCH (the reproducible-builds convention) fixes the timestamp: two runs of the
# same script now give byte-identical outputs.
FIGURE_DATE = "2026-09-27"


def pin_output_dates(date: str = FIGURE_DATE) -> str:
    """Make the generated artwork reproducible byte for byte.

    Two separate sources of run-to-run variation:
      * matplotlib stamps a creation date into PDF and SVG metadata -> fixed by SOURCE_DATE_EPOCH
        (the reproducible-builds convention);
      * the SVG backend invents random hash-based element ids for clip paths and markers ->
        fixed by setting svg.hashsalt, which makes those ids deterministic.
    Both are cosmetic, but without them a committed hash could never be re-verified.
    """
    epoch = str(int(dt.datetime.fromisoformat(date + "T00:00:00+00:00").timestamp()))
    os.environ["SOURCE_DATE_EPOCH"] = epoch
    import matplotlib
    matplotlib.rcParams["svg.hashsalt"] = "paperA"
    return epoch


class FrozenInputError(RuntimeError):
    pass


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def canonical_texts(node, acc=None) -> list[str]:
    acc = [] if acc is None else acc
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "canonical_text" and isinstance(v, str):
                acc.append(v)
            else:
                canonical_texts(v, acc)
    elif isinstance(node, list):
        for v in node:
            canonical_texts(v, acc)
    return acc


def walk_values(node, key, acc=None) -> list:
    acc = [] if acc is None else acc
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key:
                acc.append(v)
            else:
                walk_values(v, key, acc)
    elif isinstance(node, list):
        for v in node:
            walk_values(v, key, acc)
    return acc


class FrozenInputs:
    """The verified frozen chain, plus the values the figures are allowed to draw."""

    def __init__(self, base: Path):
        self.base = Path(base)
        control = self.base / "paperA-control"
        if control.is_dir():
            self._load_with_control(control)
        else:
            # public checkouts ship only frozen_results/: verify against its SHA256SUMS instead of
            # the private double-pinned control plane. The governance checks stay internal.
            self._load_from_frozen_results(self.base / "frozen_results")

    def _load_with_control(self, cp: Path) -> None:
        der = cp / "derived"
        ps = yaml.safe_load((cp / "PROJECT_STATE.yaml").read_text(encoding="utf-8"))
        sr = yaml.safe_load((cp / "SOURCE_REGISTRY.yaml").read_text(encoding="utf-8"))
        h3 = yaml.safe_load((der / "H3_MANIFEST.yaml").read_text(encoding="utf-8"))

        # each input is pinned twice, in the state file and in the registry: both must agree
        recorded = {
            "S1_FREEZE.yaml": [ps["canonical_numeric_source"]["sha256"],
                              sr["layers"]["canonical_freeze"]["sha256"]],
            "H3_MANIFEST.yaml": [
                ps["h3_summary"]["sha256"],
                sr["layers"]["derived"]["artifacts"]["h3_summary_manifest"]["sha256"]],
            "COHORT_METADATA_FREEZE.yaml": [
                ps["h5c_cohort_metadata_closure"]["freeze"]["sha256"],
                sr["layers"]["manuscript_s1_canonical"]["artifacts"]
                  ["cohort_metadata_source"]["sha256"]],
        }
        for name, pins in recorded.items():
            if len(set(pins)) != 1:
                raise FrozenInputError(f"the two records disagree about {name}: {pins}")

        self.inputs: dict[str, str] = {}
        for label, path in (("S1_FREEZE.yaml", cp / "S1_FREEZE.yaml"),
                            ("H3_MANIFEST.yaml", der / "H3_MANIFEST.yaml"),
                            ("COHORT_METADATA_FREEZE.yaml",
                             der / "metadata/COHORT_METADATA_FREEZE.yaml")):
            got = sha(path)
            if got != recorded[label][0]:
                raise FrozenInputError(
                    f"{label} hash {got[:16]}… does not match the recorded {recorded[label][0][:16]}…")
            self.inputs[label] = got

        self.csv_paths: dict[str, Path] = {}
        for entry in h3["outputs"]:
            p = der / entry["path"]
            if sha(p) != entry["sha256"]:
                raise FrozenInputError(
                    f"{entry['path']} hash {sha(p)[:16]}… does not match H3_MANIFEST "
                    f"{entry['sha256'][:16]}…")
            self.csv_paths[entry["path"]] = p
            self.inputs[f"derived/{entry['path']}"] = entry["sha256"]

        self.mode = "internal"
        self.recorded = recorded
        self.freeze = yaml.safe_load((cp / "S1_FREEZE.yaml").read_text(encoding="utf-8"))
        self.canonical = set(canonical_texts(self.freeze))
        self.selected = [str(s) for s in self.freeze["scope"]["selected_splits"]["value"]]

    def _load_from_frozen_results(self, fr: Path) -> None:
        sums_path = fr / "SHA256SUMS"
        if not sums_path.is_file():
            raise FrozenInputError(
                f"neither paperA-control/ nor {sums_path} is present: cannot verify the frozen inputs")
        sums: dict[str, str] = {}
        for line in sums_path.read_text(encoding="utf-8").splitlines():
            digest, _, rel = line.strip().partition("  ")
            if digest and rel:
                sums[rel.strip()] = digest.strip()

        def pinned(rel: str) -> str:
            path = fr / rel
            if not path.is_file():
                raise FrozenInputError(f"missing public frozen input: {rel}")
            got = sha(path)
            want = sums.get(rel)
            if want is None:
                raise FrozenInputError(f"{rel} is not listed in frozen_results/SHA256SUMS")
            if got != want:
                raise FrozenInputError(
                    f"{rel} hash {got[:16]}… does not match SHA256SUMS {want[:16]}…")
            return got

        self.mode = "public"
        self.recorded = {}
        self.inputs: dict[str, str] = {}
        self.csv_paths: dict[str, Path] = {}
        for rel in ("S1_FREEZE.yaml", "COHORT_METADATA_FREEZE.yaml"):
            self.inputs[rel] = pinned(rel)
        for name in ("cross_split_primary.csv", "seed_level_interactions.csv",
                     "condition_level_auc.csv", "sensitivity_summary.csv"):
            rel = f"derived/{name}"
            if (fr / rel).is_file():
                self.inputs[rel] = pinned(rel)
                self.csv_paths[name] = fr / rel

        self.freeze = yaml.safe_load((fr / "S1_FREEZE.yaml").read_text(encoding="utf-8"))
        self.canonical = set(canonical_texts(self.freeze))
        self.selected = [str(s) for s in self.freeze["scope"]["selected_splits"]["value"]]

    def rows(self, name: str) -> list[dict]:
        with open(self.csv_paths[name], newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))

    @property
    def primary(self) -> list[dict]:
        return self.rows("cross_split_primary.csv")

    @property
    def seeds(self) -> list[dict]:
        return self.rows("seed_level_interactions.csv")

    @property
    def condition(self) -> list[dict]:
        return self.rows("condition_level_auc.csv")

    @property
    def sensitivity(self) -> list[dict]:
        if "sensitivity_summary.csv" in self.csv_paths:
            return self.rows("sensitivity_summary.csv")
        # public checkouts do not ship the derived sensitivity table; the same ranges are
        # canonical values inside S1_FREEZE.yaml, which is hash-verified above
        rows = []
        for key, node in (self.freeze.get("primary_results") or {}).items():
            rng = node.get("leave_one_site_out_range")
            if not rng:
                continue
            rows.append({"split": str(key).removeprefix("split_"),
                         "leave_one_site_out_range": rng["canonical_text"],
                         "value_role": rng.get("role", "sensitivity")})
        return rows

    def tokens(self) -> set[str]:
        """Every individual number that appears inside a frozen canonical text.

        Interval bounds are frozen as the composite "[a, b]", so their endpoints are frozen
        numbers without being canonical texts in their own right.
        """
        import re
        out: set[str] = set()
        for c in self.canonical:
            out.update(re.findall(r"[+-]?\d+\.\d{2,6}", c))
        return out
