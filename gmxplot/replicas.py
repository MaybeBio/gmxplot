"""Replica aggregation: faint per-replica lines + mean with a SD/SEM band.

Replicas are time-normalized and windowed independently, then aligned onto a
common x grid (``union`` / ``first`` / ``intersection``) by ``np.interp``
within each replica's own support (no extrapolation).  Smoothing, when
requested, is applied per replica *before* aggregation; the summary CSV always
uses the raw (unsmoothed) windowed data.
"""

import os
from typing import List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

from .config import (
    BAND_ALPHA, BAND_COLOR, FIGURE_SIZE_SINGLE, MEAN_LINE_COLOR,
    MULTI_COLORS, REPLICA_LINE_ALPHA,
)
from .dataset import Dataset
from .plotting import StyleOptions, smooth_series, _make_axes, _x_title, _y_titles
from .stats import compute_series_stats


def _align_grid(datasets: List[Dataset], align: str) -> np.ndarray:
    xs = [ds.x.values for ds in datasets]
    if align == 'first':
        return np.sort(xs[0])
    if align == 'intersection':
        g = xs[0]
        for x in xs[1:]:
            g = np.intersect1d(g, x)
        return g
    return np.sort(np.unique(np.concatenate(xs)))


def _replica_matrix(grid: np.ndarray, datasets: List[Dataset], col: str,
                    smooth: bool) -> np.ndarray:
    """Interpolate each replica onto ``grid``; NaN outside its support."""
    mat = np.full((len(datasets), len(grid)), np.nan)
    for i, ds in enumerate(datasets):
        if col not in ds.y_cols or ds.x_col is None:
            continue
        x = ds.x.values.astype(float)
        y = ds.y(col).values.astype(float)
        order = np.argsort(x)
        x, y = x[order], y[order]
        if smooth and ds.kind == 'timeseries' and ds.roll_samples:
            y = smooth_series(pd.Series(y), ds.roll_samples).values
        mat[i] = np.interp(grid, x, y)
        mat[i][(grid < x[0]) | (grid > x[-1])] = np.nan
    return mat


def _draw_band(ax, grid: np.ndarray, mat: np.ndarray, style: StyleOptions,
               band: str, min_replicas: int) -> None:
    count = np.sum(~np.isnan(mat), axis=0)
    with np.errstate(all='ignore'):
        mean = np.nanmean(mat, axis=0)
        sd = np.nanstd(mat, axis=0)
    sem = sd / np.sqrt(np.maximum(count, 1))
    valid = count >= min_replicas
    mean_plot = np.where(valid, mean, np.nan)

    for i in range(mat.shape[0]):
        ax.plot(grid, mat[i], color=MULTI_COLORS[i % len(MULTI_COLORS)],
                alpha=REPLICA_LINE_ALPHA, lw=1.0)

    ax.plot(grid, mean_plot, color=MEAN_LINE_COLOR, lw=style.line_width, label='mean')
    if band == 'sd':
        spread = sd
    elif band == 'sem':
        spread = sem
    else:
        return
    ax.fill_between(grid, mean - spread, mean + spread,
                    where=valid, color=BAND_COLOR, alpha=BAND_ALPHA, lw=0,
                    interpolate=False)


def _legend_proxy(ax) -> None:
    handles = [
        Line2D([], [], color=MEAN_LINE_COLOR, lw=1.5, label='mean'),
        Line2D([], [], color='0.5', alpha=REPLICA_LINE_ALPHA, lw=1.0, label='replica'),
    ]
    ax.legend(handles=handles, loc='best')


def _write_long_csv(path: str, grid: np.ndarray, datasets: List[Dataset],
                    labels: List[str], y_cols: List[str]) -> None:
    rows = []
    for col in y_cols:
        mat = _replica_matrix(grid, datasets, col, smooth=False)
        for i, ds in enumerate(datasets):
            for j, xv in enumerate(grid):
                if not np.isnan(mat[i, j]):
                    rows.append({'x': xv, 'series': col,
                                 'replica': labels[i], 'value': mat[i, j]})
    df = pd.DataFrame(rows, columns=['x', 'series', 'replica', 'value'])
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    df.to_csv(path, index=False, float_format='%.8g')


