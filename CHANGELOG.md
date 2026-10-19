# Changelog

## 1.0.1 (unreleased; prepared 2026-10-19)

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

### Metadata

- `README.md`: version-to-manuscript mapping (RC4 -> `v1.0.0` / `b83ad83`; RC5.5 -> this
  revision), the distinction between the bioRxiv submission date (2026-10-02) and the first
  posting date (2026-10-08), the preprint DOI and its CC-BY 4.0 licence.
- `CITATION.cff`: added `preferred-citation` pointing at the preprint DOI; the software version
  and the Zenodo v1.0.0 DOI are unchanged until the release is cut.

### Known issue (release blocker, not fixed here)

- `figures/Fig2_primary_interaction.pdf` in this tree (`10b115d1…`, 413.9 × 447.4 pt) renders with
  text collisions under the current matplotlib: the panel-A subtitle over the x-axis title, the two
  panel-B x-axis labels over each other, the "three-seed ensemble" legend over its values, and the
  panel-B note over panel C's axis text. The script's 22 checks pass because the overlap check
  compares baselines, not text bounding boxes. The manuscript ships a different, clean build
  (`6ec9598…`, 375.9 × 446.9 pt) that the current script does not reproduce in this environment.
  Do not release until this is fixed (fix the check or pin the matplotlib version and re-render).

### Unchanged

- Split 666 still has no per-subject record; the reproducibility limitation stated in the README
  stays as it is (its interaction is carried by the frozen record and cross-checked, not
  recomputed).
- The `v1.0.0` tag, its release assets and every published hash.
