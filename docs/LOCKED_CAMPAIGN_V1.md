# Locked campaign v1

Lock date: 2026-09-07, before any full controlled GNN result.

The machine-readable authority is
`configs/study/locked_campaign_v1.yaml`. Smoke runs are engineering checks and
cannot change this file based on model performance.

Checkpoint selection uses validation AUC from all V subjects. Each validation
prediction is made in a separate `F+v` graph. Validation occurs at epoch 1,
every fifth epoch, and the final epoch. AUC ties select the earlier epoch.
Early stopping requires 20 validation checks without strict improvement. The
selected checkpoint is not refit on F+V.

After checkpoint selection, the decision threshold is selected on the same
query-isolated V predictions by maximum Youden J. Ties choose the threshold
closest to 0.5 and then the lower threshold.

The primary CIS smallest effect size of interest is an absolute probability
shift of 0.01. Effects below it are treated as practically small even if a
confidence interval or corrected test excludes zero. This choice applies to
all core models and cannot be altered after inspecting locked results.

Primary uncertainty uses 5,000 paired two-stage site/subject bootstrap
replicates. Subject-only paired bootstrap is sensitivity analysis. Seeds and
context draws are averaged within subject before primary inference.

