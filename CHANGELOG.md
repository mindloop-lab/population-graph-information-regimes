# Changelog

## 1.1.0 (2026-10-22) — prepared, not yet published

Increment for the manuscript revision candidate `revision-1022-v8`. No primary result, split,
frozen value or checkpoint was changed; `frozen_results/` is untouched.

### Added

- `control_analysis/` — the negative-control study: `nc_prepare_features.py`, `nc_cell.py`,
  `nc_run_matrix.py` and the strict aggregator `nc_aggregate_v2.py`, the 60 per-cell records
  (P0/P1 × splits 1024/2024 × 5 folds × 3 training seeds), the strict deterministic aggregate
  and the separate dropout diagnostic, the feature-manifest identity and an environment note.
  The strict aggregate requires exactly 60 canonical cells, 30 matched keys, both regimes, a
  query set equal to the split registry, finite predictions, consistent metadata, one feature
  hash per (split, fold) shared across regimes and seeds, and different training-node sets; it
  passes at max |Δp| = 8.56e-11 against the registered 1e-6 tolerance with an exact-zero AUC
  difference.
- `checklist/` — Reporting Checklist v2: source Markdown and generated LaTeX. Items 16, 19 and
  20 are rewritten, item 8 is conditional, and a change record plus a per-item applicability
  and evidence pointer table are included. Checklist S1 is unchanged in the manuscript
  supplement.

### Changed

- `figures/Fig1_information_regimes_stacked.{pdf,svg}` — regenerated with the evidence
  stratification (primary splits 1024/2024; split 666 shown separately as historical support).
- `figures/Fig2_primary_interaction.{py,pdf,svg,png}` and its manifest — regenerated with split
  666 placed first and separated by a dashed rule, and `(historical)`/`(primary)` labels.
- `README.md` — version table, the negative-control section, layout, and citation wording.

### Not included

- Internal control-plane records, the shared-scope sign-off sheet, manuscript sources, and any
  server-specific path.

## 1.0.1 (2026-10-22)

Documentation, display and metadata only. No result, range, split, prediction or checkpoint was
recomputed, and nothing in `frozen_results/` changed.

### Terminology

- Figure S1 (supplementary site-omission sensitivity plot): `LOSO` replaced by `site-omission` in
  the title, the x-axis label and the legend. The analysis omits one site at a time from the
  **fixed** out-of-fold predictions and does not refit; `P5/LOSO` remains the name of the
  training-time campaign on axis (b).
- `docs/REGIME_DEFINITIONS.md`: added a paragraph that separates the reported site-omission
  sensitivity range from the P5/LOSO training regime.

### Reproducibility

- The figure generators now run from a public checkout. `figures/_frozen_inputs.py` uses the
  private control plane (`paperA-control/`, double-pinned) when it is present and otherwise
  verifies the same inputs against `frozen_results/SHA256SUMS`; the governance checks that need
  the control plane stay internal and are not imitated publicly.
- `figures/Fig2_primary_interaction.py` and `figures/FS2_loso_sensitivity.py` regenerate
  byte-identical PDF/SVG/PNG from a public checkout (verified against the committed artwork).
- `figures/verify_concept_figures.py` needs the manuscript sources and now exits with an explicit
  SKIP message instead of a traceback when they are absent.
- PDF determinism is stated accurately: a delivered file can be verified by hash, but a
  **recompiled** PDF is content-identical (text, numbers, layout, references) and not
  byte-identical. Measured with `SOURCE_DATE_EPOCH` and `FORCE_SOURCE_DATE=1`: the creation date is
  fixed, the text is identical, the bytes still differ (pdfTeX trailer ID).

### Display

- Figure S1: the legend moved from lower-right to upper-left. The shipped v1.0.0 artwork already
  showed it upper-left while the script still said `lower right`; the regenerated figure now
  agrees with both the shipped layout and the script.
- Figure S1: the row labels are now `Split 1 (666, earlier audit)`, `Split 2 (1024)`,
  `Split 3 (2024)`. The split id stays visible, the internal run code `M4.5-S1` is dropped, and
  `split_labels` / `split_provenance` in the manifest record the mapping to the frozen record.
- `figures/FS2_loso_sensitivity_manifest.yaml`: `revision_note` records the wording, legend and
  label changes.
- Graphical abstract (journal submission file, not part of the software archive): the zero axis of
  the interaction panel is now drawn to the last result row instead of a fixed offset, and the
  generator fails if the axis stops short of a marker. Numbers are unchanged and still read from
  the frozen chain.

### Metadata

- `README.md`: version-to-manuscript mapping (RC4 -> `v1.0.0` / `b83ad83`; RC5.5 -> this
  revision), the distinction between the bioRxiv submission date (2026-10-02) and the first
  posting date (2026-10-08), the preprint DOI and its CC-BY 4.0 licence.
- `CITATION.cff`: added `preferred-citation` pointing at the preprint DOI; the software version
  and the Zenodo v1.0.0 DOI are unchanged until the release is cut.

### Figure 2 (stale script replaced)

- The v1.0.0 tree carried an older `Fig2_primary_interaction.py`. Rebuilding from it produced
  four text collisions (panel-A subtitle over the axis title, the two panel-B x-axis labels over
  each other, the legend over its values, the panel-B note over panel C). The manuscript had
  already moved to a later layout (offset annotations with a white box, an anchored legend, the
  directional prose moved into the caption).
- This revision syncs that maintained script (plus the public-loading changes), so the public
  figure now matches the manuscript byte for byte (`6ec9598…`, 375.9 × 446.9 pt) and its
  24 checks pass from a public checkout.

### Splits (new in this revision)

- `splits/` now ships the two frozen membership tables used by the manuscript, byte for byte:
  `mixed_site_dx_5fold_seed666.csv` (seed 666, 4,355 rows, `fa689961…`) and
  `mixed_site_dx_5fold_v2.csv` (seeds 1024, 2024 and the unused reserve 2025, 13,065 rows,
  `d7d2a28c…`), with their fold summaries and a README giving the field descriptions.
- The README records the encodings: `label` 1 = ASD, 0 = TD; `outer_fold` 0–4 (labelled 1–5 in
  the manuscript); within a (`split_seed`, `outer_fold`) the three roles are disjoint and every
  subject is `query` once.
- `mixed_site_dx_5fold_v2.csv` does **not** contain seed 666. The seed-666 table is a separate
  file from an earlier run and is identified by its own hash; its generating code was not
  recovered and is not attributed to either script.
- `docs/CONFIG_MAPPING.md` states side by side what the historical `locked_campaign_v1.yaml`
  describes (R1-C vs R2-Q, seeds 1024/2024/2025) and what the manuscript reports (P0 vs P1,
  partitions 666/1024/2024). The historical file is not re-dated or rewritten.

### Table 1 source (new in this revision)

- `manuscript/table1_protocols.tsv` is the single source of the regime taxonomy;
  `manuscript/build_table1.py` generates the LaTeX (six columns, the last carrying the evidence
  scope). Rebuilding from the TSV reproduces the manuscript table body exactly.

### Unchanged

- Split 666 still has no per-subject record; the reproducibility limitation stated in the README
  stays as it is (its interaction is carried by the frozen record and cross-checked, not
  recomputed).
- The `v1.0.0` tag, its release assets and every published hash.
