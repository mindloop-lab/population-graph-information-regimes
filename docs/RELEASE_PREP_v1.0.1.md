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

The deposit file name and the GitHub `isIdenticalTo` link indicate that the record was created
by the **GitHub–Zenodo integration** (a repository archive of the `v1.0.0` release), not by a
manual upload.

**Decision: use one path only — the GitHub integration.** Publishing a `v1.0.1` tag and
Release lets Zenodo mint the next version in the same concept chain. A manual deposit would
create a second, parallel record and split the DOI history.

Consequence to plan for: with the integration, the version DOI is minted *at release time*, so
`CITATION.cff` inside the tagged tree cannot already contain it. The sequence is therefore:

1. merge the accepted tree into `main` and tag `v1.0.1` (Release notes = `CHANGELOG.md` §1.0.1);
2. let Zenodo archive that tag; record the new version DOI;
3. make a **post-release metadata commit** that writes the new version DOI and release date into
   `CITATION.cff`, `README.md` and the manuscript's availability paragraph — no new tag;
4. verify the Zenodo download, then update the manuscript files and submit bioRxiv v2 / MedIA.

This keeps the concept chain intact and avoids duplicate records. It does mean the archived
tree's `CITATION.cff` names `1.0.0` as the released version; step 3 is what corrects the
metadata layer, and the manuscript must cite the version DOI created in step 2.

## 3. Files to update at release (not before)

| file | change |
|---|---|
| `CITATION.cff` | `version: 1.0.1`, `date-released`, identifiers → new version DOI |
| `README.md` | version/date table: RC5.18 → the released tag; link the new DOI |
| `CHANGELOG.md` | move the 1.0.1 section from "unreleased" to dated |
| manuscript §6 + supplement + cover letter | availability paragraph: archived version and DOI |

Nothing above has been changed in this commit: the current tree still says `1.0.0`, which is
the truth until the release exists.

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
