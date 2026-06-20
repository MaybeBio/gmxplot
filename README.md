# 🎨 gmxplot — GROMACS XVG File Visualization Tool

**Auto-detect, plot, compare, and summarize your GROMACS simulation data from the command line.**

`gmxplot` is a Python CLI tool that reads GROMACS XVG output files, automatically detects the type of simulation data (RMSD, RMSF, energy, SASA, PCA, gyration, etc.), and generates publication-ready matplotlib figures. It supports single-file plotting, two-file comparison, multi-file overlay, batch directory processing, and CSV statistical summaries — all with sensible defaults and no manual type specification required.

---

## Features

- **Automatic type detection** — No need to specify the plot type. `gmxplot` reads the XVG file headers and classifies the data as energy, RMSD, RMSF, gyration, SASA, PCA, or generic XY.
- **Publication-ready plots** — Clean matplotlib + seaborn-styled figures with consistent color schemes and typography.
- **Rolling average overlay** — Raw data shown with transparency; a rolling average line (auto-calculated at 5% of data range) highlights the trend.
- **Two-file comparison** — Overlay two simulations (e.g., different mutants, temperatures, force fields) on the same axes with distinct colors.
- **Multi-file comparison** — Compare 3+ files simultaneously with a cycling color palette (matplotlib tab10).
- **Batch processing** — Automatically find and plot all XVG files in a directory.
- **Statistical summaries** — Per-column CSV output with mean, std, min, q10, q50, q90, max, displayed as a Rich console table.
- **GROMACS escape code rendering** — Automatic conversion of xmgrace formatting codes (`\S2\N` → `$^{2}$`, `\sX\N` → `$_{X}$`, `\f{...}` removed).
- **Metadata-driven axis labels** — Axis titles are read from the XVG file headers, so units (ps vs ns, nm vs Å) always match the data.
- **Multiple output formats** — PNG (default), PDF, SVG, EPS, JPG, TIFF.

---

## Installation

### From source

```bash
git clone https://github.com/MaybeBio/gmxplot.git
cd gmxplot
pip install -e .
```

### With pip

```bash
pip install gmxplot
```

### Dependencies

- Python ≥ 3.10
- numpy, pandas, matplotlib, seaborn, typer, rich

---

## Quick Start

```bash
# Detect the type of an XVG file
gmxplot detect simulation.xvg

# Plot a single file (auto-detects type)
gmxplot plot simulation.xvg

# Plot with custom rolling average
gmxplot plot energy.xvg --roll-avg 50

# Save to a specific file
gmxplot plot rmsd.xvg -o rmsd.png
gmxplot plot rmsd.xvg -o rmsd.pdf

# Compare two simulations
gmxplot compare ref.xvg mutant.xvg --label1 WildType --label2 Mutant

# Compare 3+ files
gmxplot multi-compare run1/rmsd.xvg run2/rmsd.xvg run3/rmsd.xvg

# Batch process a directory
gmxplot batch ./simulation/ -o ./plots/ --stats

# Generate statistics CSV
gmxplot stats energy.xvg rmsd.xvg -o summary.csv
```

---

## CLI Reference

### `gmxplot plot`

Plot a single XVG file with automatic type detection.

```
Usage: gmxplot plot [OPTIONS] FILE

Arguments:
  FILE  Path to XVG file  [required]

Options:
  -r, --roll-avg INTEGER  Rolling average window size (auto if not set)
  -o, --output TEXT       Output file path (PNG, PDF, SVG, JPG)
  -d, --dpi INTEGER       DPI for saved image  [default: 300]
  --show                  Display plot in window
  -m, --mean              Plot mean line
  -s, --std               Plot mean +/- std lines
  --latex / --no-latex    Enable/disable LaTeX rendering (default: off)
  --help                  Show this message and exit
```

**Examples:**
```bash
gmxplot plot energy.xvg
gmxplot plot rmsd.xvg -o rmsd.png --roll-avg 20
gmxplot plot sasa.xvg -o sasa.pdf --dpi 600
gmxplot plot gyrate.xvg -m -s   # with mean and std lines
```

### `gmxplot compare`

Compare two XVG files side-by-side or overlaid on the same axes.

