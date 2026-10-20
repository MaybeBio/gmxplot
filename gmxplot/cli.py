"""Typer CLI entry point for gmxplot.

Backend selection is deliberately lazy: matplotlib's backend must be chosen
before ``pyplot`` is imported.  Commands that render figures call
:func:`_configure_backend` first, then import the plotting modules, so
``--show`` can switch to an interactive backend instead of being locked to Agg
at import time.
"""

import os
import re
import shutil
from pathlib import Path
from typing import List, Optional, Tuple

import typer
from rich.console import Console

from .config import (
    DPI_DEFAULT, LINE_WIDTH_RA, RAW_ALPHA, FLAT_THRESHOLD, BLOCK_MIN_SIZE,
)

app = typer.Typer(
    name='gmxplot',
    help='GROMACS XVG plotting and statistics with family/kind semantics, '
         'physical time axes, configurable windows and smoothing, replica '
         'aggregation, and JSON dashboards.',
    rich_markup_mode='rich',
)

console = Console()


# --------------------------------------------------------------------------
# backend / latex / save helpers
# --------------------------------------------------------------------------

def _configure_backend(interactive: bool = False) -> None:
    """Select the matplotlib backend before pyplot is imported."""
    import matplotlib
    if not interactive:
        matplotlib.use('Agg', force=True)
        return
    for name in ('TkAgg', 'Qt5Agg', 'QtAgg', 'MacOSX'):
        try:
            matplotlib.use(name, force=True)
            return
        except Exception:
            continue
    matplotlib.use('Agg', force=True)
    console.print('[yellow]No interactive backend available; falling back to Agg[/yellow]')


def _detect_latex() -> bool:
    return shutil.which('latex') is not None


def _setup_latex(use_latex: Optional[bool] = None) -> bool:
    import matplotlib.pyplot as plt
    if use_latex is None:
        use_latex = False  # default off — raw XVG labels often have ^ outside math mode
    if use_latex:
        plt.rcParams.update({
            'text.usetex': True,
            'font.family': 'sans-serif',
            'font.size': 14,
        })
    return use_latex


def _save_figure(fig, output_path: str, dpi: int = DPI_DEFAULT) -> None:
    path = Path(output_path)
    suffix = path.suffix.lower()
    if suffix not in ('.png', '.jpg', '.jpeg', '.pdf', '.svg', '.eps', '.tiff'):
        path = path.with_suffix('.png')
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(path), dpi=dpi, bbox_inches='tight')
    console.print(f'Saved to: {path}')


def _parse_pair(value: Optional[str], name: str) -> Optional[Tuple[float, float]]:
    """Parse ``"MIN MAX"`` or ``"MIN,MAX"`` into a float pair."""
    if value is None:
        return None
    parts = re.split(r'[,\s]+', value.strip())
    if len(parts) != 2:
        raise typer.BadParameter(f'{name} must be "MIN MAX" or "MIN,MAX"')
    try:
        return float(parts[0]), float(parts[1])
    except ValueError:
        raise typer.BadParameter(f'{name} values must be numeric')


def _flatten_labels(labels: Optional[List[str]], n: int) -> List[str]:
    """Normalize ``--labels`` (repeatable and/or comma-separated) to one per file."""
    out: List[str] = []
    for chunk in (labels or []):
        for part in chunk.split(','):
            part = part.strip()
            if part:
                out.append(part)
    if not out:
        return [f'rep{i + 1}' for i in range(n)]
    if len(out) < n:
        out += [f'rep{i + 1}' for i in range(len(out), n)]
    return out[:n]


# --------------------------------------------------------------------------
# shared builders (import plotting lazily to keep backend lazy)
# --------------------------------------------------------------------------

def _build_style(
    figsize=None, title=None, xlabel=None, ylabel=None, xlim=None, ylim=None,
    xlog=False, ylog=False, grid=True, legend=True, legend_loc='best',
    cmap='viridis', palette=None, line_width=LINE_WIDTH_RA, raw_alpha=RAW_ALPHA,
    hline=None, vline=None, no_raw=False, dpi=DPI_DEFAULT,
):
    from .plotting import StyleOptions
    return StyleOptions(
        figsize=_parse_pair(figsize, '--figsize'),
        title=title, xlabel=xlabel, ylabel=ylabel,
        xlim=_parse_pair(xlim, '--xlim'), ylim=_parse_pair(ylim, '--ylim'),
        xlog=xlog, ylog=ylog, grid=grid, legend=legend, legend_loc=legend_loc,
        cmap=cmap, palette=palette, line_width=line_width, raw_alpha=raw_alpha,
        hlines=hline or [], vlines=vline or [], no_raw=no_raw, dpi=dpi,
    )


