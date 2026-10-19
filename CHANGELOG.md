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

### Display

- Figure S1: the legend moved from lower-right to upper-left. The shipped v1.0.0 artwork already
  showed it upper-left while the script still said `lower right`; the regenerated figure now
  agrees with both the shipped layout and the script.
- `figures/FS2_loso_sensitivity_manifest.yaml`: `revision_note` records the wording and legend
  changes.

### Metadata

- `README.md`: version-to-manuscript mapping (RC4 -> `v1.0.0` / `b83ad83`; RC5.3 -> this
  revision), the distinction between the bioRxiv submission date (2026-10-02) and the first
  posting date (2026-10-08), the preprint DOI and its CC-BY 4.0 licence.
- `CITATION.cff`: added `preferred-citation` pointing at the preprint DOI; the software version
  and the Zenodo v1.0.0 DOI are unchanged until the release is cut.

### Unchanged

- Split 666 still has no per-subject record; the reproducibility limitation stated in the README
  stays as it is (its interaction is carried by the frozen record and cross-checked, not
  recomputed).
- The `v1.0.0` tag, its release assets and every published hash.