```
Usage: gmxplot compare [OPTIONS] FILE1 FILE2

Arguments:
  FILE1  Path to first XVG file  [required]
  FILE2  Path to second XVG file  [required]

Options:
  -l1, --label1 TEXT      Label for first dataset  [default: prot_1]
  -l2, --label2 TEXT      Label for second dataset  [default: prot_2]
  -r, --roll-avg INTEGER  Rolling average window size  [default: 50]
  -o, --output TEXT       Output file path
  -d, --dpi INTEGER       DPI for saved image  [default: 300]
  --latex / --no-latex    Enable/disable LaTeX rendering (default: off)
  --help                  Show this message and exit
```

**Type-specific behavior:**
| Plot Type | Comparison Mode |
|-----------|----------------|
| energy | Multi-panel grid: one subplot per component, both datasets overlaid per panel |
| rmsd | Single axes: both RMSD rolling averages overlaid |
| rmsf | Single axes: both RMSF traces overlaid (no rolling average) |
| gyration | Single axes: both Rg traces overlaid |
| sasa | Single axes: both SASA rolling averages overlaid |
| pca | Side-by-side: two hexbin density plots |
| xy | Single axes: generic overlay of both files |

**Examples:**
```bash
gmxplot compare prot1/rmsd.xvg prot2/rmsd.xvg -l1 WT -l2 Mutant
gmxplot compare run1/energy.xvg run2/energy.xvg -o energy_compare.png
```

### `gmxplot multi-compare`

Compare multiple XVG files (3+) of the same type.

```
Usage: gmxplot multi-compare [OPTIONS] FILES...

Arguments:
  FILES...  Paths to XVG files (at least 2)  [required]

Options:
  -r, --roll-avg INTEGER  Rolling average window size  [default: 50]
  -o, --output TEXT       Output file path
  -d, --dpi INTEGER       DPI for saved image  [default: 300]
  --latex / --no-latex    Enable/disable LaTeX rendering (default: off)
  --help                  Show this message and exit
```

Uses matplotlib's tab10 color palette (10 cycled colors) for distinguishing traces.

**Examples:**
```bash
gmxplot multi-compare chA/rmsd.xvg chB/rmsd.xvg chC/rmsd.xvg
gmxplot multi-compare prot3/rmsf_ch*.xvg -o rmsf_multi.png
```

### `gmxplot detect`

Print the detected plot type and metadata for an XVG file without generating a plot.

```
Usage: gmxplot detect [OPTIONS] FILE

Arguments:
  FILE  Path to XVG file  [required]

Options:
  --help  Show this message and exit
```

**Example output:**
```
File: tests/fixtures/prot1/energy.xvg
  Type: energy
  Title: GROMACS Energies
  X-axis: Time (ps)
  Y-axis: (kJ/mol), (K), (bar), (kg/m^3)
  Columns: ['Time', 'Potential', 'Temperature', 'Pressure', 'Density']
  Data points: 20001
  Columns count: 5
```

### `gmxplot batch`

Process all XVG files in a directory, generating plots and optionally a statistics CSV.

```
Usage: gmxplot batch [OPTIONS] [INPUT_DIR]

Arguments:
  [INPUT_DIR]  Input directory with XVG files  [default: .]

Options:
  -o, --output-dir TEXT       Output directory for plots  [default: .]
  -r, --roll-avg INTEGER      Rolling average window size (auto if not set)
  -d, --dpi INTEGER           DPI for saved images  [default: 300]
  -e, --ext TEXT              Export format (png, pdf, svg, jpg)  [default: png]
  --stats / --no-stats        Generate statistics CSV  [default: True]
  --stats-file TEXT           Statistics CSV filename  [default: xvg-stats.csv]
  -m, --mean                  Plot mean lines
  -s, --std                   Plot mean +/- std lines
  --latex / --no-latex        Enable/disable LaTeX rendering (default: off)
  --help                      Show this message and exit
```

**Examples:**
```bash
gmxplot batch ./simulation/ -o ./plots/
gmxplot batch ./data/ -o ./output/ --stats --ext pdf
gmxplot batch ./runs/ --no-stats -m    # batch without stats, with mean lines
```

