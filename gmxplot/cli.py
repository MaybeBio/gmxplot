"""Typer CLI entry point for gmxplot."""

import os
import shutil
import sys
from pathlib import Path
from typing import List, Optional

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import typer
from rich.console import Console

from .parser import read_xvg
from .plotting import create_plot, calculate_roll_avg
from .comparison import compare_two, compare_multi
from .stats import generate_stats_csv, format_stats_table

app = typer.Typer(
    name='gmxplot',
    help='GROMACS XVG file visualization with auto type detection, comparison, and statistical summary.',
    rich_markup_mode='rich',
)

console = Console()


def _detect_latex() -> bool:
    return shutil.which('latex') is not None


def _setup_latex(use_latex: Optional[bool] = None) -> bool:
    if use_latex is None:
        use_latex = False  # default off — raw XVG labels often have ^ outside math mode
    if use_latex:
        plt.rcParams.update({
            'text.usetex': True,
            'font.family': 'sans-serif',
            'font.size': 14,
        })
    return use_latex


def _save_figure(fig, output_path: str, dpi: int = 300) -> None:
    path = Path(output_path)
    suffix = path.suffix.lower()
    if suffix not in ('.png', '.jpg', '.jpeg', '.pdf', '.svg', '.eps', '.tiff'):
        path = path.with_suffix('.png')
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(path), dpi=dpi, bbox_inches='tight')
    console.print(f'Saved to: {path}')


def _print_file_info(file_path: str, metadata) -> None:
    console.print(f'File: {file_path}')
    console.print(f'  Type: [cyan]{metadata.plot_type}[/cyan]')
    console.print(f'  Title: {metadata.title}')
    console.print(f'  X-axis: {metadata.x_label}')
    console.print(f'  Y-axis: {metadata.y_label}')
    console.print(f'  Columns: {metadata.df.columns.tolist() if hasattr(metadata, "df") else "N/A"}')
    if hasattr(metadata, 'df') and metadata.df is not None:
        console.print(f'  Data points: {len(metadata.df)}')


@app.command()
def plot(
    file: str = typer.Argument(..., help='Path to XVG file'),
    roll_avg: Optional[int] = typer.Option(None, '--roll-avg', '-r',
        help='Rolling average window size (auto if not set)'),
    output: Optional[str] = typer.Option(None, '--output', '-o',
        help='Output file path (PNG, PDF, SVG, JPG)'),
    dpi: int = typer.Option(300, '--dpi', '-d', help='DPI for saved image'),
    show: bool = typer.Option(False, '--show', help='Display plot in window'),
    mean: bool = typer.Option(False, '--mean', '-m', help='Plot mean line'),
    std: bool = typer.Option(False, '--std', '-s', help='Plot mean +/- std lines'),
    latex: Optional[bool] = typer.Option(None, '--latex/--no-latex',
        help='Enable/disable LaTeX rendering (auto-detect if not set)'),
):
    """Plot a single XVG file with automatic type detection."""
    if not os.path.exists(file):
        console.print(f'[red]Error: File not found — {file}[/red]')
        raise typer.Exit(1)

    use_latex = _setup_latex(latex)
    df, metadata = read_xvg(file)

    if df.empty:
        console.print(f'[red]Error: Could not parse data from {file}[/red]')
        raise typer.Exit(1)

    _print_file_info(file, metadata)

    if roll_avg is None:
        x_col = df.columns[0]
        roll_avg = calculate_roll_avg(df, x_col)
        console.print(f'  Auto roll-avg: {roll_avg}')

    fig = create_plot(df, metadata, roll_avg=roll_avg, show_mean=mean, show_std=std)

    if output:
        _save_figure(fig, output, dpi)
    else:
        stem = Path(file).stem
        auto_output = f'{stem}_plot.png'
        _save_figure(fig, auto_output, dpi)

    if show:
        matplotlib.use('TkAgg')
        plt.show()

    plt.close(fig)


