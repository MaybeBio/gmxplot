"""Matplotlib plotting primitives keyed on dataset kind."""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from .config import (
    DPI_DEFAULT, LINE_WIDTH_RAW, LINE_WIDTH_RA, RAW_ALPHA, RA_COLOR, RAW_COLOR,
    FIGURE_SIZE_SINGLE, FIGURE_SIZE_MULTI_ROW_HEIGHT, MULTI_COLORS,
)
from .dataset import Dataset
from .escape_codes import clean_gromacs_label

sns.set_style('whitegrid')
sns.set_context('paper', font_scale=1.2)


@dataclass
class StyleOptions:
    figsize: Optional[Tuple[float, float]] = None
    title: Optional[str] = None
    xlabel: Optional[str] = None
    ylabel: Optional[str] = None
    xlim: Optional[Tuple[float, float]] = None
    ylim: Optional[Tuple[float, float]] = None
    xlog: bool = False
    ylog: bool = False
    grid: bool = True
    legend: bool = True
    legend_loc: str = 'best'
    cmap: str = 'viridis'
    palette: Optional[str] = None
    line_width: float = LINE_WIDTH_RA
    raw_alpha: float = RAW_ALPHA
    hlines: List[float] = field(default_factory=list)
    vlines: List[float] = field(default_factory=list)
    no_raw: bool = False
    dpi: int = DPI_DEFAULT
    hist_style: str = 'step'          # 'step' | 'bar'
    pca_scatter: bool = False
    pca_gridsize: int = 30


def smooth_series(y, n: int):
    if not n or len(y) < 2:
        return y
    s = pd.Series(y)
    out = s.rolling(window=n, min_periods=1, center=True).mean()
    return out if isinstance(y, pd.Series) else out.values


def resolve_palette(palette: Optional[str], n: int) -> List[str]:
    """Resolve a ``--palette`` spec into ``n`` hex color strings.

    Accepts a comma-separated color list (cycled as needed), a matplotlib
    colormap name, or a seaborn palette name. Falls back to ``MULTI_COLORS``.
    """
    if not palette:
        return [MULTI_COLORS[i % len(MULTI_COLORS)] for i in range(n)]
    import matplotlib.colors as mcolors
    if ',' in palette:
        specs = [p.strip() for p in palette.split(',') if p.strip()]
        if not specs:
            raise ValueError('--palette color list is empty')
        return [specs[i % len(specs)] for i in range(n)]
    try:
        pal = sns.color_palette(palette, n_colors=n)
        return [mcolors.to_hex(c) for c in pal]
    except Exception:
        pass
    try:
        cmap = plt.get_cmap(palette)
        step = n - 1 if n > 1 else 1
        return [mcolors.to_hex(cmap(i / step)) for i in range(n)]
    except Exception:
        raise ValueError(
            f'unknown palette {palette!r}; use a comma-separated color list, '
            'a matplotlib colormap name, or a seaborn palette name')


def _make_axes(n_panels: int, figsize: Optional[Tuple[float, float]] = None):
    if n_panels <= 1:
        fig, ax = plt.subplots(figsize=figsize or FIGURE_SIZE_SINGLE)
        return fig, [ax], 1
    n_cols = min(2, n_panels)
    n_rows = (n_panels + n_cols - 1) // n_cols
    size = figsize or (12, n_rows * FIGURE_SIZE_MULTI_ROW_HEIGHT)
    fig, axes = plt.subplots(n_rows, n_cols, figsize=size, squeeze=False)
    axes_flat = list(axes.flatten())
    for idx in range(n_panels, len(axes_flat)):
        axes_flat[idx].set_visible(False)
    return fig, axes_flat, n_cols


# GROMACS writes ONE y-axis label for a whole multi-column file and merges
# repeated units: energy.xvg has 6 columns but the label only lists five
# "(...)" groups.  A purely positional assignment therefore shifts every unit
# after the duplicate (Total Energy gets K, Temperature gets bar, ...), so fall
# back to per-term units when the counts do not line up.
_TERM_UNITS = [
    (r'\bdensity\b', 'kg/m^3'),
    (r'\bpressure\b|\bpres\.|\bvir-', 'bar'),
    (r'\btemperature\b|^t-', 'K'),
    (r'\bbox-[xyz]\b', 'nm'),
    (r'\bvolume\b', 'nm^3'),
    (r'\bpotential\b|\bkinetic\b|\btotal energy\b|\benthalpy\b|\bgibbs\b',
     'kJ/mol'),
    (r'\bcoul|\blj-|\bdisper|\bbond|\bangle\b|\bdihedral|\bimproper|\bvdw',
     'kJ/mol'),
]


