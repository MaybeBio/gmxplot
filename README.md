# gmxplot — GROMACS XVG File Visualization & Statistics Tool

**Auto-detect, plot, compare, aggregate, and summarize GROMACS XVG output from the command line.**

`gmxplot` reads GROMACS XVG files, classifies each one by *what the data is*
(`family`) and *how it should be rendered and analyzed* (`kind`), then produces
publication-ready matplotlib figures and rigorous statistics. It normalizes
physical time axes, applies configurable windows and smoothing, aggregates
independent replicas into a mean±band figure, and assembles heterogeneous XVG
files into a single dashboard from a JSON manifest.

---

## Features

- **Two-level classification** — `family` (energy, rmsd, hbond_dist, …) is
  decoupled from `kind` (timeseries, histogram, spectrum, bar, profile, pca,
  scatter, xy). Rolling averages and drift statistics apply *only* to
  `timeseries`, never to histograms, eigenvalue spectra, or cluster-size bars.
- **Physical time axes** — `Time (ps|ns|us|fs)` is detected and normalized to ns;
  `--start/--end/--t-eq` and `--roll-window` are expressed in physical units.
- **Configurable windows** — statistics are computed on a `[start, end]` window;
  `--plot-full` shows the full trajectory with the out-of-window region shaded.
- **Rigorous statistics** — naive and block-averaged SEM, half-window drift test,
  count-weighted histogram statistics, and correct PCA (both PCs analyzed).
- **Replica aggregation** — faint per-replica lines + mean with a SD/SEM band,
  with union/first/intersection alignment and long/summary CSV export.
- **JSON dashboard** — assemble any mix of single-file and replica panels into one
  figure with shared time axes, `t_eq` lines, and panel labels.
- **GROMACS escape codes** — xmgrace `\S`, `\s`, `\f{}` converted to mathtext.
- **Multiple output formats** — PNG (default), PDF, SVG, EPS, JPG, TIFF.

---

## Installation

```bash
git clone https://github.com/MaybeBio/gmxplot.git
cd gmxplot
pip install -e .
```

Requirements: Python ≥ 3.10, numpy, pandas, matplotlib, seaborn, typer, rich.

---

## Quick Start

```bash
# Inspect how a file is classified
gmxplot detect rmsd.xvg

# Plot with automatic detection, 1 ns rolling window
gmxplot plot rmsd.xvg -o rmsd.png --roll-window 1.0

# Statistics on the equilibrated segment, 10 ps blocks
gmxplot stats rmsd.xvg --start 100 --end 200 --block-time 0.01

# Compare two runs
gmxplot compare rep1/rmsd.xvg rep2/rmsd.xvg -l1 WT -l2 Mutant

# Aggregate three replicas into a mean±SD band
gmxplot replicas rep1/rmsd.xvg rep2/rmsd.xvg rep3/rmsd.xvg \
  --labels r1,r2,r3 --band sd --summary-csv rmsd_summary.csv

# Render a dashboard from a manifest
gmxplot dashboard manifest.json -o overview.pdf --stats-csv panel_stats.csv
```

---

## Concepts: `family` vs `kind`

- **`family`** — the *semantic content* of the file:
  `energy`, `rmsd`, `rmsf`, `gyration`, `sasa`, `pca`, `hbond_num`,
  `hbond_dist`, `mindist`, `contacts`, `eigenvalue`, `cluster_size`, `dssp`,
  `generic`, `unknown`.
- **`kind`** — the *rendering / statistics semantics*:

  | kind | meaning | smoothing | drift |
  |------|---------|-----------|-------|
  | `timeseries` | ordered time series | yes | yes |
  | `profile` | per-residue / per-atom profile | no | no |
  | `histogram` | bin coordinate + counts | no | no (weighted x-stats) |
  | `spectrum` | eigenvalue / index vs intensity | no | no |
  | `bar` | discrete categories / cluster sizes | no | no |
  | `pca` | PC1–PC2 scatter / hexbin | no | no |
  | `scatter` | unordered x–y scatter | no | no |
  | `xy` | ordered non-time line | no | no |

- **Smoothing** is only offered to `timeseries`; requesting it on another kind is
  silently ignored (those kinds never smooth).

`--type` overrides `family`; `--kind` overrides `kind`. Precedence:
`--kind` > kind implied by `--type` > automatic detection. Both appear in
`gmxplot detect`.

---

## CLI Reference

### `gmxplot detect FILE`

Print the resolved family, kind, columns, time unit, and primary y columns.