def _build_dataset_options(
    kind=None, family=None, x_col=None, y_col=None, all_cols=False,
    time_unit='auto', no_time_normalize=False, start=None, end=None,
    t_eq=None, plot_full=False, roll_samples=None, roll_avg=None,
    roll_window=None, roll_fraction=None, no_roll=False, label='', path='',
):
    from .dataset import DatasetOptions
    rs = roll_samples if roll_samples is not None else roll_avg
    return DatasetOptions(
        kind=kind, family=family, x_col=x_col, y_cols=y_col, all_cols=all_cols,
        time_unit=time_unit, normalize_time=not no_time_normalize,
        start=start, end=end, t_eq=t_eq, plot_full=plot_full,
        roll_samples=rs, roll_window=roll_window, roll_fraction=roll_fraction,
        no_roll=no_roll, label=label, path=path,
    )


def _require_file(path: str) -> None:
    if not os.path.exists(path):
        console.print(f'[red]Error: File not found — {path}[/red]')
        raise typer.Exit(1)


def _print_dataset(ds) -> None:
    console.print(f'File: [cyan]{ds.path}[/cyan]')
    console.print(f'  Family: [magenta]{ds.family}[/magenta]   Kind: [green]{ds.kind}[/green]')
    console.print(f'  X column: {ds.x_col}   X is time: {ds.x_is_time}   Time unit: {ds.time_unit}')
    console.print(f'  Y columns: {", ".join(ds.y_cols)}')
    if ds.window[0] is not None or ds.window[1] is not None:
        console.print(f'  Stats window: [{ds.window[0]}, {ds.window[1]}]')
    if ds.kind == 'timeseries' and ds.roll_samples:
        console.print(f'  Rolling samples: {ds.roll_samples}')


def _write_tidy_csv(ds, out_path: str) -> None:
    """Export the resolved (windowed, time-normalized) data as a wide CSV.

    Columns are the x column (if any) followed by every selected y column.
    """
    cols = ([ds.x_col] if ds.x_col is not None else []) + list(ds.y_cols)
    df = ds.df_win[cols]
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    console.print(f'Resolved data saved to: {out_path}')


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

@app.command()
def detect(
    file: str = typer.Argument(..., help='Path to XVG file'),
):
    """Detect and print XVG family/kind/columns without plotting."""
    _require_file(file)
    from .parser import read_xvg
    _, meta = read_xvg(file)
    console.print(f'File: {file}')
    console.print(f'  Family: [magenta]{meta.family}[/magenta]')
    console.print(f'  Kind:   [green]{meta.kind}[/green]')
    console.print(f'  Title:  {meta.title}')
    console.print(f'  X-axis label: {meta.x_label}')
    console.print(f'  Y-axis label: {meta.y_label}')
    console.print(f'  X column:       {meta.x_col}')
    console.print(f'  Y columns:      {", ".join(meta.y_cols)}')
    console.print(f'  Primary Y cols: {", ".join(meta.primary_y_cols)}')
    console.print(f'  Time unit: {meta.time_unit or "-"}   X is time: {meta.x_is_time}')
    console.print(f'  Column count: {meta.n_columns}   Data points: {len(meta.df)}')