def _unit_for_column(col: str, units: List[str]) -> Optional[str]:
    """Resolve a unit for one column when the file's unit list is incomplete."""
    label = clean_gromacs_label(col).lower()
    for pattern, unit in _TERM_UNITS:
        if re.search(pattern, label):
            return unit
    # A single unit for the whole file applies to every column.
    return units[0] if len(units) == 1 else None


def _y_titles(ds: Dataset) -> dict:
    """Map each y column to a display label with units when available."""
    units = [clean_gromacs_label(u)
             for u in re.findall(r'\(([^()]+)\)', ds.meta.y_label)]
    out = {}
    if units and len(units) == len(ds.y_cols):
        for col, unit in zip(ds.y_cols, units):
            out[col] = f'{clean_gromacs_label(col)} ({unit})'
        return out
    for col in ds.y_cols:
        base = clean_gromacs_label(col)
        unit = _unit_for_column(col, units)
        out[col] = f'{base} ({unit})' if unit else base
    return out


def _x_title(ds: Dataset, style: StyleOptions) -> str:
    if style.xlabel:
        return clean_gromacs_label(style.xlabel)
    if ds.x_col and ds.meta.x_label:
        return clean_gromacs_label(ds.meta.x_label)
    return ds.x_col or ''


def _apply_style(ax, style: StyleOptions, x_label: str, y_label: str) -> None:
    if x_label:
        ax.set_xlabel(clean_gromacs_label(x_label))
    if y_label:
        ax.set_ylabel(clean_gromacs_label(y_label))
    if style.xlim:
        ax.set_xlim(*style.xlim)
    if style.ylim:
        ax.set_ylim(*style.ylim)
    if style.xlog:
        ax.set_xscale('log')
    if style.ylog:
        ax.set_yscale('log')
    ax.grid(style.grid)


def _draw_references(ax, style: StyleOptions) -> None:
    for v in style.vlines:
        ax.axvline(v, color='0.5', ls='--', lw=0.8)
    for h in style.hlines:
        ax.axhline(h, color='0.5', ls='--', lw=0.8)


def _draw_t_eq(ax, ds: Dataset) -> None:
    if ds.x_is_time and ds.t_eq is not None:
        ax.axvline(ds.t_eq, color='k', ls=':', lw=1.0)
        ax.text(ds.t_eq, 0.01, f'  t_eq={ds.t_eq:g}', transform=ax.get_xaxis_transform(),
                fontsize=9, va='bottom')


def _shade_window(ax, ds: Dataset) -> None:
    if not ds.x_is_time or not ds.plot_full or ds.x_col is None:
        return
    lo, hi = ds.window
    x = ds.df[ds.x_col]
    xmin, xmax = float(x.min()), float(x.max())
    if lo is not None and lo > xmin:
        ax.axvspan(xmin, lo, color='0.8', alpha=0.3, lw=0)
    if hi is not None and hi < xmax:
        ax.axvspan(hi, xmax, color='0.8', alpha=0.3, lw=0)


def _finish(fig, ax, ds: Dataset, style: StyleOptions, y_label: str, title: str) -> None:
    _draw_references(ax, style)
    _draw_t_eq(ax, ds)
    _shade_window(ax, ds)
    ax.set_title(title)
    if style.legend and ax.get_legend_handles_labels()[0]:
        ax.legend(loc=style.legend_loc)
    fig.tight_layout()


def _raw_smooth(ax, x, y, roll_samples: int, style: StyleOptions, color: str = RA_COLOR,
                raw_color: str = RAW_COLOR, label: str = '') -> None:
    if roll_samples and style.no_raw:
        ys = smooth_series(y, roll_samples)
        ax.plot(x, ys, color=color, lw=style.line_width, label=label or 'smooth')
    elif roll_samples:
        ax.plot(x, y, color=raw_color, alpha=style.raw_alpha, lw=LINE_WIDTH_RAW, label='raw')
        ys = smooth_series(y, roll_samples)
        ax.plot(x, ys, color=color, lw=style.line_width, label=f'smooth n={roll_samples}')
    else:
        ax.plot(x, y, color=color, lw=style.line_width, label=label)


