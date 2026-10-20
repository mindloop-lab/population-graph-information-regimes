# Table 1 — regime taxonomy source

`table1_protocols.tsv` is the single source of the taxonomy table in the manuscript.
`build_table1.py` turns it into LaTeX:

    python manuscript/build_table1.py            # writes manuscript/table1_protocols.tex
    python manuscript/build_table1.py --out /tmp/table1_protocols.tex

The generated `.tex` is not tracked here; the archive ships the source and the generator.
The table carries six columns, the last one being the evidence scope (`evaluated` for the two
regimes this study runs, `definition only` for the rest). Edit the TSV, never the `.tex`.

To check the generator, delete any previously generated `.tex` and rebuild: six columns must
appear, and no numeric file changes.