@app.command()
def plot(
    file: str = typer.Argument(..., help='Path to XVG file'),
    output: Optional[str] = typer.Option(None, '--output', '-o',
        help='Output file path (PNG, PDF, SVG, JPG)'),
    kind: Optional[str] = typer.Option(None, '--kind', help='Override rendering kind'),
    family: Optional[str] = typer.Option(None, '--type', help='Override data family'),
    x_col: Optional[str] = typer.Option(None, '--x-col', help='X column name or 1-based index'),
    y_col: Optional[List[str]] = typer.Option(None, '--y-col', help='Y column (repeatable)'),
    all_cols: bool = typer.Option(False, '--all-cols', help='Plot all data columns'),
    start: Optional[float] = typer.Option(None, '--start', help='Window start (ns for time axes)'),
    end: Optional[float] = typer.Option(None, '--end', help='Window end (ns for time axes)'),
    plot_full: bool = typer.Option(False, '--plot-full',
        help='Plot full trajectory; shade the region outside the stats window'),
    t_eq: Optional[float] = typer.Option(None, '--t-eq', help='Equilibration time (ns); vertical line'),
    time_unit: str = typer.Option('auto', '--time-unit', help='Input time unit (auto/ps/ns/us/fs)'),
    no_time_normalize: bool = typer.Option(False, '--no-time-normalize',
        help='Keep the original time unit'),
    roll_samples: Optional[int] = typer.Option(None, '--roll-samples', help='Rolling window in samples'),
    roll_avg: Optional[int] = typer.Option(None, '--roll-avg', '-r',
        help='Alias for --roll-samples'),
    roll_window: Optional[float] = typer.Option(None, '--roll-window',
        help='Rolling window in physical x units (ns for time axes)'),
    roll_fraction: Optional[float] = typer.Option(None, '--roll-fraction',
        help='Rolling window as a fraction of the x span'),
    no_roll: bool = typer.Option(False, '--no-roll', help='Disable rolling average'),
    no_raw: bool = typer.Option(False, '--no-raw', help='Hide the raw (unsmoothed) line'),
    mean: bool = typer.Option(False, '--mean', '-m', help='Plot mean line'),
    std: bool = typer.Option(False, '--std', '-s', help='Plot mean +/- std lines'),
    figsize: Optional[str] = typer.Option(None, '--figsize', help='Figure size "W H"'),
    title: Optional[str] = typer.Option(None, '--title', help='Plot title'),
    xlabel: Optional[str] = typer.Option(None, '--xlabel', help='X-axis label'),
    ylabel: Optional[str] = typer.Option(None, '--ylabel', help='Y-axis label'),
    xlim: Optional[str] = typer.Option(None, '--xlim', help='X limits "MIN MAX"'),
    ylim: Optional[str] = typer.Option(None, '--ylim', help='Y limits "MIN MAX"'),
    xlog: bool = typer.Option(False, '--xlog/--no-xlog', help='Log x axis'),
    ylog: bool = typer.Option(False, '--ylog/--no-ylog', help='Log y axis'),
    grid: bool = typer.Option(True, '--grid/--no-grid', help='Show grid'),
    legend: bool = typer.Option(True, '--legend/--no-legend', help='Show legend'),
    legend_loc: str = typer.Option('best', '--legend-loc', help='Legend location'),
    cmap: str = typer.Option('viridis', '--cmap', help='Colormap (PCA hexbin)'),
    palette: Optional[str] = typer.Option(None, '--palette',
        help='Color palette: comma-separated colors, matplotlib colormap, or seaborn palette name'),
    line_width: float = typer.Option(LINE_WIDTH_RA, '--line-width', help='Line width'),
    raw_alpha: float = typer.Option(RAW_ALPHA, '--raw-alpha', help='Raw line alpha'),
    hline: Optional[List[float]] = typer.Option(None, '--hline', help='Horizontal reference line (repeatable)'),
    vline: Optional[List[float]] = typer.Option(None, '--vline', help='Vertical reference line (repeatable)'),
    dpi: int = typer.Option(DPI_DEFAULT, '--dpi', '-d', help='DPI for saved image'),
    csv: Optional[str] = typer.Option(None, '--csv', help='Write resolved window data CSV (x + y columns)'),
    show: bool = typer.Option(False, '--show', help='Display plot in a window'),
    latex: Optional[bool] = typer.Option(None, '--latex/--no-latex',
        help='Enable/disable LaTeX rendering'),
):
    """Plot a single XVG file with automatic family/kind detection."""
    _require_file(file)
    _configure_backend(show)
    _setup_latex(latex)

    from .parser import read_xvg
    from .dataset import prepare_dataset
    from .plotting import plot_dataset
    import matplotlib.pyplot as plt

    df, meta = read_xvg(file)
    if df.empty:
        console.print(f'[red]Error: Could not parse data from {file}[/red]')
        raise typer.Exit(1)

    opts = _build_dataset_options(
        kind=kind, family=family, x_col=x_col, y_col=y_col, all_cols=all_cols,
        time_unit=time_unit, no_time_normalize=no_time_normalize,
        start=start, end=end, t_eq=t_eq, plot_full=plot_full,
        roll_samples=roll_samples, roll_avg=roll_avg, roll_window=roll_window,
        roll_fraction=roll_fraction, no_roll=no_roll,
        label=Path(file).stem, path=file,
    )
    ds = prepare_dataset(df, meta, opts)
    _print_dataset(ds)

    style = _build_style(
        figsize=figsize, title=title, xlabel=xlabel, ylabel=ylabel,
        xlim=xlim, ylim=ylim, xlog=xlog, ylog=ylog, grid=grid, legend=legend,
        legend_loc=legend_loc, cmap=cmap, palette=palette, line_width=line_width,
        raw_alpha=raw_alpha, hline=hline, vline=vline, no_raw=no_raw, dpi=dpi,
    )

    fig = plot_dataset(ds, style, show_mean=mean, show_std=std)

    out = output or f'{Path(file).stem}_plot.png'
    _save_figure(fig, out, dpi)

    if csv:
        _write_tidy_csv(ds, csv)

    if show:
        plt.show()
    plt.close(fig)


