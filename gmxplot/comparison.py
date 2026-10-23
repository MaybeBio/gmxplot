"""Multi-dataset overlay comparison built on the Dataset abstraction.

Replaces the old per-family hardcoded ``Time``/``RgX`` handling: every dataset
resolves its own x/y columns, so per-residue SASA (kind=profile, x=Residue) no
longer crashes with ``KeyError: 'Time'``, and gyration compares only the
primary ``Rg`` column unless ``--all-cols`` is requested.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .config import (
    FIGURE_SIZE_SINGLE, FIGURE_SIZE_MULTI_ROW_HEIGHT, LINE_WIDTH_RA,
)
from .dataset import Dataset
from .escape_codes import clean_gromacs_label
from .plotting import (
    StyleOptions, smooth_series, resolve_palette, _y_titles, _x_title, _make_axes,
)


def compare_datasets(
    datasets: list, labels: list, style: StyleOptions,
    roll_samples: int | None = None,
) -> plt.Figure:
    """Overlay two or more resolved Datasets, dispatching on the shared kind."""
    if not datasets:
        raise ValueError('No datasets to compare')
    ds0 = datasets[0]
    if ds0.kind == 'pca':
        return _compare_pca(datasets, labels, style)
    if ds0.family == 'energy' and len(ds0.y_cols) > 1:
        return _compare_multipanel(datasets, labels, style)
    return _compare_single(datasets, labels, style)


def _effective_roll(ds: Dataset, roll_samples: int | None) -> int:
    return ds.roll_samples if roll_samples is None else roll_samples


def _overlay_line(ax, ds: Dataset, col: str, color: str, label: str,
                  style: StyleOptions, roll: int) -> None:
    x = ds.x.values
    y = ds.y(col).values
    if roll:
        if not style.no_raw:
            ax.plot(x, y, color=color, alpha=0.35, lw=0.8)
        ys = smooth_series(ds.y(col), roll).values
        ax.plot(x, ys, color=color, lw=style.line_width, label=label)
    else:
        ax.plot(x, y, color=color, lw=style.line_width, label=label)


def _compare_single(datasets: list, labels: list, style: StyleOptions) -> plt.Figure:
    ds0 = datasets[0]
    multi = len(ds0.y_cols) > 1
    colors = resolve_palette(style.palette, len(datasets))
    fig, ax = plt.subplots(figsize=style.figsize or FIGURE_SIZE_SINGLE)
    if not multi:
        # One series per file: match by position, not by column name.  GROMACS
        # names the legend after the selection, so files that differ only in the
        # selection (ZF1-DNA, ZF2-DNA, ...) carry different column names and
        # only the first file would be drawn.
        for i, ds in enumerate(datasets):
            if not ds.y_cols:
                continue
            _overlay_line(ax, ds, ds.y_cols[0], colors[i],
                          labels[i] if labels else str(i), style,
                          _effective_roll(ds, None))
    else:
        for col in ds0.y_cols:
            for i, ds in enumerate(datasets):
                if col not in ds.y_cols:
                    continue
                color = colors[i]
                label = labels[i] if labels else str(i)
                label = f'{label} {col}'
                _overlay_line(ax, ds, col, color, label, style, _effective_roll(ds, None))
    ax.set_xlabel(_x_title(ds0, style))
    ax.set_ylabel(style.ylabel or ds0.meta.y_label or '')
    ax.set_title(style.title or ds0.meta.title)
    ax.grid(style.grid)
    if style.legend and ax.get_legend_handles_labels()[0]:
        ax.legend(loc=style.legend_loc)
    fig.tight_layout()
    return fig


def _compare_multipanel(datasets: list, labels: list, style: StyleOptions) -> plt.Figure:
    ds0 = datasets[0]
    y_cols = ds0.y_cols
    colors = resolve_palette(style.palette, len(datasets))
    fig, axes, n_cols = _make_axes(len(y_cols), style.figsize)
    y_titles = _y_titles(ds0)
    x_title = _x_title(ds0, style)
    for idx, col in enumerate(y_cols):
        ax = axes[idx]
        for i, ds in enumerate(datasets):
            if col not in ds.y_cols:
                continue
            color = colors[i]
            _overlay_line(ax, ds, col, color, labels[i] if labels else str(i),
                          style, _effective_roll(ds, None))
        ax.set_ylabel(y_titles.get(col, col))
        ax.set_title(col)
    n_rows = (len(y_cols) + n_cols - 1) // n_cols
    for ax in axes[(n_rows - 1) * n_cols:len(y_cols)]:
        ax.set_xlabel(x_title)
    fig.suptitle(style.title or ds0.meta.title, fontsize=14)
    fig.tight_layout()
    return fig


def _compare_pca(datasets: list, labels: list, style: StyleOptions) -> plt.Figure:
    n = len(datasets)
    n_cols = min(3, n)
    n_rows = (n + n_cols - 1) // n_cols
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(14, 6 * n_rows), squeeze=False)
    axes_flat = list(axes.flatten())
    for i, ds in enumerate(datasets):
        ax = axes_flat[i]
        c1 = ds.y_cols[0]
        c2 = ds.y_cols[1] if len(ds.y_cols) > 1 else ds.y_cols[0]
        hb = ax.hexbin(ds.df_plot[c1].values, ds.df_plot[c2].values,
                       cmap=style.cmap, gridsize=style.pca_gridsize, mincnt=1)
        fig.colorbar(hb, ax=ax, label='Density')
        ax.set_xlabel(clean_gromacs_label(c1))
        ax.set_ylabel(clean_gromacs_label(c2))
        ax.set_title(labels[i] if labels else str(i))
    for idx in range(n, len(axes_flat)):
        axes_flat[idx].set_visible(False)
    fig.suptitle(style.title or datasets[0].meta.title, fontsize=14)
    fig.tight_layout()
    return fig
