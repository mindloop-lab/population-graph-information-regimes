# Regime definitions (evaluation-regime taxonomy)

Two axes are separated. They answer different questions and are reported separately.

## Axis (a): training-time cohort visibility

Does the graph used for **fitting** contain the subjects that will later be queried?

- **P0 / R0-T** — query subjects are present in the training graph as *unlabeled* nodes:
  their connectivity features and graph relations are used; their diagnostic labels are
  never used for optimisation.
- **P1 / R1-C** — query subjects are removed from the training graph; the supervised fit
  set, the validation-based checkpoint and threshold selection, and all training rules are
  unchanged.

The P0→P1 intervention concerns **cohort visibility in the graph, not label supervision**;
it is not a contrast between a leaky and a clean pipeline.

## Axis (b): inference-time query context / site familiarity

Which other unlabeled subjects (and from which sites) are co-present when one query is
scored? P2 (context dose k swept), P3/R2-Q (strict single query), P4 (size-matched
target-site context) and P5/LOSO (leave-one-site-out) live on this axis. They belong to a
separate, earlier campaign with its own estimands and are **not** merged with the primary
P0/P1 evidence.

## Primary estimand

The implementation-by-training-context interaction, per split s:

    ΔΔAUC(s) = [AUC_P0 − AUC_P1](EV-GCN, s) − [AUC_P0 − AUC_P1](Parisot-GCN, s)

computed independently within each preselected split from the three-seed probability
ensemble of each condition. Positive values indicate a more negative P0→P1 AUC change for
EV-GCN than for Parisot-GCN; they are not a claim that both implementations lose
performance. The two implementations differ in architecture *and* in their model-specific
graph operators, so the estimand is read at the level of the implementations compared, not
as a claim about architectures in general. Direction and monotonicity are not assumed.

## Inference

Per split, never pooled: paired subject bootstrap (same resample across the four
conditions) and paired site-cluster bootstrap (sites drawn, then subjects within drawn
sites); leave-one-site-out estimates as a sensitivity view. Splits are replication units;
subjects recur across splits, so no cross-split average exists.

## Implementation notes in this repository

- `audit/protocols/` — regime definitions as code (what information each regime exposes).
- `audit/training/` — checkpoint/threshold selection restricted to the validation partition.
- `audit/preprocessing/` — preprocessing fitted on the fit partition only.
- The tests in `tests/test_protocol_spec.py` and `tests/test_firewalls.py` assert these
  boundaries mechanically.