@app.command()
def compare(
    file1: str = typer.Argument(..., help='Path to first XVG file'),
    file2: str = typer.Argument(..., help='Path to second XVG file'),
    label1: str = typer.Option('prot_1', '--label1', '-l1', help='Label for first dataset'),
    label2: str = typer.Option('prot_2', '--label2', '-l2', help='Label for second dataset'),
    output: Optional[str] = typer.Option(None, '--output', '-o', help='Output file path'),
    kind: Optional[str] = typer.Option(None, '--kind', help='Override rendering kind'),
    family: Optional[str] = typer.Option(None, '--type', help='Override data family'),
    x_col: Optional[str] = typer.Option(None, '--x-col', help='X column name or 1-based index'),
    y_col: Optional[List[str]] = typer.Option(None, '--y-col', help='Y column (repeatable)'),
    all_cols: bool = typer.Option(False, '--all-cols', help='Compare all data columns'),
    start: Optional[float] = typer.Option(None, '--start', help='Window start'),
    end: Optional[float] = typer.Option(None, '--end', help='Window end'),
    t_eq: Optional[float] = typer.Option(None, '--t-eq', help='Equilibration time (ns)'),
    time_unit: str = typer.Option('auto', '--time-unit', help='Input time unit'),
    no_time_normalize: bool = typer.Option(False, '--no-time-normalize', help='Keep original time unit'),
    roll_samples: Optional[int] = typer.Option(None, '--roll-samples', help='Rolling window in samples'),
    roll_avg: Optional[int] = typer.Option(None, '--roll-avg', '-r', help='Alias for --roll-samples'),
    roll_window: Optional[float] = typer.Option(None, '--roll-window', help='Rolling window in physical units'),
    no_roll: bool = typer.Option(False, '--no-roll', help='Disable rolling average'),
    no_raw: bool = typer.Option(False, '--no-raw', help='Hide raw (unsmoothed) lines'),
    figsize: Optional[str] = typer.Option(None, '--figsize', help='Figure size "W H"'),
    title: Optional[str] = typer.Option(None, '--title', help='Plot title'),
    xlabel: Optional[str] = typer.Option(None, '--xlabel', help='X-axis label'),
    ylabel: Optional[str] = typer.Option(None, '--ylabel', help='Y-axis label'),
    xlim: Optional[str] = typer.Option(None, '--xlim', help='X limits "MIN MAX"'),
    ylim: Optional[str] = typer.Option(None, '--ylim', help='Y limits "MIN MAX"'),
    grid: bool = typer.Option(True, '--grid/--no-grid', help='Show grid'),
    legend: bool = typer.Option(True, '--legend/--no-legend', help='Show legend'),
    legend_loc: str = typer.Option('best', '--legend-loc', help='Legend location'),
    palette: Optional[str] = typer.Option(None, '--palette',
        help='Color palette: comma-separated colors, matplotlib colormap, or seaborn palette name'),
    line_width: float = typer.Option(LINE_WIDTH_RA, '--line-width', help='Line width'),
    dpi: int = typer.Option(DPI_DEFAULT, '--dpi', '-d', help='DPI for saved image'),
    latex: Optional[bool] = typer.Option(None, '--latex/--no-latex', help='Enable/disable LaTeX'),
):
    """Compare two XVG files with auto family/kind detection."""
    for f in (file1, file2):
        _require_file(f)
    _configure_backend(False)
    _setup_latex(latex)

    from .parser import read_xvg
    from .dataset import prepare_dataset
    from .comparison import compare_datasets
    import matplotlib.pyplot as plt

    datasets = []
    for f, lbl in ((file1, label1), (file2, label2)):
        df, meta = read_xvg(f)
        if df.empty:
            console.print(f'[red]Error: Could not parse data from {f}[/red]')
            raise typer.Exit(1)
        opts = _build_dataset_options(
            kind=kind, family=family, x_col=x_col, y_col=y_col, all_cols=all_cols,
            time_unit=time_unit, no_time_normalize=no_time_normalize,
            start=start, end=end, t_eq=t_eq, roll_samples=roll_samples,
            roll_avg=roll_avg, roll_window=roll_window, no_roll=no_roll,
            label=lbl, path=f,
        )
        datasets.append(prepare_dataset(df, meta, opts))

    style = _build_style(
        figsize=figsize, title=title, xlabel=xlabel, ylabel=ylabel,
        xlim=xlim, ylim=ylim, grid=grid, legend=legend, legend_loc=legend_loc,
        palette=palette, line_width=line_width, no_raw=no_raw, dpi=dpi,
    )
    fig = compare_datasets(datasets, [label1, label2], style)

    out = output or f'{Path(file1).stem}_compare.png'
    _save_figure(fig, out, dpi)
    plt.close(fig)


