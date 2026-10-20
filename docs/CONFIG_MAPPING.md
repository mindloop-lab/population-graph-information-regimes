# Configuration mapping (historical vs. current)

This archive contains two campaign configurations. They are not the same object and must not be
merged.

| | Historical campaign | Current controlled campaign |
|---|---|---|
| File | `configs/study/locked_campaign_v1.yaml` (kept as-is) | reported in the manuscript (§2) |
| Primary contrast | `R1-C` vs `R2-Q` (inference-context regimes) | `P0` vs `P1` (training-time cohort visibility) |
| Split seeds in the file | `[1024, 2024, 2025]` | reported partitions: 666, 1024, 2024 |
| Training seeds | `[11, 22, 33]` | `[11, 22, 33]` |
| Status of 2025 | listed as a reserve; **not run** | not used |
| Status of 666 | not in this file | from an earlier, independently audited run |

Notes.

- The historical file documents what was planned for that campaign. It is **not** evidence that the
  three partitions reported in the manuscript were selected before any result existed; that claim
  rests on the locked records cited in §2 and on the decision log, not on this YAML.
- Nothing here re-dates the historical file. The mapping was written on 2026-10-20 to make the two
  configurations legible side by side; it does not add pre-registration evidence.
- The seed-666 membership table is archived under `splits/` and is identified by its own hash; its
  generating code has not been recovered.