@app.command()
def compare(
    file1: str = typer.Argument(..., help='Path to first XVG file'),
    file2: str = typer.Argument(..., help='Path to second XVG file'),
    label1: str = typer.Option('prot_1', '--label1', '-l1', help='Label for first dataset'),
    label2: str = typer.Option('prot_2', '--label2', '-l2', help='Label for second dataset'),
    roll_avg: int = typer.Option(50, '--roll-avg', '-r', help='Rolling average window size'),
    output: Optional[str] = typer.Option(None, '--output', '-o', help='Output file path'),
    dpi: int = typer.Option(300, '--dpi', '-d', help='DPI for saved image'),
    latex: Optional[bool] = typer.Option(None, '--latex/--no-latex',
        help='Enable/disable LaTeX rendering'),
):
    """Compare two XVG files with auto type detection."""
    for f in (file1, file2):
        if not os.path.exists(f):
            console.print(f'[red]Error: File not found — {f}[/red]')
            raise typer.Exit(1)

    _setup_latex(latex)
    df1, meta1 = read_xvg(file1)
    df2, meta2 = read_xvg(file2)

    if df1.empty or df2.empty:
        console.print('[red]Error: Could not parse data[/red]')
        raise typer.Exit(1)

    _print_file_info(file1, meta1)
    _print_file_info(file2, meta2)

    if meta1.plot_type != meta2.plot_type:
        console.print(f'[yellow]Warning: Different types ({meta1.plot_type} vs {meta2.plot_type})[/yellow]')

    fig = compare_two(df1, meta1, df2, meta2, label1, label2, roll_avg)

    if output:
        _save_figure(fig, output, dpi)
    else:
        stem1 = Path(file1).stem
        auto_output = f'{stem1}_compare.png'
        _save_figure(fig, auto_output, dpi)

    plt.close(fig)


@app.command(name='multi-compare')
def multi_compare(
    files: List[str] = typer.Argument(..., help='Paths to XVG files (at least 2)'),
    roll_avg: int = typer.Option(50, '--roll-avg', '-r', help='Rolling average window size'),
    output: Optional[str] = typer.Option(None, '--output', '-o', help='Output file path'),
    dpi: int = typer.Option(300, '--dpi', '-d', help='DPI for saved image'),
    latex: Optional[bool] = typer.Option(None, '--latex/--no-latex',
        help='Enable/disable LaTeX rendering'),
):
    """Compare multiple XVG files of the same type (3+ files)."""
    valid_files = [f for f in files if os.path.exists(f)]
    if len(valid_files) < 2:
        console.print('[red]Error: Need at least 2 valid files[/red]')
        raise typer.Exit(1)

    _setup_latex(latex)
    data_list = []
    for f in valid_files:
        df, meta = read_xvg(f)
        if df.empty:
            continue
        label = Path(f).stem
        data_list.append((df, meta, label))

    if len(data_list) < 2:
        console.print('[red]Error: Need at least 2 valid data files[/red]')
        raise typer.Exit(1)

    types = set(d[1].plot_type for d in data_list)
    if len(types) > 1:
        console.print(f'[yellow]Warning: Mixed types: {types}[/yellow]')

    fig = compare_multi(data_list, roll_avg)

    if output:
        _save_figure(fig, output, dpi)
    else:
        auto_output = 'multi_compare.png'
        _save_figure(fig, auto_output, dpi)

    plt.close(fig)


@app.command()
def detect(
    file: str = typer.Argument(..., help='Path to XVG file'),
):
    """Detect and print XVG file type and metadata without plotting."""
    if not os.path.exists(file):
        console.print(f'[red]Error: File not found — {file}[/red]')
        raise typer.Exit(1)

    df, metadata = read_xvg(file)
    _print_file_info(file, metadata)
    console.print(f'  Columns count: {metadata.n_columns}')