@app.command(name='multi-compare')
def multi_compare(
    files: List[str] = typer.Argument(..., help='Paths to XVG files (at least 2)'),
    labels: Optional[List[str]] = typer.Option(None, '--labels', help='Labels (comma-separated or repeated)'),
    output: Optional[str] = typer.Option(None, '--output', '-o', help='Output file path'),
    kind: Optional[str] = typer.Option(None, '--kind', help='Override rendering kind'),
    family: Optional[str] = typer.Option(None, '--type', help='Override data family'),
    x_col: Optional[str] = typer.Option(None, '--x-col', help='X column name or index'),
    y_col: Optional[List[str]] = typer.Option(None, '--y-col', help='Y column (repeatable)'),
    all_cols: bool = typer.Option(False, '--all-cols', help='Compare all data columns'),
    start: Optional[float] = typer.Option(None, '--start', help='Window start'),
    end: Optional[float] = typer.Option(None, '--end', help='Window end'),
    t_eq: Optional[float] = typer.Option(None, '--t-eq', help='Equilibration time (ns)'),
    time_unit: str = typer.Option('auto', '--time-unit', help='Input time unit'),
    no_time_normalize: bool = typer.Option(False, '--no-time-normalize', help='Keep original time unit'),
    roll_samples: Optional[int] = typer.Option(None, '--roll-samples', help='Rolling window in samples'),
    roll_avg: Optional[int] = typer.Option(None, '--roll-avg', '-r', help='Alias for --roll-samples'),
    roll_window: Optional[float] = typer.Option(None, '--roll-window', help='Rolling window in physical units'),
    no_roll: bool = typer.Option(False, '--no-roll', help='Disable rolling average'),
    no_raw: bool = typer.Option(False, '--no-raw', help='Hide raw lines'),
    figsize: Optional[str] = typer.Option(None, '--figsize', help='Figure size "W H"'),
    title: Optional[str] = typer.Option(None, '--title', help='Plot title'),
    xlabel: Optional[str] = typer.Option(None, '--xlabel', help='X-axis label'),
    ylabel: Optional[str] = typer.Option(None, '--ylabel', help='Y-axis label'),
    xlim: Optional[str] = typer.Option(None, '--xlim', help='X limits "MIN MAX"'),
    ylim: Optional[str] = typer.Option(None, '--ylim', help='Y limits "MIN MAX"'),
    legend: bool = typer.Option(True, '--legend/--no-legend', help='Show legend'),
    legend_loc: str = typer.Option('best', '--legend-loc', help='Legend location'),
    palette: Optional[str] = typer.Option(None, '--palette',
        help='Color palette: comma-separated colors, matplotlib colormap, or seaborn palette name'),
    line_width: float = typer.Option(LINE_WIDTH_RA, '--line-width', help='Line width'),
    dpi: int = typer.Option(DPI_DEFAULT, '--dpi', '-d', help='DPI for saved image'),
    latex: Optional[bool] = typer.Option(None, '--latex/--no-latex', help='Enable/disable LaTeX'),
):
    """Compare multiple XVG files of the same family/kind (3+ files)."""
    valid_files = [f for f in files if os.path.exists(f)]
    if len(valid_files) < 2:
        console.print('[red]Error: Need at least 2 valid files[/red]')
        raise typer.Exit(1)
    _configure_backend(False)
    _setup_latex(latex)

    from .parser import read_xvg
    from .dataset import prepare_dataset
    from .comparison import compare_datasets
    import matplotlib.pyplot as plt

    lbls = _flatten_labels(labels, len(valid_files))
    datasets = []
    for f, lbl in zip(valid_files, lbls):
        df, meta = read_xvg(f)
        if df.empty:
            continue
        opts = _build_dataset_options(
            kind=kind, family=family, x_col=x_col, y_col=y_col, all_cols=all_cols,
            time_unit=time_unit, no_time_normalize=no_time_normalize,
            start=start, end=end, t_eq=t_eq, roll_samples=roll_samples,
            roll_avg=roll_avg, roll_window=roll_window, no_roll=no_roll,
            label=lbl, path=f,
        )
        datasets.append(prepare_dataset(df, meta, opts))

    if len(datasets) < 2:
        console.print('[red]Error: Need at least 2 valid data files[/red]')
        raise typer.Exit(1)

    style = _build_style(
        figsize=figsize, title=title, xlabel=xlabel, ylabel=ylabel,
        xlim=xlim, ylim=ylim, legend=legend, legend_loc=legend_loc,
        palette=palette, line_width=line_width, no_raw=no_raw, dpi=dpi,
    )
    fig = compare_datasets(datasets, [d.label for d in datasets], style)

    out = output or 'multi_compare.png'
    _save_figure(fig, out, dpi)
    plt.close(fig)


