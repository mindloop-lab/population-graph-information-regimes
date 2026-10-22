# Release preparation — v1.0.1 (2026-10-22)

Status: **prepared, not released**. No tag, no GitHub Release, no Zenodo deposit.

## 1. What this revision contains

Relative to `v1.0.0` (`b83ad83`) the software result layer is unchanged: no model, split,
training rule or frozen value has changed. Added: the frozen split registry (`splits/`), the
Table 1 source and generator (`manuscript/`), `docs/CONFIG_MAPPING.md`, a Figure 2 script
synced with the maintained layout, and documentation.

## 2. Zenodo: how the existing record was made, and the single path to use

Checked against the public API on 2026-10-22:

| field | value |
|---|---|
| record | `10.5281/zenodo.23104123` (version DOI), concept `10.5281/zenodo.23104122` |
| version | `1.0.0` |
| publication date | 2026-10-02 |
| deposit file | `population-graph-information-regimes-1.0.0.tar.gz` |
| related identifier | `https://github.com/mindloop-lab/population-graph-information-regimes` (`isIdenticalTo`) |

The deposit file name and the GitHub `isIdenticalTo` link are **supporting evidence** that the
record was created by the GitHub–Zenodo integration; they do not by themselves prove the source,
and they say nothing about whether the connection is still enabled today.

Checks performed on 2026-10-22 from this host:

| check | result |
|---|---|
| `.zenodo.json` in the repository | **absent** (contents API returns 404), so Zenodo would read `CITATION.cff` |
| repository webhooks (to see an integration hook) | **not verifiable** — the GitHub token here lacks `admin:repo_hook`, the hooks API returns 404 |
| Zenodo integration status for the repository | **not verifiable without the Zenodo account UI** |

**Project decision (not a general rule): this project uses the GitHub–Zenodo integration and
will not create a separate manual deposit.** A manual deposit would be a second record for the
same software in this project's history, which we choose to avoid; we are not claiming that a
manual deposit always produces a duplicate.

Before tagging, confirm in the Zenodo account that the repository connection is still enabled,
and read the existing release list. If the connection is not enabled, the fallback is a manual
"new version" in the *same* concept record (never a new deposition), and the archive hash and
version DOI are recorded here before the manuscript is updated.

Consequence to plan for: with the integration, the version DOI is minted *at release time*.
`CITATION.cff` therefore now carries `version: 1.0.1` and the planned release date, keeps the
concept DOI, and **omits any version DOI** — the `v1.0.0` version DOI stays in the README's
history note. The sequence is:

1. merge the accepted tree into `main` and tag `v1.0.1` (Release notes = `CHANGELOG.md` §1.0.1);
2. let Zenodo archive that tag; record the new version DOI;
3. make a **post-release metadata commit** that writes the new version DOI and release date into
   `CITATION.cff`, `README.md` and the manuscript's availability paragraph — no new tag;
4. verify the Zenodo download, then update the manuscript files and submit bioRxiv v2 / MedIA.

This keeps the concept chain intact. The archived tree's `CITATION.cff` names `1.0.1` and the
planned release date but carries no version DOI; step 3 adds it after the archive exists (no
new tag), and the manuscript must cite the version DOI created in step 2.

## 3. Files to update at release (not before)

| file | change |
|---|---|
| `CITATION.cff` | **done**: `version: 1.0.1`, planned `date-released`, concept DOI only. Remaining: add the version DOI after the archive exists |
| `README.md` | **done**: version table and history note. Remaining: replace the planned date with the actual one after release |
| `CHANGELOG.md` | move the 1.0.1 section from "unreleased" to dated, after the tag |
| manuscript §6 + supplement + cover letter | availability paragraph: archived version and DOI (after release) |

Nothing claims that `v1.0.1` is published: the tree carries the planned date and no version DOI,
which is the truth until the archive exists.

## 4. Shared-scope record (unsigned)

`SHARED_ARTIFACTS_MATRIX.md` (paperA-control/audits) records: cohort shared (871/871 subjects
and labels match), partitions distinct (5 folds here vs 10 folds in the related manuscript's
seed-666 run; 10.2% fold agreement, i.e. chance), no byte-identical code among the 51/971
Python files, and no shared OOF/statistics/displays found.

It is **not** an author sign-off. Preprocessing features and checkpoints were not compared in
full, and derivative code reuse is not excluded, so the disclosure deliberately does not claim
"no reuse".

## 5. Acceptance for this commit

Run from a clean `git archive` export of the commit that carries this note (results recorded in
the pull request):

- split tables present, byte-identical (`fa689961…`, `d7d2a28c…`);
- Table 1 rebuilt from the TSV → body identical to the manuscript's table;
- `Fig2_primary_interaction.py` 24/24; `FS2_loso_sensitivity.py` 11/11; PDFs identical to the
  tracked files;
- no journal-only files (cover letter, disclosure, internal audit records) in the tree.