def _mean_std(ax, y, color: str, show_mean: bool, show_std: bool) -> None:
    if not show_mean and not show_std:
        return
    mean = float(np.nanmean(y))
    std = float(np.nanstd(y))
    if show_mean:
        ax.axhline(mean, color=color, ls='--', lw=1.0, alpha=0.8)
    if show_std:
        ax.axhline(mean + std, color=color, ls=':', lw=0.5, alpha=0.6)
        ax.axhline(mean - std, color=color, ls=':', lw=0.5, alpha=0.6)


# --------------------------------------------------------------------------
# per-kind primitives
# --------------------------------------------------------------------------

def plot_timeseries(ds: Dataset, style: StyleOptions, show_mean=False, show_std=False,
                    roll_samples: Optional[int] = None) -> plt.Figure:
    rs = ds.roll_samples if roll_samples is None else roll_samples
    x = ds.x.values
    y_titles = _y_titles(ds)
    fig, axes, _ = _make_axes(len(ds.y_cols), style.figsize)
    for ax, col in zip(axes, ds.y_cols):
        y = ds.y(col).values
        _raw_smooth(ax, x, y, rs, style, label=ds.label or None)
        _mean_std(ax, y, RA_COLOR, show_mean, show_std)
        _apply_style(ax, style, _x_title(ds, style), y_titles[col])
        _finish(fig, ax, ds, style, y_titles[col], col)
    if len(ds.y_cols) > 1:
        fig.suptitle(style.title or ds.meta.title, fontsize=14)
    return fig


def plot_profile(ds: Dataset, style: StyleOptions, show_mean=False, show_std=False,
                 roll_samples: Optional[int] = None) -> plt.Figure:
    x = ds.x.values
    y_titles = _y_titles(ds)
    fig, axes, _ = _make_axes(len(ds.y_cols), style.figsize)
    for ax, col in zip(axes, ds.y_cols):
        y = ds.y(col).values
        ax.plot(x, y, color=RA_COLOR, lw=style.line_width)
        _mean_std(ax, y, RA_COLOR, show_mean, show_std)
        _apply_style(ax, style, _x_title(ds, style), y_titles[col])
        _finish(fig, ax, ds, style, y_titles[col], col)
    if len(ds.y_cols) > 1:
        fig.suptitle(style.title or ds.meta.title, fontsize=14)
    return fig


def plot_histogram(ds: Dataset, style: StyleOptions, show_mean=False, show_std=False,
                   roll_samples: Optional[int] = None) -> plt.Figure:
    x = ds.x.values
    y_titles = _y_titles(ds)
    fig, axes, _ = _make_axes(len(ds.y_cols), style.figsize)
    for ax, col in zip(axes, ds.y_cols):
        y = ds.y(col).values
        if style.hist_style == 'bar':
            ax.bar(x, y, width=0.8 * np.median(np.diff(np.sort(x))) if len(x) > 1 else 0.8,
                   color=RA_COLOR, alpha=0.8)
        else:
            ax.plot(x, y, color=RA_COLOR, lw=style.line_width, drawstyle='steps-mid')
        _apply_style(ax, style, _x_title(ds, style), y_titles[col])
        _finish(fig, ax, ds, style, y_titles[col], col)
    if len(ds.y_cols) > 1:
        fig.suptitle(style.title or ds.meta.title, fontsize=14)
    return fig


def plot_spectrum(ds: Dataset, style: StyleOptions, show_mean=False, show_std=False,
                  roll_samples: Optional[int] = None) -> plt.Figure:
    x = ds.x.values
    y_titles = _y_titles(ds)
    fig, axes, _ = _make_axes(len(ds.y_cols), style.figsize)
    for ax, col in zip(axes, ds.y_cols):
        y = ds.y(col).values
        ax.plot(x, y, color=RA_COLOR, lw=style.line_width, marker='o', ms=3)
        _apply_style(ax, style, _x_title(ds, style), y_titles[col])
        _finish(fig, ax, ds, style, y_titles[col], col)
    if len(ds.y_cols) > 1:
        fig.suptitle(style.title or ds.meta.title, fontsize=14)
    return fig


