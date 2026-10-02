# Data preparation

**Nothing from ABIDE is redistributed by this repository** — no raw images, no derived
connectivity matrices, no phenotypic table, no timeseries. You must obtain the data from
the authorized source and respect its terms of use.

## 1. Obtain ABIDE-I derivatives

The controlled pathway consumes the preprocessed ABIDE-I release (CPAC pipeline,
`filt_noglobal` strategy) via the Preprocessed Connectomes Project:

- derivative timeseries: `rois_cc200` (the paper's connectivity features; the audit also
  cross-checks `rois_aal` and `rois_ho`);
- phenotypic file: `Phenotypic_V1_0b_preprocessed1.csv` (subject identifiers, site, sex,
  age, diagnosis).

Download: https://preprocessed-connectomes-project.org/abide/ — use the current official
instructions; record what you downloaded.

> Redistribution note: the upstream `preprocessed-connectomes-project/abide` GitHub
> repository carries no license file; this project therefore vendors none of its content.
> Everything data-specific here is a *reference* to the official source.

## 2. Cohort definition

The frozen cohort is the widely used complete-case subset: 871 subjects (403 autistic,
468 typically developing) across 20 acquisition sites with complete phenotype fields,
following Di Martino et al. (2014) and Abraham et al. (2017). Exact subject lists are not
hard-coded: the split generator derives them from your local phenotype file
(`scripts/generate_mixed_site_splits.py`), so the same canonical subset is reconstructed
from the official source at your site.

## 3. Connectivity features

Per subject: one 200×200 CC200 Pearson correlation matrix; strict upper triangle
(19,900 features), **not** Fisher-z transformed in the controlled pathway.

## 4. Splits

The campaign uses three preselected outer split seeds (666, 1024, 2024) of 5 mixed-site
folds each, with disjoint fit/validation/query partitions; split seed 2025 is reserved and
was not executed. Fold assignment is generated deterministically from your local subject
identities; the per-subject fold/seed registry released in `frozen_results/registry_v2.csv`
lets you verify your generated splits against the ones the paper used.

## 5. Upstream model code

Fetch at the pinned commits in `THIRD_PARTY_NOTICES.md` (do not take HEAD):

```bash
git clone https://github.com/parisots/population-gcn.git && git -C population-gcn checkout <pinned-sha>
git clone https://github.com/SamitHuang/EV_GCN.git   && git -C EV_GCN checkout <pinned-sha>
```

The controlled adapters in `audit/models/` wrap these implementations; the parity scripts
(`scripts/verify_ev_parity.py`, `scripts/verify_parisot_parity.py`) verify the wrapper
against the upstream on fixed inputs before any controlled run counts.