```
gmxplot detect rmsd.xvg
  Family: rmsd
  Kind:   timeseries
  X column: Time     X is time: True    Time unit: ns
  Y columns: RMSD
```

### `gmxplot plot FILE`

Key options: `--kind`, `--type`, `--x-col`, `--y-col` (repeatable), `--all-cols`,
`--start`, `--end`, `--t-eq`, `--plot-full`, `--time-unit {auto,ps,ns,us,fs}`,
`--no-time-normalize`, `--roll-samples N` / `--roll-avg N` / `--roll-window T` /
`--roll-fraction F`, `--no-roll`, `--no-raw`, `--mean`, `--std`, `--csv`, and the
shared style options below.

```bash
gmxplot plot energy.xvg --all-cols -o energy.png
gmxplot plot rmsd.xvg --start 100 --t-eq 100 --roll-window 1.0 -o rmsd.png
gmxplot plot hbond_dist.xvg --no-roll -o hbdist.png   # histogram, no smoothing
```

`--csv PATH` writes the **resolved windowed data** (x column + each selected y
column, time-normalized, trimmed to `[start, end]`) as a wide CSV — the data the
plot is drawn from, not statistics. For the statistical summary (SEM, block SEM,
drift), use `gmxplot stats`.

### `gmxplot compare FILE1 FILE2`

Overlay two files. Accepts the same dataset options (`--kind`, `--type`,
`--x-col`, `--y-col`, `--all-cols`, `--start/--end`, `--time-unit`, smoothing).
`--label1/--label2` set trace labels.

### `gmxplot multi-compare FILES...`

Overlay 3+ files with a cycling tab10 palette. `--labels` accepts a
comma-separated or repeated list.

### `gmxplot stats FILES...`

Write a statistics CSV. Key options: `--start/--end`, `--time-unit`,
`--block-size N` or `--block-time T`, `--flat-threshold F`, `--ignore-series REGEX`
(repeatable), `-o/--out`.

### `gmxplot replicas FILES...`

Aggregate 2+ replicas. Options: `--labels`, `--align {union,first,intersection}`,
`--band {sd,sem,none}`, `--min-replicas`, `--csv`, `--summary-csv`, plus the
usual window/smoothing/style options.

### `gmxplot dashboard MANIFEST`

Render a JSON manifest. Options: `-o`, `--dpi`, `--figsize`, `--cols`,
`--sharex/--no-sharex`, `--strict`, `--stats-csv`, `--latex/--no-latex`.

### `gmxplot batch INPUT_DIR`

Plot every XVG in a directory. Options: `-o/--output-dir`, `--recursive`,
`--pattern` (default `*.xvg`), `--skip-errors`, `--roll-avg`, `--dpi`, `--ext`,
`--stats/--no-stats`, `--stats-file`.

With `--recursive`, the relative directory structure under `INPUT_DIR` is
preserved in the output directory (so `sub/a.xvg` → `<out>/sub/a_plot.png`),
avoiding stem collisions across subdirectories.

### Shared style options

`--figsize "W H"`, `--title`, `--xlabel`, `--ylabel`, `--xlim "MIN MAX"`,
`--ylim "MIN MAX"`, `--xlog/--no-xlog`, `--ylog/--no-ylog`, `--grid/--no-grid`,
`--legend/--no-legend`, `--legend-loc`, `--cmap`, `--palette`, `--line-width`,
`--raw-alpha`, `--hline` (repeatable), `--vline` (repeatable), `--dpi`,
`--latex/--no-latex`.

`--palette` sets the multi-series line colors (used by `compare`/`multi-compare`
and multi-column `xy`). It accepts a comma-separated color list (cycled as
needed), a matplotlib colormap name, or a seaborn palette name; default is the
tab10 `MULTI_COLORS` cycle. `--cmap` remains the colormap for PCA hexbins only.

---

## Time Axis & Windowing

- The x axis is detected as time when its label contains `Time (...)` or the
  family is a time-series family. `--time-unit auto` converts to ns via
  `ps→1e-3`, `ns→1`, `us→1e3`, `fs→1e-6`; `--no-time-normalize` keeps the
  original unit.
- `--start`/`--end` trim **both** the plot and the statistics window.
- `--plot-full` keeps the full trajectory on the plot and shades the region
  outside the window; statistics still use `[start, end]`.
- `--t-eq` draws a vertical line; without an explicit `--start`, the statistics
  window starts at `t_eq` (plot full, analyze `[t_eq, end]`).

---

## Smoothing

Only `timeseries` is smoothed. Window resolution order:
`--no-roll` > `--roll-samples` > `--roll-window` > `--roll-fraction` > auto.
The default is 1% of the x-span; `--roll-window` is converted to samples via the
median Δx. Samples are clamped to `[3, min(100, n//2)]`.

