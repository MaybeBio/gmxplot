"""Two-file and multi-file comparison plotting with matplotlib."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .escape_codes import resolve_axis_titles
from .plotting import calculate_roll_avg, _parse_y_units, _build_y_titles, clean_gromacs_label
from .config import (
    FIGURE_SIZE_SINGLE, FIGURE_SIZE_MULTI_ROW_HEIGHT,
    COMPARE_COLORS, MULTI_COLORS,
    LINE_WIDTH_RA, ROLL_AVG_DEFAULT_COMPARE,
)


def compare_two(
    df1: pd.DataFrame, meta1,
    df2: pd.DataFrame, meta2,
    label1: str = 'prot_1', label2: str = 'prot_2',
    roll_avg: int = ROLL_AVG_DEFAULT_COMPARE,
) -> plt.Figure:
    """Create comparison plot for two XVG files, dispatching by type."""
    plot_type = meta1.plot_type

    if plot_type == 'energy':
        return _compare_energy(df1, meta1, df2, meta2, label1, label2, roll_avg)
    elif plot_type == 'pca':
        return _compare_pca(df1, meta1, df2, meta2, label1, label2)

    fig, ax = plt.subplots(figsize=FIGURE_SIZE_SINGLE)
    color1, color2 = COMPARE_COLORS

    if plot_type == 'gyration':
        for col in ['Rg', 'RgX', 'RgY', 'RgZ']:
            if col in df1.columns and col in df2.columns:
                ra1 = df1[col].rolling(window=roll_avg, min_periods=1, center=True).mean()
                ra2 = df2[col].rolling(window=roll_avg, min_periods=1, center=True).mean()
                ax.plot(df1['Time'], ra1, color=color1, linewidth=LINE_WIDTH_RA,
                        label=f'{label1} {col}')
                ax.plot(df2['Time'], ra2, color=color2, linewidth=LINE_WIDTH_RA,
                        label=f'{label2} {col}')

    elif plot_type == 'rmsd':
        if 'RMSD' in df1.columns and 'RMSD' in df2.columns:
            ra1 = df1['RMSD'].rolling(window=roll_avg, min_periods=1, center=True).mean()
            ra2 = df2['RMSD'].rolling(window=roll_avg, min_periods=1, center=True).mean()
            ax.plot(df1['Time'], ra1, color=color1, linewidth=LINE_WIDTH_RA,
                    label=f'{label1} RMSD')
            ax.plot(df2['Time'], ra2, color=color2, linewidth=LINE_WIDTH_RA,
                    label=f'{label2} RMSD')

    elif plot_type == 'rmsf':
        if 'RMSF' in df1.columns and 'RMSF' in df2.columns:
            ax.plot(df1['Residue'], df1['RMSF'], color=color1, linewidth=LINE_WIDTH_RA,
                    label=f'{label1} RMSF')
            ax.plot(df2['Residue'], df2['RMSF'], color=color2, linewidth=LINE_WIDTH_RA,
                    label=f'{label2} RMSF')

    elif plot_type == 'sasa':
        if 'Area' in df1.columns and 'Area' in df2.columns:
            ra1 = df1['Area'].rolling(window=roll_avg, min_periods=1, center=True).mean()
            ra2 = df2['Area'].rolling(window=roll_avg, min_periods=1, center=True).mean()
            ax.plot(df1['Time'], ra1, color=color1, linewidth=LINE_WIDTH_RA,
                    label=f'{label1} SASA')
            ax.plot(df2['Time'], ra2, color=color2, linewidth=LINE_WIDTH_RA,
                    label=f'{label2} SASA')

    else:
        # Generic XY comparison
        x_col = df1.columns[0]
        y_col = df1.columns[1] if len(df1.columns) > 1 else df1.columns[0]
        if x_col in df1.columns and y_col in df1.columns:
            ra1 = df1[y_col].rolling(window=roll_avg, min_periods=1, center=True).mean()
            ra2 = df2[y_col].rolling(window=roll_avg, min_periods=1, center=True).mean()
            ax.plot(df1[x_col], ra1, color=color1, linewidth=LINE_WIDTH_RA,
                    label=f'{label1}')
            ax.plot(df2[x_col], ra2, color=color2, linewidth=LINE_WIDTH_RA,
                    label=f'{label2}')

    x_title, y_title = resolve_axis_titles(meta1, 'X', 'Y')
    ax.set_xlabel(x_title)
    ax.set_ylabel(y_title)
    ax.set_title(f'Comparison — {meta1.title}')
    ax.legend()
    fig.tight_layout()
    return fig


def compare_multi(
    data_list: list,
    roll_avg: int = ROLL_AVG_DEFAULT_COMPARE,
) -> plt.Figure:
    """Create comparison plot for multiple XVG files of the same type.

    data_list: list of (DataFrame, XVGMetadata, label) tuples.
    """
    if not data_list:
        raise ValueError('No data provided for comparison')

    plot_type = data_list[0][1].plot_type

    if plot_type == 'energy':
        return _compare_multi_energy(data_list, roll_avg)
    elif plot_type == 'pca':
        return _compare_multi_pca(data_list)

    fig, ax = plt.subplots(figsize=FIGURE_SIZE_SINGLE)

    if plot_type == 'rmsf':
        for idx, (df, meta, label) in enumerate(data_list):
            if 'RMSF' in df.columns and 'Residue' in df.columns:
                ax.plot(df['Residue'], df['RMSF'],
                        color=MULTI_COLORS[idx % len(MULTI_COLORS)],
                        linewidth=LINE_WIDTH_RA, label=label)

    elif plot_type == 'sasa':
        for idx, (df, meta, label) in enumerate(data_list):
            if 'Area' in df.columns and 'Time' in df.columns:
                ra = df['Area'].rolling(window=roll_avg, min_periods=1, center=True).mean()
                ax.plot(df['Time'], ra,
                        color=MULTI_COLORS[idx % len(MULTI_COLORS)],
                        linewidth=LINE_WIDTH_RA, label=label)

    elif plot_type in ('rmsd', 'gyration'):
        y_col = 'RMSD' if plot_type == 'rmsd' else 'Rg'
        y_fallback = 'RMSD (nm)' if plot_type == 'rmsd' else 'Rg (nm)'
        title = 'RMSD' if plot_type == 'rmsd' else 'Radius of Gyration'
        for idx, (df, meta, label) in enumerate(data_list):
            if y_col in df.columns and 'Time' in df.columns:
                ra = df[y_col].rolling(window=roll_avg, min_periods=1, center=True).mean()
                ax.plot(df['Time'], ra,
                        color=MULTI_COLORS[idx % len(MULTI_COLORS)],
                        linewidth=LINE_WIDTH_RA, label=label)

    else:
        # Generic XY
        for idx, (df, meta, label) in enumerate(data_list):
            x_col = df.columns[0]
            y_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]
            if x_col in df.columns and y_col in df.columns:
                ra = df[y_col].rolling(window=roll_avg, min_periods=1, center=True).mean()
                ax.plot(df[x_col], ra,
                        color=MULTI_COLORS[idx % len(MULTI_COLORS)],
                        linewidth=LINE_WIDTH_RA, label=label)

    x_title, y_title = resolve_axis_titles(data_list[0][1], 'X', 'Y')
    ax.set_xlabel(x_title)
    ax.set_ylabel(y_title)
    ax.set_title(f'Comparison ({len(data_list)} files)')
    ax.legend()
    fig.tight_layout()
    return fig


def _compare_energy(
    df1, meta1, df2, meta2, label1, label2, roll_avg
) -> plt.Figure:
    """Energy comparison: multi-panel grid with both datasets per panel."""
    y_cols = [c for c in df1.columns if c != 'Time' and c in df2.columns]
    n_y = len(y_cols)
    if n_y == 0:
        fig, ax = plt.subplots(figsize=FIGURE_SIZE_SINGLE)
        return fig

    n_cols = min(2, n_y) if n_y > 1 else 1
    n_rows = max(1, (n_y + n_cols - 1) // n_cols)

    fig, axes = plt.subplots(n_rows, n_cols,
                              figsize=(12, n_rows * FIGURE_SIZE_MULTI_ROW_HEIGHT),
                              sharex=True, squeeze=False)
    axes_flat = axes.flatten()
    color1, color2 = COMPARE_COLORS

    units = _parse_y_units(meta1.y_label)
    y_titles = _build_y_titles(y_cols, units)

    for idx, y_col in enumerate(y_cols):
        ax = axes_flat[idx]
        ra1 = df1[y_col].rolling(window=roll_avg, min_periods=1, center=True).mean()
        ra2 = df2[y_col].rolling(window=roll_avg, min_periods=1, center=True).mean()
        ax.plot(df1['Time'], ra1, color=color1, linewidth=LINE_WIDTH_RA, label=label1)
        ax.plot(df2['Time'], ra2, color=color2, linewidth=LINE_WIDTH_RA, label=label2)
        ax.set_ylabel(y_titles.get(y_col, y_col))
        ax.set_title(y_col)

    for idx in range(n_y, len(axes_flat)):
        axes_flat[idx].set_visible(False)

    x_title, _ = resolve_axis_titles(meta1, 'Time (ps)', '')
    for ax_row in axes[-1]:
        if ax_row.get_visible():
            ax_row.set_xlabel(x_title)

    fig.suptitle(f'Energy Comparison — {label1} vs {label2}', fontsize=14)
    fig.tight_layout()
    return fig


def _compare_pca(df1, meta1, df2, meta2, label1, label2) -> plt.Figure:
    """PCA comparison: side-by-side hexbin density plots."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    if 'PC1' in df1.columns and 'PC2' in df1.columns:
        hb1 = ax1.hexbin(df1['PC1'], df1['PC2'], cmap='viridis', gridsize=30, mincnt=1)
        fig.colorbar(hb1, ax=ax1, label='Density')
    ax1.set_title(label1)

    if 'PC1' in df2.columns and 'PC2' in df2.columns:
        hb2 = ax2.hexbin(df2['PC1'], df2['PC2'], cmap='viridis', gridsize=30, mincnt=1)
        fig.colorbar(hb2, ax=ax2, label='Density')
    ax2.set_title(label2)

    x_title, y_title = resolve_axis_titles(meta1, 'PC1', 'PC2')
    ax1.set_xlabel(x_title)
    ax1.set_ylabel(y_title)
    ax2.set_xlabel(x_title)
    ax2.set_ylabel(y_title)

    fig.suptitle(f'PCA Comparison — {label1} vs {label2}', fontsize=14)
    fig.tight_layout()
    return fig