@app.command()
def stats(
    files: List[str] = typer.Argument(..., help='XVG files to analyze'),
    output: str = typer.Option('xvg-stats.csv', '--output', '-o', '--out', help='Output CSV path'),
    kind: Optional[str] = typer.Option(None, '--kind', help='Override rendering kind'),
    family: Optional[str] = typer.Option(None, '--type', help='Override data family'),
    x_col: Optional[str] = typer.Option(None, '--x-col', help='X column name or index'),
    y_col: Optional[List[str]] = typer.Option(None, '--y-col', help='Y column (repeatable)'),
    all_cols: bool = typer.Option(False, '--all-cols', help='Analyze all data columns'),
    start: Optional[float] = typer.Option(None, '--start', help='Window start'),
    end: Optional[float] = typer.Option(None, '--end', help='Window end'),
    time_unit: str = typer.Option('auto', '--time-unit', help='Input time unit'),
    block_size: Optional[int] = typer.Option(None, '--block-size', help='Block size in samples'),
    block_time: Optional[float] = typer.Option(None, '--block-time', help='Block size in physical time units'),
    flat_threshold: float = typer.Option(FLAT_THRESHOLD, '--flat-threshold',
        help='Drift flag threshold (|drift|/SEM)'),
    ignore_series: Optional[List[str]] = typer.Option(None, '--ignore-series',
        help='Regex to skip matching series (repeatable)'),
):
    """Generate statistical summary CSV for XVG files."""
    valid_files = [f for f in files if os.path.exists(f)]
    if not valid_files:
        console.print('[red]Error: No valid files[/red]')
        raise typer.Exit(1)

    from .stats import generate_stats_csv, format_stats_table

    opts = _build_dataset_options(
        kind=kind, family=family, x_col=x_col, y_col=y_col, all_cols=all_cols,
        time_unit=time_unit, start=start, end=end,
    )
    stats_df = generate_stats_csv(
        valid_files, output, opts=opts, flat_threshold=flat_threshold,
        block_size=block_size, block_time=block_time, ignore_series=ignore_series,
    )
    if not stats_df.empty:
        console.print(f'Saved to: {output}')
        table = format_stats_table(stats_df)
        console.print(table)
    else:
        console.print('[red]Error: No data to summarize[/red]')
        raise typer.Exit(1)


