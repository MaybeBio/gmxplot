"""Matplotlib plotting functions for all XVG plot types."""

import re
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from .escape_codes import clean_gromacs_label, resolve_axis_titles
from .config import (
    FIGURE_SIZE_SINGLE, FIGURE_SIZE_MULTI_ROW_HEIGHT, DPI_DEFAULT,
    LINE_WIDTH_RAW, LINE_WIDTH_RA, RAW_ALPHA, RA_COLOR, RAW_COLOR,
    ROLL_AVG_MIN, ROLL_AVG_MAX, ROLL_AVG_FRACTION,
)

# Apply seaborn style defaults
sns.set_style('whitegrid')
sns.set_context('paper', font_scale=1.2)


def calculate_roll_avg(df: pd.DataFrame, x_col: str = 'Time') -> int:
    """Calculate rolling average window: 5% of data range, min 3, max 100."""
    if x_col not in df.columns or len(df) < 10:
        return 10
    x_range = df[x_col].max() - df[x_col].min()
    window = max(ROLL_AVG_MIN, min(ROLL_AVG_MAX, int(x_range * ROLL_AVG_FRACTION)))
    return max(3, window)


def _add_ra_trace(ax, x, y, roll_avg, raw_color=RAW_COLOR, ra_color=RA_COLOR):
    """Add raw data line + rolling average overlay to axes."""
    y_ra = y.rolling(window=roll_avg, min_periods=1, center=True).mean()
    ax.plot(x, y, color=raw_color, alpha=RAW_ALPHA, linewidth=LINE_WIDTH_RAW, label='Raw')
    ax.plot(x, y_ra, color=ra_color, linewidth=LINE_WIDTH_RA, label=f'RA (n={roll_avg})')


def _add_mean_std_lines(ax, df, y_col, show_mean=False, show_std=False):
    """Optionally draw mean and mean +/- std horizontal lines."""
    if y_col not in df.columns:
        return
    y_data = df[y_col]
    mean = y_data.mean()
    std = y_data.std()
    color = RA_COLOR
    if show_mean:
        ax.axhline(y=mean, color=color, linestyle='--', linewidth=1, alpha=0.8)
    if show_std:
        ax.axhline(y=mean + std, color=color, linestyle=':', linewidth=0.5, alpha=0.6)
        ax.axhline(y=mean - std, color=color, linestyle=':', linewidth=0.5, alpha=0.6)


def plot_energy(df: pd.DataFrame, metadata, roll_avg=None,
                show_mean=False, show_std=False) -> plt.Figure:
    """Plot energy components with rolling average in dynamic subplot grid."""
    if roll_avg is None:
        roll_avg = calculate_roll_avg(df, 'Time')

    y_cols = [c for c in df.columns if c != 'Time']
    n_y = len(y_cols)
    if n_y == 0:
        return plot_xy(df, metadata, roll_avg, show_mean, show_std)

    # Grid layout
    n_cols = min(2, n_y) if n_y > 1 else 1
    n_rows = max(1, (n_y + n_cols - 1) // n_cols)

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(12, n_rows * FIGURE_SIZE_MULTI_ROW_HEIGHT),
                              sharex=True, squeeze=False)
    axes_flat = axes.flatten()

    # Parse per-column units from y_label
    units = _parse_y_units(metadata.y_label)
    y_titles = _build_y_titles(y_cols, units)

    for idx, y_col in enumerate(y_cols):
        ax = axes_flat[idx]
        _add_ra_trace(ax, df['Time'], df[y_col], roll_avg)
        _add_mean_std_lines(ax, df, y_col, show_mean, show_std)
        ax.set_ylabel(y_titles.get(y_col, y_col))
        ax.set_title(y_col)

    # Hide unused axes
    for idx in range(n_y, len(axes_flat)):
        axes_flat[idx].set_visible(False)

    x_title, _ = resolve_axis_titles(metadata, 'Time (ps)', '')
    for ax_row in axes[-1]:
        if ax_row.get_visible():
            ax_row.set_xlabel(x_title)

    fig.suptitle('Energy Components', fontsize=14)
    fig.tight_layout()
    return fig


def plot_gyration(df: pd.DataFrame, metadata, roll_avg=None,
                  show_mean=False, show_std=False) -> plt.Figure:
    """Plot radius of gyration (Rg only)."""
    if roll_avg is None:
        roll_avg = calculate_roll_avg(df, 'Time')

    fig, ax = plt.subplots(figsize=FIGURE_SIZE_SINGLE)

    if 'Rg' in df.columns:
        _add_ra_trace(ax, df['Time'], df['Rg'], roll_avg)
        _add_mean_std_lines(ax, df, 'Rg', show_mean, show_std)

    x_title, y_title = resolve_axis_titles(metadata, 'Time (ps)', 'Rg (nm)')
    ax.set_xlabel(x_title)
    ax.set_ylabel(y_title)
    ax.set_title(f'Radius of Gyration — {metadata.title}')
    ax.legend()
    fig.tight_layout()
    return fig


def plot_rmsd(df: pd.DataFrame, metadata, roll_avg=None,
              show_mean=False, show_std=False) -> plt.Figure:
    """Plot RMSD with rolling average."""
    if roll_avg is None:
        roll_avg = calculate_roll_avg(df, 'Time')

    fig, ax = plt.subplots(figsize=FIGURE_SIZE_SINGLE)

    if 'RMSD' in df.columns:
        _add_ra_trace(ax, df['Time'], df['RMSD'], roll_avg)
        _add_mean_std_lines(ax, df, 'RMSD', show_mean, show_std)

    x_title, y_title = resolve_axis_titles(metadata, 'Time (ns)', 'RMSD (nm)')
    ax.set_xlabel(x_title)
    ax.set_ylabel(y_title)
    ax.set_title(f'RMSD — {metadata.title}')
    ax.legend()
    fig.tight_layout()
    return fig


