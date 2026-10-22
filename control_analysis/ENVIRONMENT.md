# Environment where the negative control was run

| component | version / value |
|---|---|
| OS | Linux (compute node of the project cluster) |
| CPU | Intel Xeon Platinum 8269CY @ 2.50 GHz (104 threads) |
| GPU | not used for the control (CPU, deterministic kernels, single thread) |
| Python | 3.12.13 |
| numpy | 1.26.4 |
| scikit-learn | 1.7.2 |
| scipy | 1.16.3 |
| torch | 2.13.0+cu130 (CPU execution) |
| matplotlib | 3.11.1 (figures only) |

Determinism settings in `nc_cell.py`:

- `torch.use_deterministic_algorithms(True)`, `torch.set_num_threads(1)`;
- full-batch updates, dropout 0, float64 parameters and inputs;
- fixed seed per (fold, training seed); feature selection and row normalisation recomputed
  inside every run from the same cached raw features.

Timing observed: about 7–9 s per cell on the host above, 60 cells in 115 s with six workers.

The stochastic diagnostic (`--dropout 0.2`, output `cells_dropout/` and
`invariance_dropout_v2.json`) is included only to document that a random stream consumed per
batch changes the result; it is not part of the invariance verdict.