def plot_bar(ds: Dataset, style: StyleOptions, show_mean=False, show_std=False,
             roll_samples: Optional[int] = None) -> plt.Figure:
    x = ds.x.values
    y_titles = _y_titles(ds)
    fig, axes, _ = _make_axes(len(ds.y_cols), style.figsize)
    for ax, col in zip(axes, ds.y_cols):
        y = ds.y(col).values
        ax.bar(x.astype(str), y, color=RA_COLOR, alpha=0.8)
        _apply_style(ax, style, _x_title(ds, style), y_titles[col])
        _finish(fig, ax, ds, style, y_titles[col], col)
    if len(ds.y_cols) > 1:
        fig.suptitle(style.title or ds.meta.title, fontsize=14)
    return fig


def plot_pca(ds: Dataset, style: StyleOptions, show_mean=False, show_std=False,
             roll_samples: Optional[int] = None) -> plt.Figure:
    fig, ax = plt.subplots(figsize=style.figsize or FIGURE_SIZE_SINGLE)
    c1, c2 = ds.y_cols[0], (ds.y_cols[1] if len(ds.y_cols) > 1 else ds.y_cols[0])
    x = ds.df_plot[c1].values
    y = ds.df_plot[c2].values
    if style.pca_scatter:
        ax.scatter(x, y, s=4, alpha=0.5, c=RA_COLOR)
    else:
        hb = ax.hexbin(x, y, cmap=style.cmap, gridsize=style.pca_gridsize, mincnt=1)
        fig.colorbar(hb, ax=ax, label='Density')
    ax.set_xlabel(clean_gromacs_label(c1))
    ax.set_ylabel(clean_gromacs_label(c2))
    ax.set_title(style.title or ds.meta.title)
    ax.grid(style.grid)
    fig.tight_layout()
    return fig


def plot_scatter(ds: Dataset, style: StyleOptions, show_mean=False, show_std=False,
                 roll_samples: Optional[int] = None) -> plt.Figure:
    x = ds.x.values
    y_titles = _y_titles(ds)
    fig, axes, _ = _make_axes(len(ds.y_cols), style.figsize)
    for ax, col in zip(axes, ds.y_cols):
        y = ds.y(col).values
        ax.scatter(x, y, s=4, alpha=0.5, color=RA_COLOR)
        _apply_style(ax, style, _x_title(ds, style), y_titles[col])
        _finish(fig, ax, ds, style, y_titles[col], col)
    if len(ds.y_cols) > 1:
        fig.suptitle(style.title or ds.meta.title, fontsize=14)
    return fig


def plot_xy(ds: Dataset, style: StyleOptions, show_mean=False, show_std=False,
            roll_samples: Optional[int] = None) -> plt.Figure:
    x = ds.x.values
    y_titles = _y_titles(ds)
    fig, ax = plt.subplots(figsize=style.figsize or FIGURE_SIZE_SINGLE)
    colors = resolve_palette(style.palette, len(ds.y_cols))
    for i, col in enumerate(ds.y_cols):
        y = ds.y(col).values
        ax.plot(x, y, color=colors[i], lw=style.line_width, label=y_titles[col])
    _apply_style(ax, style, _x_title(ds, style),
                 style.ylabel or ds.meta.y_label or '')
    _finish(fig, ax, ds, style, style.ylabel or ds.meta.y_label or '', style.title or ds.meta.title)
    return fig


_PLOT_DISPATCH = {
    'timeseries': plot_timeseries,
    'profile': plot_profile,
    'histogram': plot_histogram,
    'spectrum': plot_spectrum,
    'bar': plot_bar,
    'pca': plot_pca,
    'scatter': plot_scatter,
    'xy': plot_xy,
}


def plot_dataset(ds: Dataset, style: StyleOptions, show_mean=False, show_std=False,
                 roll_samples: Optional[int] = None) -> plt.Figure:
    func = _PLOT_DISPATCH.get(ds.kind, plot_xy)
    return func(ds, style, show_mean, show_std, roll_samples)


def calculate_roll_avg(df: pd.DataFrame, x_col: str = 'Time') -> int:
    """Backward-compatible auto rolling window (samples)."""
    if x_col not in df.columns or len(df) < 10:
        return 10
    x_range = df[x_col].max() - df[x_col].min()
    return max(3, min(100, int(x_range * 0.05)))
