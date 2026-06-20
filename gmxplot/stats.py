"""Statistical summary generation for XVG data."""

import os
from pathlib import Path
from typing import List

import pandas as pd
from rich.console import Console
from rich.table import Table

from .parser import read_xvg


def compute_column_stats(df: pd.DataFrame, metadata) -> List[dict]:
    """Compute per-column statistics: mean, std, min, q10, q50, q90, max."""
    results = []
    fp = Path(metadata.file_path)
    for col in df.columns[1:]:
        series = df[col].dropna()
        results.append({
            'dir': str(fp.parent),
            'file': fp.name,
            'plot': col,
            'mean': series.mean(),
            'std': series.std(),
            'min': series.min(),
            'q10': series.quantile(0.1),
            'q50': series.quantile(0.5),
            'q90': series.quantile(0.9),
            'max': series.max(),
        })
    return results


def generate_stats_csv(
    file_paths: List[str],
    output_path: str,
) -> pd.DataFrame:
    """Generate statistical summary CSV for multiple XVG files."""
    all_stats = []
    for fp in file_paths:
        if not os.path.exists(fp):
            continue
        df, metadata = read_xvg(fp)
        if df.empty:
            continue
        all_stats.extend(compute_column_stats(df, metadata))

    stats_df = pd.DataFrame(all_stats)
    if not stats_df.empty:
        stats_df.to_csv(output_path, index=False, float_format='%.6f')
    return stats_df


def format_stats_table(stats_df: pd.DataFrame, console: Console = None) -> Table:
    """Format statistics DataFrame as a Rich console table."""
    if console is None:
        console = Console()

    table = Table(title='XVG Statistics Summary')
    table.add_column('File', style='cyan')
    table.add_column('Plot', style='green')
    table.add_column('Mean', justify='right')
    table.add_column('Std', justify='right')
    table.add_column('Min', justify='right')
    table.add_column('Q10', justify='right')
    table.add_column('Q50', justify='right')
    table.add_column('Q90', justify='right')
    table.add_column('Max', justify='right')

    for _, row in stats_df.iterrows():
        table.add_row(
            str(row['file']),
            str(row['plot']),
            f'{row["mean"]:.4f}',
            f'{row["std"]:.4f}',
            f'{row["min"]:.4f}',
            f'{row["q10"]:.4f}',
            f'{row["q50"]:.4f}',
            f'{row["q90"]:.4f}',
            f'{row["max"]:.4f}',
        )

    return table