@app.command()
def batch(
    input_dir: str = typer.Argument('.', help='Input directory with XVG files'),
    output_dir: str = typer.Option('.', '--output-dir', '-o', help='Output directory for plots'),
    roll_avg: Optional[int] = typer.Option(None, '--roll-avg', '-r',
        help='Rolling average window size (auto if not set)'),
    dpi: int = typer.Option(300, '--dpi', '-d', help='DPI for saved images'),
    ext: str = typer.Option('png', '--ext', '-e', help='Export format (png, pdf, svg, jpg)'),
    stats: bool = typer.Option(True, '--stats/--no-stats', help='Generate statistics CSV'),
    stats_file: str = typer.Option('xvg-stats.csv', '--stats-file', help='Statistics CSV filename'),
    mean: bool = typer.Option(False, '--mean', '-m', help='Plot mean lines'),
    std: bool = typer.Option(False, '--std', '-s', help='Plot mean +/- std lines'),
    latex: Optional[bool] = typer.Option(None, '--latex/--no-latex',
        help='Enable/disable LaTeX rendering'),
):
    """Batch process all XVG files in a directory."""
    input_path = Path(input_dir)
    if not input_path.exists():
        console.print(f'[red]Error: Directory not found — {input_dir}[/red]')
        raise typer.Exit(1)

    _setup_latex(latex)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    xvg_files = sorted(input_path.glob('*.xvg'))
    if not xvg_files:
        console.print(f'[red]Error: No XVG files in {input_dir}[/red]')
        raise typer.Exit(1)

    console.print(f'Found {len(xvg_files)} XVG file(s)')
    all_file_paths = []
    results = []

    for xvg_file in xvg_files:
        console.print(f'\nProcessing: {xvg_file.name}')
        df, metadata = read_xvg(str(xvg_file))

        if df.empty:
            console.print(f'  [red]Error: Could not parse[/red]')
            results.append((xvg_file.name, 'error', 'parse failed'))
            continue

        if roll_avg is None:
            ra = calculate_roll_avg(df, df.columns[0])
        else:
            ra = roll_avg

        fig = create_plot(df, metadata, roll_avg=ra, show_mean=mean, show_std=std)
        out_file = output_path / f'{xvg_file.stem}_plot.{ext}'
        fig.savefig(str(out_file), dpi=dpi, bbox_inches='tight')
        console.print(f'  Saved: {out_file}')
        plt.close(fig)

        all_file_paths.append(str(xvg_file))
        results.append((xvg_file.name, 'success', metadata.plot_type))

    # Statistics
    if stats and all_file_paths:
        stats_path = str(output_path / stats_file)
        stats_df = generate_stats_csv(all_file_paths, stats_path)
        if not stats_df.empty:
            console.print(f'\nStatistics saved to: {stats_path}')
            table = format_stats_table(stats_df)
            console.print(table)

    # Summary
    console.print('\n' + '=' * 50)
    console.print('BATCH SUMMARY')
    console.print('=' * 50)
    for filename, status, info in results:
        icon = '[green]OK[/green]' if status == 'success' else '[red]ERR[/red]'
        console.print(f'  {icon} {filename}: {info}')


@app.command()
def stats(
    files: List[str] = typer.Argument(..., help='XVG files to analyze'),
    output: str = typer.Option('xvg-stats.csv', '--output', '-o', help='Output CSV path'),
):
    """Generate statistical summary CSV for XVG files."""
    valid_files = [f for f in files if os.path.exists(f)]
    if not valid_files:
        console.print('[red]Error: No valid files[/red]')
        raise typer.Exit(1)

    stats_df = generate_stats_csv(valid_files, output)
    if not stats_df.empty:
        console.print(f'Saved to: {output}')
        table = format_stats_table(stats_df)
        console.print(table)
    else:
        console.print('[red]Error: No data to summarize[/red]')
        raise typer.Exit(1)


if __name__ == '__main__':
    app()