def _write_summary_csv(path: str, datasets: List[Dataset], labels: List[str],
                       y_cols: List[str]) -> None:
    rows = []
    for col in y_cols:
        rep_means = []
        for i, ds in enumerate(datasets):
            if col not in ds.y_cols:
                continue
            y = ds.df_win[col].values.astype(float)
            x = ds.df_win[ds.x_col].values.astype(float) if ds.x_col is not None else None
            r = compute_series_stats(x, y, ds.kind)
            rep_means.append(r['mean'])
            rows.append({'series': col, 'replica': labels[i], 'n': r['n'],
                         'mean': r['mean'], 'sd': r['sd'], 'sem': r.get('sem')})
        if rep_means:
            m = float(np.nanmean(rep_means))
            s = float(np.nanstd(rep_means, ddof=1)) if len(rep_means) > 1 else 0.0
            rows.append({'series': col, 'replica': 'MEAN', 'n': len(rep_means),
                         'mean': m, 'sd': s, 'sem': s / np.sqrt(len(rep_means))})
    df = pd.DataFrame(rows, columns=['series', 'replica', 'n', 'mean', 'sd', 'sem'])
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    df.to_csv(path, index=False, float_format='%.8g')


def _replica_bar(datasets: List[Dataset], labels: List[str],
                 style: StyleOptions, min_replicas: int) -> plt.Figure:
    ds0 = datasets[0]
    fig, axes, _ = _make_axes(len(ds0.y_cols), style.figsize)
    for ax, col in zip(axes, ds0.y_cols):
        xs = [np.asarray(ds.df_win[ds.x_col].values) for ds in datasets
              if col in ds.y_cols]
        if any(len(x) != len(xs[0]) or not np.allclose(x, xs[0]) for x in xs):
            raise ValueError(
                f'bar series {col!r} requires exact x alignment across replicas; '
                'use --kind or --y-col to restrict, or align the bins first'
            )
        mat = np.array([ds.df_win[col].values for ds in datasets if col in ds.y_cols])
        mean = np.nanmean(mat, axis=0)
        sd = np.nanstd(mat, axis=0)
        x_pos = xs[0]
        width = 0.8 * np.median(np.diff(np.sort(x_pos))) if len(x_pos) > 1 else 0.8
        ax.bar(x_pos.astype(float), mean, yerr=sd, width=width, color=BAND_COLOR,
               alpha=0.8, capsize=3, label='mean±SD')
        ax.set_title(col)
        if style.legend:
            ax.legend()
    fig.suptitle(style.title or ds0.meta.title, fontsize=14)
    fig.tight_layout()
    return fig


def replica_plot(
    datasets: List[Dataset], labels: List[str], style: StyleOptions,
    align: str = 'union', band: str = 'sd', min_replicas: int = 2,
    csv_path: Optional[str] = None, summary_csv: Optional[str] = None,
) -> plt.Figure:
    """Aggregate replicas into a mean±band figure, optionally writing CSVs."""
    ds0 = datasets[0]
    y_cols = ds0.y_cols

    if ds0.kind == 'pca':
        from .comparison import compare_datasets
        return compare_datasets(datasets, labels, style)

    if ds0.kind == 'bar':
        fig = _replica_bar(datasets, labels, style, min_replicas)
    else:
        grid = _align_grid(datasets, align)
        fig, axes, _ = _make_axes(len(y_cols), style.figsize)
        y_titles = _y_titles(ds0)
        for ax, col in zip(axes, y_cols):
            mat = _replica_matrix(grid, datasets, col, smooth=True)
            _draw_band(ax, grid, mat, style, band, min_replicas)
            ax.set_xlabel(_x_title(ds0, style))
            ax.set_ylabel(y_titles[col])
            ax.set_title(col)
            ax.grid(style.grid)
            _legend_proxy(ax)
        if len(y_cols) > 1:
            fig.suptitle(style.title or ds0.meta.title, fontsize=14)
        fig.tight_layout()

    if csv_path:
        _write_long_csv(csv_path, _align_grid(datasets, align), datasets, labels, y_cols)
    if summary_csv:
        _write_summary_csv(summary_csv, datasets, labels, y_cols)
    return fig