def plot_rmsf(df: pd.DataFrame, metadata, roll_avg=None,
              show_mean=False, show_std=False) -> plt.Figure:
    """Plot RMSF per residue (no rolling average)."""
    fig, ax = plt.subplots(figsize=FIGURE_SIZE_SINGLE)

    if 'RMSF' in df.columns:
        ax.plot(df['Residue'], df['RMSF'], color=RA_COLOR, linewidth=LINE_WIDTH_RA)
        _add_mean_std_lines(ax, df, 'RMSF', show_mean, show_std)

    x_title, y_title = resolve_axis_titles(metadata, 'Residue', 'RMSF (nm)')
    ax.set_xlabel(x_title)
    ax.set_ylabel(y_title)
    ax.set_title(f'RMSF — {metadata.title}')
    fig.tight_layout()
    return fig


def plot_sasa(df: pd.DataFrame, metadata, roll_avg=None,
              show_mean=False, show_std=False) -> plt.Figure:
    """Plot SASA — time-series with RA, or per-residue without RA."""
    fig, ax = plt.subplots(figsize=FIGURE_SIZE_SINGLE)

    if 'Time' in df.columns:
        x_col = 'Time'
        fallback_x = 'Time (ns)'
    elif 'Residue' in df.columns:
        x_col = 'Residue'
        fallback_x = 'Residue'
    else:
        x_col = df.columns[0]
        fallback_x = x_col

    x_title, y_title = resolve_axis_titles(metadata, fallback_x, 'Area (nm$^{2}$)')

    if 'Area' in df.columns:
        if x_col == 'Residue':
            ax.plot(df[x_col], df['Area'], color=RA_COLOR, linewidth=LINE_WIDTH_RA)
        else:
            if roll_avg is None:
                roll_avg = calculate_roll_avg(df, x_col)
            _add_ra_trace(ax, df[x_col], df['Area'], roll_avg)
        _add_mean_std_lines(ax, df, 'Area', show_mean, show_std)

    ax.set_xlabel(x_title)
    ax.set_ylabel(y_title)
    ax.set_title(f'SASA — {metadata.title}')
    if x_col == 'Time':
        ax.legend()
    fig.tight_layout()
    return fig


def plot_pca(df: pd.DataFrame, metadata, roll_avg=None,
             show_mean=False, show_std=False) -> plt.Figure:
    """Plot PCA projection as 2D hexbin density with viridis colormap."""
    fig, ax = plt.subplots(figsize=FIGURE_SIZE_SINGLE)

    if 'PC1' in df.columns and 'PC2' in df.columns:
        hb = ax.hexbin(df['PC1'], df['PC2'], cmap='viridis', gridsize=30, mincnt=1)
        fig.colorbar(hb, ax=ax, label='Density')

    x_title, y_title = resolve_axis_titles(metadata, 'PC1', 'PC2')
    ax.set_xlabel(x_title)
    ax.set_ylabel(y_title)
    ax.set_title(f'PCA Projection — {metadata.title}')
    fig.tight_layout()
    return fig


def plot_xy(df: pd.DataFrame, metadata, roll_avg=None,
            show_mean=False, show_std=False) -> plt.Figure:
    """Generic XY plot for unrecognized types."""
    x_col = df.columns[0]
    y_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]

    if roll_avg is None:
        roll_avg = calculate_roll_avg(df, x_col)

    fig, ax = plt.subplots(figsize=FIGURE_SIZE_SINGLE)

    # Multiple Y columns: each as separate line
    y_cols = list(df.columns[1:])
    if len(y_cols) <= 1:
        _add_ra_trace(ax, df[x_col], df[y_col], roll_avg)
        _add_mean_std_lines(ax, df, y_col, show_mean, show_std)
    else:
        for yc in y_cols:
            y_ra = df[yc].rolling(window=roll_avg, min_periods=1, center=True).mean()
            ax.plot(df[x_col], y_ra, linewidth=LINE_WIDTH_RA, label=yc)
            _add_mean_std_lines(ax, df, yc, show_mean, show_std)

    x_title, y_title = resolve_axis_titles(metadata, x_col, y_col)
    ax.set_xlabel(x_title)
    ax.set_ylabel(y_title)
    ax.set_title(f'Plot — {metadata.title}')
    ax.legend()
    fig.tight_layout()
    return fig


def create_plot(df: pd.DataFrame, metadata, roll_avg=None,
                show_mean=False, show_std=False) -> plt.Figure:
    """Dispatch to type-specific plot function."""
    plot_type = metadata.plot_type
    func_map = {
        'energy': plot_energy,
        'gyration': plot_gyration,
        'rmsd': plot_rmsd,
        'rmsf': plot_rmsf,
        'sasa': plot_sasa,
        'pca': plot_pca,
        'xy': plot_xy,
        'unknown': plot_xy,
    }
    func = func_map.get(plot_type, plot_xy)
    return func(df, metadata, roll_avg, show_mean, show_std)


def _parse_y_units(y_label: str) -> list:
    """Parse per-column units from y_label like '(kJ/mol), (K), (bar), (kg/m^3)'."""
    return re.findall(r'\(([^)]+)\)', y_label)

def _build_y_titles(y_cols: list, units: list) -> dict:
    """Build column-name -> 'Name (unit)' map from y_label units."""
    result = {}
    for idx, col in enumerate(y_cols):
        if idx < len(units):
            result[col] = f'{col} ({clean_gromacs_label(units[idx])})'
        else:
            result[col] = col
    return result