@app.command()
def replicas(
    files: List[str] = typer.Argument(..., help='Replica XVG files (at least 2)'),
    labels: Optional[List[str]] = typer.Option(None, '--labels', help='Labels (comma-separated or repeated)'),
    output: Optional[str] = typer.Option(None, '--output', '-o', help='Output file path'),
    align: str = typer.Option('union', '--align', help='Alignment: union/first/intersection'),
    band: str = typer.Option('sd', '--band', help='Band type: sd/sem/none'),
    min_replicas: int = typer.Option(2, '--min-replicas', help='Min replicas to draw the mean'),
    csv: Optional[str] = typer.Option(None, '--csv', help='Long-format CSV: x, series, replica, value'),
    summary_csv: Optional[str] = typer.Option(None, '--summary-csv', help='Per-replica + cross-replica summary CSV'),
    kind: Optional[str] = typer.Option(None, '--kind', help='Override rendering kind'),
    family: Optional[str] = typer.Option(None, '--type', help='Override data family'),
    x_col: Optional[str] = typer.Option(None, '--x-col', help='X column name or index'),
    y_col: Optional[List[str]] = typer.Option(None, '--y-col', help='Y column (repeatable)'),
    all_cols: bool = typer.Option(False, '--all-cols', help='Aggregate all data columns'),
    start: Optional[float] = typer.Option(None, '--start', help='Window start'),
    end: Optional[float] = typer.Option(None, '--end', help='Window end'),
    t_eq: Optional[float] = typer.Option(None, '--t-eq', help='Equilibration time (ns)'),
    time_unit: str = typer.Option('auto', '--time-unit', help='Input time unit'),
    no_time_normalize: bool = typer.Option(False, '--no-time-normalize', help='Keep original time unit'),
    roll_samples: Optional[int] = typer.Option(None, '--roll-samples', help='Rolling window in samples'),
    roll_window: Optional[float] = typer.Option(None, '--roll-window', help='Rolling window in physical units'),
    no_roll: bool = typer.Option(False, '--no-roll', help='Disable rolling average'),
    figsize: Optional[str] = typer.Option(None, '--figsize', help='Figure size "W H"'),
    title: Optional[str] = typer.Option(None, '--title', help='Plot title'),
    xlabel: Optional[str] = typer.Option(None, '--xlabel', help='X-axis label'),
    ylabel: Optional[str] = typer.Option(None, '--ylabel', help='Y-axis label'),
    xlim: Optional[str] = typer.Option(None, '--xlim', help='X limits "MIN MAX"'),
    ylim: Optional[str] = typer.Option(None, '--ylim', help='Y limits "MIN MAX"'),
    legend: bool = typer.Option(True, '--legend/--no-legend', help='Show legend'),
    dpi: int = typer.Option(DPI_DEFAULT, '--dpi', '-d', help='DPI for saved image'),
    latex: Optional[bool] = typer.Option(None, '--latex/--no-latex', help='Enable/disable LaTeX'),
):
    """Aggregate 2+ replicas into faint lines + mean with a SD/SEM band."""
    valid_files = [f for f in files if os.path.exists(f)]
    if len(valid_files) < 2:
        console.print('[red]Error: Need at least 2 valid replica files[/red]')
        raise typer.Exit(1)
    _configure_backend(False)
    _setup_latex(latex)

    from .parser import read_xvg
    from .dataset import prepare_dataset
    from .replicas import replica_plot
    import matplotlib.pyplot as plt

    lbls = _flatten_labels(labels, len(valid_files))
    datasets = []
    for f, lbl in zip(valid_files, lbls):
        df, meta = read_xvg(f)
        if df.empty:
            console.print(f'[yellow]Skipping empty file: {f}[/yellow]')
            continue
        opts = _build_dataset_options(
            kind=kind, family=family, x_col=x_col, y_col=y_col, all_cols=all_cols,
            time_unit=time_unit, no_time_normalize=no_time_normalize,
            start=start, end=end, t_eq=t_eq, roll_samples=roll_samples,
            roll_window=roll_window, no_roll=no_roll, label=lbl, path=f,
        )
        datasets.append(prepare_dataset(df, meta, opts))

    if len(datasets) < 2:
        console.print('[red]Error: Need at least 2 valid replica datasets[/red]')
        raise typer.Exit(1)

    style = _build_style(
        figsize=figsize, title=title, xlabel=xlabel, ylabel=ylabel,
        xlim=xlim, ylim=ylim, legend=legend, dpi=dpi,
    )
    fig = replica_plot(
        datasets, labels=[d.label for d in datasets], style=style,
        align=align, band=band, min_replicas=min_replicas,
        csv_path=csv, summary_csv=summary_csv,
    )

    out = output or 'replicas.png'
    _save_figure(fig, out, dpi)
    plt.close(fig)


@app.command()
def dashboard(
    manifest: str = typer.Argument(..., help='Path to JSON manifest file'),
    output: Optional[str] = typer.Option(None, '--output', '-o', help='Output file path'),
    dpi: int = typer.Option(DPI_DEFAULT, '--dpi', '-d', help='DPI for saved image'),
    figsize: Optional[str] = typer.Option(None, '--figsize', help='Figure size "W H"'),
    cols: Optional[int] = typer.Option(None, '--cols', help='Number of columns'),
    sharex: bool = typer.Option(True, '--sharex/--no-sharex', help='Share x axis across time panels'),
    strict: bool = typer.Option(False, '--strict', help='Error on unknown manifest keys'),
    stats_csv: Optional[str] = typer.Option(None, '--stats-csv', help='Write per-panel window statistics'),
    latex: Optional[bool] = typer.Option(None, '--latex/--no-latex', help='Enable/disable LaTeX'),
):
    """Render a multi-panel dashboard from a JSON manifest."""
    _require_file(manifest)
    _configure_backend(False)
    _setup_latex(latex)

    from .dashboard import render_dashboard
    import matplotlib.pyplot as plt

    fig = render_dashboard(
        manifest, dpi=dpi, figsize=_parse_pair(figsize, '--figsize'),
        cols=cols, sharex=sharex, strict=strict, stats_csv=stats_csv,
    )
    out = output or f'{Path(manifest).stem}.pdf'
    _save_figure(fig, out, dpi)
    plt.close(fig)