### `gmxplot stats`

Generate a statistical summary CSV for one or more XVG files, displayed as a Rich table.

```
Usage: gmxplot stats [OPTIONS] FILES...

Arguments:
  FILES...  XVG files to analyze  [required]

Options:
  -o, --output TEXT  Output CSV path  [default: xvg-stats.csv]
  --help             Show this message and exit
```

Per-column statistics computed:
| Field | Description |
|-------|-------------|
| dir | Parent directory of the file |
| file | XVG filename |
| plot | Column name (e.g., Potential, RMSD, Rg) |
| mean | Arithmetic mean |
| std | Standard deviation |
| min | Minimum value |
| q10 | 10th percentile |
| q50 | 50th percentile (median) |
| q90 | 90th percentile |
| max | Maximum value |

**Example output:**
```
 XVG Statistics Summary
┏━━━━━━━━┳━━━━━━━━━━┳━━━━━━━┳━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━┳━━━━━━━━┳━━━━━━━━┓
┃ File   ┃ Plot     ┃  Mean ┃   Std ┃    Min ┃    Q10 ┃   Q50 ┃    Q90 ┃    Max ┃
┡━━━━━━━━╇━━━━━━━━━━╇━━━━━━━╇━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━╇━━━━━━━━╇━━━━━━━━┩
│ rmsd…  │ RMSD     │ 0.2905│ 0.0323│ 0.0369 │ 0.2544 │ 0.2868│ 0.3324 │ 0.3977 │
│ energ… │ Potenti… │-5616.…│1095.5…│-5659.39│-5639.27│-5616…│-5601.2…│-5570.…│
└────────┴──────────┴───────┴───────┴────────┴────────┴───────┴────────┴────────┘
```

---

## Plot Type Detection

Plot type is detected automatically from the `@ title "..."` header line in each XVG file, with fallback heuristics based on axis labels and column count when the title is unrecognized.

| Plot Type | `@ title` pattern | Column Names | Special Features |
|-----------|-------------------|--------------|------------------|
| `energy` | "GROMACS Energies", "Energy", ... | Time, Potential, Temperature, Pressure, Density | Multi-panel grid (2-column), per-component subplots |
| `gyration` | "Radius of gyration ..." | Time, Rg, RgX, RgY, RgZ | Rg rolling average only (components not shown) |
| `rmsd` | "RMSD" | Time, RMSD | Rolling average overlay |
| `rmsf` | "RMS fluctuation", "RMSF" | Residue, RMSF | Per-residue line (no rolling average) |
| `sasa` | "Solvent Accessible Surface", "Area per residue ..." | Time/Residue, Area, StdDev | Time-series (with RA) or per-residue (without RA) |
| `pca` | "2D projection of trajectory" | PC1, PC2 | Hexbin density with viridis colormap + colorbar |
| `xy` | Any unrecognized title | Auto-detected | Generic fallback, legend-based line labels |

### Detection priority

1. **Title match** (fast, authoritative) — if `@ title` contains a known keyword, use that type
2. **Axis label / column count fallback** — when the title doesn't match, heuristics examine the y-label for units, column count, and axis names
3. **Default** — 2+ columns → `xy`, otherwise `unknown`

---

## Architecture

```
gmxplot/
├── pyproject.toml          # Package config, dependencies, entry point
├── README.md
├── gmxplot/
│   ├── __init__.py         # Package version
│   ├── cli.py              # Typer CLI: all 6 commands, figure saving, LaTeX setup
│   ├── parser.py           # XVG parsing: XVGMetadata, read_xvg(), classify_plot_type()
│   ├── plotting.py         # Matplotlib figures: plot_energy, plot_rmsd, plot_rmsf, etc.
│   ├── comparison.py       # Comparison: compare_two(), compare_multi(), type-specific funcs
│   ├── stats.py            # Statistics: compute_column_stats(), generate_stats_csv()
│   ├── escape_codes.py     # Escape codes: clean_gromacs_label(), resolve_axis_titles()
│   └── config.py           # Defaults: figure sizes, DPI, colors, rolling avg params
└── tests/
    ├── test_parser.py
    ├── test_plotting.py
    ├── test_comparison.py
    ├── test_stats.py
    ├── test_escape_codes.py
    ├── test_cli.py
    └── fixtures/           # Sample XVG files for testing
        ├── prot1/          # energy, gyrate, rmsd, rmsf, sasa, 2dproj
        ├── prot2/          # Same types (for comparison testing)
        ├── prot3/          # Chain-specific files (for multi-compare)
        └── other_xvg/      # Edge cases (hbnum, resarea, cphmd)
```