def _compare_multi_energy(data_list: list, roll_avg: int) -> plt.Figure:
    """Multi-file energy comparison: multi-panel grid with all files per panel."""
    y_cols = [c for c in data_list[0][0].columns
              if c != 'Time' and all(c in d[0].columns for d in data_list)]
    n_y = len(y_cols)
    if n_y == 0:
        fig, ax = plt.subplots(figsize=FIGURE_SIZE_SINGLE)
        return fig

    n_cols = min(2, n_y) if n_y > 1 else 1
    n_rows = max(1, (n_y + n_cols - 1) // n_cols)

    fig, axes = plt.subplots(n_rows, n_cols,
                              figsize=(12, n_rows * FIGURE_SIZE_MULTI_ROW_HEIGHT),
                              sharex=True, squeeze=False)
    axes_flat = axes.flatten()

    units = _parse_y_units(data_list[0][1].y_label)
    y_titles = _build_y_titles(y_cols, units)

    for idx, y_col in enumerate(y_cols):
        ax = axes_flat[idx]
        for file_idx, (df, meta, label) in enumerate(data_list):
            if y_col in df.columns:
                ra = df[y_col].rolling(window=roll_avg, min_periods=1, center=True).mean()
                ax.plot(df['Time'], ra,
                        color=MULTI_COLORS[file_idx % len(MULTI_COLORS)],
                        linewidth=LINE_WIDTH_RA, label=label)
        ax.set_ylabel(y_titles.get(y_col, y_col))
        ax.set_title(y_col)

    for idx in range(n_y, len(axes_flat)):
        axes_flat[idx].set_visible(False)

    x_title, _ = resolve_axis_titles(data_list[0][1], 'Time (ps)', '')
    for ax_row in axes[-1]:
        if ax_row.get_visible():
            ax_row.set_xlabel(x_title)

    fig.suptitle(f'Energy Comparison ({len(data_list)} files)', fontsize=14)
    fig.tight_layout()
    return fig


def _compare_multi_pca(data_list: list) -> plt.Figure:
    """Multi-file PCA comparison: multi-panel hexbin layout."""
    n_files = len(data_list)
    n_cols = min(3, n_files)
    n_rows = max(1, (n_files + n_cols - 1) // n_cols)

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(14, 6 * n_rows), squeeze=False)
    axes_flat = axes.flatten()

    x_title, y_title = resolve_axis_titles(data_list[0][1], 'PC1', 'PC2')

    for idx, (df, meta, label) in enumerate(data_list):
        ax = axes_flat[idx]
        if 'PC1' in df.columns and 'PC2' in df.columns:
            hb = ax.hexbin(df['PC1'], df['PC2'], cmap='viridis', gridsize=30, mincnt=1)
            fig.colorbar(hb, ax=ax, label='Density')
        ax.set_xlabel(x_title)
        ax.set_ylabel(y_title)
        ax.set_title(label)

    for idx in range(n_files, len(axes_flat)):
        axes_flat[idx].set_visible(False)

    fig.suptitle(f'PCA Comparison ({n_files} files)', fontsize=14)
    fig.tight_layout()
    return fig