@app.command()
def batch(
    input_dir: str = typer.Argument('.', help='Input directory with XVG files'),
    output_dir: str = typer.Option('.', '--output-dir', '-o', help='Output directory for plots'),
    recursive: bool = typer.Option(False, '--recursive', help='Recurse into subdirectories'),
    pattern: str = typer.Option('*.xvg', '--pattern', help='Glob pattern for XVG files'),
    skip_errors: bool = typer.Option(False, '--skip-errors', help='Continue on per-file errors'),
    roll_avg: Optional[int] = typer.Option(None, '--roll-avg', '-r', help='Rolling average window'),
    dpi: int = typer.Option(DPI_DEFAULT, '--dpi', '-d', help='DPI for saved images'),
    ext: str = typer.Option('png', '--ext', '-e', help='Export format (png, pdf, svg, jpg)'),
    stats: bool = typer.Option(True, '--stats/--no-stats', help='Generate statistics CSV'),
    stats_file: str = typer.Option('xvg-stats.csv', '--stats-file', help='Statistics CSV filename'),
    mean: bool = typer.Option(False, '--mean', '-m', help='Plot mean lines'),
    std: bool = typer.Option(False, '--std', '-s', help='Plot mean +/- std lines'),
    latex: Optional[bool] = typer.Option(None, '--latex/--no-latex', help='Enable/disable LaTeX'),
):
    """Batch process XVG files in a directory using the full plot pipeline."""
    input_path = Path(input_dir)
    if not input_path.exists():
        console.print(f'[red]Error: Directory not found — {input_dir}[/red]')
        raise typer.Exit(1)
    _configure_backend(False)
    _setup_latex(latex)

    from .parser import read_xvg
    from .dataset import prepare_dataset
    from .plotting import plot_dataset
    from .stats import generate_stats_csv, format_stats_table

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    xvg_files = sorted(input_path.rglob(pattern) if recursive else input_path.glob(pattern))
    if not xvg_files:
        console.print(f'[red]Error: No files matching {pattern} in {input_dir}[/red]')
        raise typer.Exit(1)

    console.print(f'Found {len(xvg_files)} XVG file(s)')
    all_file_paths = []
    results = []

    for xvg_file in xvg_files:
        console.print(f'\nProcessing: {xvg_file}')
        try:
            df, meta = read_xvg(str(xvg_file))
            if df.empty:
                raise ValueError('parse failed')
            opts = _build_dataset_options(
                roll_samples=roll_avg, label=xvg_file.stem, path=str(xvg_file),
            )
            ds = prepare_dataset(df, meta, opts)
            style = _build_style()
            fig = plot_dataset(ds, style, show_mean=mean, show_std=std)
            if recursive:
                rel = xvg_file.relative_to(input_path)
                out_file = output_path / rel.with_name(f'{rel.stem}_plot.{ext}')
            else:
                out_file = output_path / f'{xvg_file.stem}_plot.{ext}'
            out_file.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(str(out_file), dpi=dpi, bbox_inches='tight')
            import matplotlib.pyplot as plt
            plt.close(fig)
            console.print(f'  Saved: {out_file}')
            all_file_paths.append(str(xvg_file))
            results.append((str(xvg_file), 'success', ds.family, ds.kind))
        except Exception as e:
            console.print(f'  [red]Error: {e}[/red]')
            results.append((str(xvg_file), 'error', '-', str(e)))
            if not skip_errors:
                raise typer.Exit(1)

    if stats and all_file_paths:
        stats_path = str(output_path / stats_file)
        stats_df = generate_stats_csv(all_file_paths, stats_path)
        if not stats_df.empty:
            console.print(f'\nStatistics saved to: {stats_path}')
            table = format_stats_table(stats_df)
            console.print(table)

    console.print('\n' + '=' * 50)
    console.print('BATCH SUMMARY')
    console.print('=' * 50)
    for filename, status, info, extra in results:
        icon = '[green]OK[/green]' if status == 'success' else '[red]ERR[/red]'
        console.print(f'  {icon} {filename}: {info} ({extra})')


if __name__ == '__main__':
    app()