---

## Statistics Definitions

For a `timeseries` (NaN dropped pairwise):

- `n`, `mean`, `sd` (ddof=1), `sem = sd/√n`
- `block_size` (default `round(n**(1/3))`, override with `--block-size/--block-time`),
  `n_blocks = floor(n/block_size)`, `sem_block = SD(block means)/√n_blocks`
- `sem_used = max(sem, sem_block)`
- `mean_first_half` / `mean_second_half` split at the window midpoint
- `drift = mean_second − mean_first`
- `drift_over_sem = |drift| / √(sem1_used² + sem2_used²)` (plus a naive ratio)
- `flag = flat` if `drift_over_sem ≤ --flat-threshold` (default 2), else `DRIFT`
- `min/q10/q50/q90/max`

`profile`/`spectrum`/`bar`/`xy`/`scatter` output descriptive statistics only.
`histogram` adds count-weighted x statistics: `x_weighted_mean`,
`x_weighted_sd`, `x_weighted_median`, `x_mode`, `n_eff = (Σw)²/Σw²`,
`sem_weighted`. `pca` analyzes every PC column.

`--ignore-series REGEX` skips matching series (e.g. `RgX|RgY|RgZ`).

---

## Replica Aggregation

- Each replica is time-normalized and windowed independently.
- `--align union` (default) uses the union of x points; `first` uses the first
  file's grid; `intersection` uses shared points. Values are `np.interp`-ed
  within each replica's support (NaN outside, no extrapolation).
- Smoothing (if any) is applied per replica *before* aggregation; the summary CSV
  always uses the raw windowed data.
- `--band sd` (default) fills mean±SD, `sem` fills mean±SEM, `none` draws only
  the mean. `--min-replicas` (default 2) suppresses the mean where too few
  replicas overlap.

---

## Dashboard Manifest

```json
{
  "title": "Equilibration overview",
  "time_unit": "auto",
  "start": 0, "end": 200, "t_eq": 100,
  "cols": 2, "figsize": [14, 10], "sharex": true,
  "panels": [
    { "file": "rep1/rmsd.xvg", "title": "Backbone RMSD",
      "kind": "timeseries", "y_col": "RMSD", "ylim": [0, 0.6] },
    { "files": ["rep1/hbnum.xvg", "rep2/hbnum.xvg", "rep3/hbnum.xvg"],
      "labels": ["r1", "r2", "r3"], "title": "Interface H-bonds", "band": "sd" }
  ]
}
```

- Global keys (`title`, `time_unit`, `start`, `end`, `t_eq`, `cols`, `figsize`,
  `sharex`) are inherited by every panel and overridable per-panel.
- A panel has either `file` (single) or `files` + `labels` (replica).
- Panel keys: `kind`, `type`, `x_col`, `y_col`/`y_cols`, `all_cols`, `title`,
  `xlabel`, `ylabel`, `ylog`, `ylim`, `xlim`, `hline`, `vline`, `start`, `end`,
  `t_eq`, `roll_window`, `roll_samples`, `legend`, `band`, `align`, `min_replicas`.
- Multi-column panels are expanded into one sub-plot per y column so each axis
  carries a single self-consistent unit. `t_eq` lines and panel letters (A, B, C…)
  are drawn automatically; `sharex` applies only when every panel is a time axis.
- Unknown keys warn by default and error under `--strict`.

---

## Architecture

```
gmxplot/
├── cli.py          # Typer CLI: 8 commands, lazy matplotlib backend
├── parser.py       # XVG parsing, family/kind detection, column naming, time unit
├── dataset.py      # Dataset/DatasetOptions: columns, time, window, rolling
├── plotting.py     # per-kind primitives + StyleOptions
├── comparison.py   # multi-dataset overlay
├── replicas.py     # alignment + mean±SD band + CSV export
├── dashboard.py    # JSON manifest → multi-panel figure
├── stats.py        # SEM/block-SEM/drift/histogram-weighting + CSV
├── escape_codes.py # xmgrace → mathtext
└── config.py       # defaults (colors, rolling, block, thresholds)
```

Data flow: `parser.read_xvg` → `dataset.prepare_dataset` (resolve family/kind,
normalize time, apply window, resolve rolling) → `plotting.plot_dataset` /
`comparison.compare_datasets` / `replicas.replica_plot` / `dashboard.render_dashboard`
→ `stats.compute_dataset_stats`.

---

## License

GPL-3.0 — see [LICENSE](LICENSE).