### Module relationships

```
cli.py  ──→  parser.py       (read_xvg, classify_plot_type)
cli.py  ──→  plotting.py     (create_plot, calculate_roll_avg)
cli.py  ──→  comparison.py   (compare_two, compare_multi)
cli.py  ──→  stats.py        (generate_stats_csv, format_stats_table)

plotting.py  ──→  escape_codes.py   (resolve_axis_titles, clean_gromacs_label)
comparison.py ──→  escape_codes.py
comparison.py ──→  plotting.py      (calculate_roll_avg, _parse_y_units)
```

### Data flow

1. **Parsing**: XVG file → `read_xvg()` → `XVGMetadata` (title, labels, legend entries) + `DataFrame` (numeric columns with type-specific names)
2. **Classification**: `classify_plot_type()` matches title against known patterns → sets `metadata.plot_type`
3. **Plotting**: `create_plot()` dispatches to type-specific function → `Figure` with rolling average overlay
4. **Output**: `plt.savefig()` → PNG/PDF/SVG on disk, or `plt.show()` for interactive viewing

---

## Rolling Average

The rolling average window size is calculated as **5% of the data range** (max - min along the x-axis), clamped between **3 and 100**. This provides a reasonable smoothing level for most GROMACS simulation data without over-smoothing.

- **Single plot**: Auto-calculated by default; override with `--roll-avg N`
- **Comparison**: Default 50 (larger window for trend-focused comparison)
- **RMSF**: No rolling average (per-residue data is not a time series)

---

## Color Schemes

| Context | Colors | Source |
|---------|--------|--------|
| Single plot raw data | `#aec6cf` (pastel blue, 50% alpha) | config.py |
| Single plot rolling avg | `#1f77b4` (tab10 blue) | config.py |
| Two-file comparison | `#1f77b4` (blue) vs `#d62728` (red) | `COMPARE_COLORS` |
| Multi-file comparison | tab10 10-color cycle | `MULTI_COLORS` |
| PCA density | viridis colormap | matplotlib |

---

## GROMACS Escape Code Handling

GROMACS XVG files use xmgrace-style formatting codes for axis labels and legends. `gmxplot` converts these to matplotlib-compatible notation:

| Escape Code | Meaning | Conversion | Example |
|-------------|---------|------------|---------|
| `\S...\N` | Superscript | `$^{...}$` | `nm\S2\N` → `nm$^{2}$` |
| `\s...\N` | Subscript | `$_{...}$` | `Rg\sX\N` → `Rg$_{X}$` |
| `\f{...}` | Font switch | Removed | `\f{Symbol}alpha` → `alpha` |

Works with matplotlib's built-in mathtext renderer (no LaTeX installation required). If you enable `--latex`, the same notation is handled by LaTeX's math mode.

---

## References

`gmxplot` was inspired by and builds upon ideas from:

- **[GMXvg](https://github.com/TheBiomics/GMXvg)** — Batch-oriented matplotlib plotting for GROMACS XVG files with statistical CSV export.
- **[xvg_plot](https://github.com/TheBiomics/GMXvg)** — Interactive Plotly-based XVG visualization with rich type detection and multi-file comparison.

Key differences from these tools:
- **vs GMXvg**: No heavy UtilityLib dependency; cleaner modular architecture; type-specific plot functions with auto-detection; comparison and multi-file support.
- **vs xvg_plot**: Uses matplotlib instead of Plotly for publication-ready static output; includes statistical summary CSV; uses typer instead of argparse for CLI; supports mean/std overlay lines.

---

## License

MIT

## Todos

⚠️ In Chinese

- 1. 输出原始xvg数据
- 2. 可视化其他需求