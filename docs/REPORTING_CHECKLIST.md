# Reporting Checklist for Population-Graph Neuroimaging Evaluation

Paper A methodological output (v1, 2026-09-14). Reusable, self-contained.
Companion artifacts: `results/registry_v2.csv`, `scripts/analysis_v2.py`,
`docs/PROTOCOL_inference_v2_order_controlled.md`.

## How to use

Answer every item with **yes / no / not applicable**, and state the artifact
(config file, line of code, or hash) that supports the answer. Items marked
**[must]** are required for any claim about population-graph performance on
multi-site data; items marked **[if]** are required only when the corresponding
protocol is used.

## A. Graph construction visibility

1. **[must]** Are the outer test subjects present as nodes in the graph used
   during **training** (parameter learning)? (`R0-T` vs `R1-C` distinction)
2. **[must]** Are outer test **labels** excluded from every fitting step
   (feature selection, normalization statistics, early stopping, threshold
   selection, hyperparameter search)?
3. **[if]** If test subjects are present at training time without labels,
   is this stated explicitly as *unlabeled cohort visibility* rather than
   *label leakage*?
4. **[must]** Are graph edges (or edge-candidate sets) constructed from the
   same subject set in training and inference? If not, name both sets.
5. **[must]** Are phenotypic variables of test subjects (e.g. acquisition
   site, sex, age) used in edge construction? Report yes/no per variable.

## B. Query context at inference

6. **[must]** Is a query subject's prediction computed with other
   **unlabeled test subjects** co-present in the inference graph
   (cohort-visible) or in isolation (single-query)?
7. **[if]** If cohort-visible, report the context size convention and whether
   it is the full remaining test cohort, a fixed batch size `k`, or sampled.
8. **[must]** Is the checkpoint identical between the cohort-visible and
   query-isolated runs? Report the checkpoint hash.
9. **[must]** Is the inference graph **permutation invariant** with respect to
   the query's node index? If not, state the fixed node-order convention and
   report the effect of the alternative convention.
10. **[must]** Is the decision threshold selected without using query labels?

## C. Site familiarity

11. **[must]** Report the acquisition-site composition of the inference
    context (same-site vs cross-site vs mixed) and, when possible, the
    size-matched same-site vs cross-site contrast.
12. **[if]** If leave-one-site-out (or unseen-site) results are reported,
    state that neither features nor labels of the held-out site were used at
    any fitting step.
13. **[must]** Do not describe a model that saw held-out-site features at
    training time as "unseen-site".

## D. Normalization and preprocessing scope

14. **[must]** Report the scope (fit set) of every normalization or
    harmonization step: full cohort before splitting, fold-local, or F-only.
15. **[if]** If any normalization statistic depends on the current inference
    graph (cohort-dependent normalization), report it as an information
    channel and, where possible, provide a frozen-statistics sensitivity run.

## E. Estimation and inference

16. **[must]** Report the primary estimand explicitly. If regime sensitivity
    is claimed, report a per-subject shift measure (e.g. mean |Δp|) with its
    pre-specified smallest effect size of interest (SESOI).
17. **[must]** Report paired subject-level inference (bootstrap or permutation)
    using the **same resample** for both regimes.
18. **[must]** Cluster resampling by acquisition site when subjects are nested
    within sites (two-stage site→subject), and compare with subject-level
    bootstrap as a sensitivity analysis.
19. **[must]** Pre-specify the families for multiple-comparison correction, and
    correct within family (e.g. Holm). Report raw and corrected p-values.
20. **[if]** If a model-by-regime interaction is claimed, report the
    difference-in-differences with a **paired** resample and a corrected
    p-value; a directional point estimate alone is not an interaction claim.
21. **[must]** Separate split-seed variance from subject-level sampling
    variance; never treat seeds or context draws as independent subjects.

## F. Reproducibility

22. **[must]** Provide the cohort manifest, split registry (with hash), model
    commit, environment lock, and per-cell checkpoint hashes.
23. **[must]** Provide per-subject out-of-fold predictions in a documented
    schema (subject, site, label, split seed, fold, train seed, model, regime,
    prediction), so that all reported numbers can be regenerated mechanically.
24. **[must]** State the node-order convention, the context sampling rule, and
    the threshold rule in the methods section, not only in code.

## G. Claims

25. **[must]** State the deployment assumption that the reported regime
    corresponds to. Cohort-visible inference answers a *cohort-conditioned*
    question; single-query inference answers a *prospective* question. Do not
    present either as the only correct protocol.
26. **[must]** Do not state that a model's absolute accuracy is *explained by*
    site composition unless a site-specific intervention supports that claim.
27. **[must]** Report the number of excluded sites/subjects and the exclusion
    rule.
