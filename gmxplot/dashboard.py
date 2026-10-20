"""JSON-manifest dashboard: assemble heterogeneous XVG panels into one figure.

A manifest describes a grid of panels.  Each panel is either a single file
(``file``) or a replica group (``files``), and is resolved through the same
Dataset pipeline as the CLI.  Multi-column panels are expanded into one sub-plot
per y column so each axis carries a single, self-consistent unit.
"""

import json
import os
from pathlib import Path
from typing import List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .config import (
    DPI_DEFAULT, FIGURE_SIZE_MULTI_ROW_HEIGHT, LINE_WIDTH_RAW, RA_COLOR, RAW_COLOR,
)
from .dataset import DatasetOptions, prepare_dataset
from .escape_codes import clean_gromacs_label
from .parser import read_xvg
from .plotting import StyleOptions, smooth_series
from .replicas import _align_grid, _replica_matrix, _draw_band
from .stats import CSV_COLUMNS, compute_dataset_stats

GLOBAL_KEYS = {'title', 'time_unit', 'start', 'end', 't_eq', 'cols', 'figsize',
               'sharex', 'dpi', 'panels'}
PANEL_KEYS = {'file', 'files', 'labels', 'kind', 'type', 'x_col', 'y_col', 'y_cols',
              'all_cols', 'title', 'xlabel', 'ylabel', 'ylog', 'ylim', 'xlim',
              'hline', 'vline', 'start', 'end', 't_eq', 'roll_window', 'roll_samples',
              'legend', 'band', 'align', 'min_replicas'}


def _as_list(v) -> Optional[List]:
    if v is None:
        return None
    if isinstance(v, list):
        return v
    return [v]


def _as_float_list(v) -> List[float]:
    if v is None:
        return []
    if isinstance(v, (int, float)):
        return [float(v)]
    return [float(x) for x in v]


def _check_keys(d, known, strict, context):
    unknown = set(d) - known
    if unknown:
        for k in sorted(unknown):
            print(f'[warning] unknown {context} key: {k!r}')
        if strict:
            raise ValueError(f'unknown {context} key(s): {", ".join(sorted(unknown))}')


def _load_manifest(path: str) -> dict:
    with open(path, 'r') as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError('manifest must be a JSON object')
    if 'panels' not in data:
        raise ValueError('manifest requires a "panels" list')
    return data


def _opts_from(manifest: dict, panel: dict) -> DatasetOptions:
    y_col = _as_list(panel.get('y_col') or panel.get('y_cols'))
    return DatasetOptions(
        kind=panel.get('kind'), family=panel.get('type'),
        x_col=panel.get('x_col'), y_cols=y_col,
        all_cols=panel.get('all_cols', False),
        time_unit=manifest.get('time_unit', 'auto'),
        normalize_time=True,
        start=panel.get('start', manifest.get('start')),
        end=panel.get('end', manifest.get('end')),
        t_eq=panel.get('t_eq', manifest.get('t_eq')),
        plot_full=False,
        roll_samples=panel.get('roll_samples'),
        roll_window=panel.get('roll_window'),
    )


def _base_sub(panel, manifest, title):
    return {
        'title': panel.get('title') or title,
        'xlabel': panel.get('xlabel'),
        'ylabel': panel.get('ylabel'),
        'ylim': panel.get('ylim'),
        'xlim': panel.get('xlim'),
        'ylog': panel.get('ylog', False),
        'hline': _as_float_list(panel.get('hline')),
        'vline': _as_float_list(panel.get('vline')),
        'legend': panel.get('legend', True),
        't_eq': panel.get('t_eq', manifest.get('t_eq')),
    }


def _single_sub(ds, col, panel, manifest):
    sub = _base_sub(panel, manifest, ds.meta.title)
    sub.update({'kind': 'single', 'ds': ds, 'col': col})
    return sub


def _replica_sub(datasets, labels, col, panel, manifest):
    sub = _base_sub(panel, manifest, datasets[0].meta.title)
    sub.update({'kind': 'replicas', 'datasets': datasets, 'labels': labels,
                'col': col, 'band': panel.get('band', 'sd'),
                'align': panel.get('align', 'union'),
                'min_replicas': panel.get('min_replicas', 2)})
    return sub


def _pca_sub(ds, panel, manifest, suffix=None):
    sub = _base_sub(panel, manifest, ds.meta.title)
    if suffix:
        sub['title'] = f'{sub["title"]} ({suffix})'
    sub.update({'kind': 'pca', 'ds': ds})
    return sub


def _build_subpanels(manifest: dict, panel: dict) -> List[dict]:
    files = _as_list(panel.get('files'))
    if files:
        labels = _as_list(panel.get('labels')) or [Path(f).stem for f in files]
        datasets = []
        for f, lbl in zip(files, labels):
            df, meta = read_xvg(f)
            opts = _opts_from(manifest, panel)
            opts.label = lbl
            opts.path = f
            datasets.append(prepare_dataset(df, meta, opts))
        if datasets[0].kind == 'pca':
            return [_pca_sub(ds, panel, manifest, suffix=lbl)
                    for ds, lbl in zip(datasets, labels)]
        return [_replica_sub(datasets, labels, col, panel, manifest)
                for col in datasets[0].y_cols]

    fp = panel['file']
    df, meta = read_xvg(fp)
    opts = _opts_from(manifest, panel)
    opts.label = panel.get('title') or Path(fp).stem
    opts.path = fp
    ds = prepare_dataset(df, meta, opts)
    if ds.kind == 'pca':
        return [_pca_sub(ds, panel, manifest)]
    return [_single_sub(ds, col, panel, manifest) for col in ds.y_cols]


# --------------------------------------------------------------------------
# drawing
# --------------------------------------------------------------------------

def _draw_series(ax, ds, col, style: StyleOptions) -> None:
    x = ds.x.values
    y = ds.y(col).values
    kind = ds.kind
    if kind == 'bar':
        width = 0.8 * np.median(np.diff(np.sort(x))) if len(x) > 1 else 0.8
        ax.bar(x.astype(str), y, width=width, color=RA_COLOR, alpha=0.8)
    elif kind == 'histogram':
        ax.plot(x, y, color=RA_COLOR, lw=style.line_width, drawstyle='steps-mid')
    elif kind == 'spectrum':
        ax.plot(x, y, color=RA_COLOR, lw=style.line_width, marker='o', ms=3)
    elif kind == 'scatter':
        ax.scatter(x, y, s=4, alpha=0.5, color=RA_COLOR)
    elif kind == 'timeseries' and ds.roll_samples:
        if not style.no_raw:
            ax.plot(x, y, color=RAW_COLOR, alpha=style.raw_alpha, lw=LINE_WIDTH_RAW)
        ax.plot(x, smooth_series(ds.y(col), ds.roll_samples).values,
                color=RA_COLOR, lw=style.line_width)
    else:
        ax.plot(x, y, color=RA_COLOR, lw=style.line_width)


def _draw_subpanel(ax, sub: dict, style: StyleOptions, letter: str) -> None:
    if sub['kind'] == 'pca':
        ds = sub['ds']
        c1 = ds.y_cols[0]
        c2 = ds.y_cols[1] if len(ds.y_cols) > 1 else ds.y_cols[0]
        hb = ax.hexbin(ds.df_plot[c1].values, ds.df_plot[c2].values,
                       cmap=style.cmap, gridsize=style.pca_gridsize, mincnt=1)
        ax.figure.colorbar(hb, ax=ax, label='Density')
        ax.set_xlabel(clean_gromacs_label(c1))
        ax.set_ylabel(clean_gromacs_label(c2))
    elif sub['kind'] == 'replicas':
        datasets = sub['datasets']
        grid = _align_grid(datasets, sub['align'])
        mat = _replica_matrix(grid, datasets, sub['col'], smooth=True)
        _draw_band(ax, grid, mat, style, sub['band'], sub['min_replicas'])
        ds0 = datasets[0]
        ax.set_xlabel(sub['xlabel'] or clean_gromacs_label(ds0.meta.x_label))
        from .plotting import _y_titles
        ax.set_ylabel(sub['ylabel'] or _y_titles(ds0)[sub['col']])
    else:
        ds = sub['ds']
        _draw_series(ax, ds, sub['col'], style)
        from .plotting import _y_titles
        ax.set_xlabel(sub['xlabel'] or clean_gromacs_label(ds.meta.x_label))
        ax.set_ylabel(sub['ylabel'] or _y_titles(ds)[sub['col']])

    if sub['ylim']:
        ax.set_ylim(*sub['ylim'])
    if sub['xlim']:
        ax.set_xlim(*sub['xlim'])
    if sub['ylog']:
        ax.set_yscale('log')
    for v in sub['vline']:
        ax.axvline(v, color='0.5', ls='--', lw=0.8)
    for h in sub['hline']:
        ax.axhline(h, color='0.5', ls='--', lw=0.8)

    ds_ref = sub.get('ds') or (sub['datasets'][0] if sub['kind'] == 'replicas' else None)
    if ds_ref is not None and ds_ref.x_is_time and sub['t_eq'] is not None:
        ax.axvline(sub['t_eq'], color='k', ls=':', lw=1.0)

    ax.set_title(f'{letter}  {sub["title"]}')
    ax.grid(style.grid)


def _collect_stats(subs: List[dict]) -> List[dict]:
    rows = []
    for sub in subs:
        if sub['kind'] == 'replicas':
            dss = sub['datasets']
        else:
            dss = [sub['ds']]
        for ds in dss:
            for r in compute_dataset_stats(ds):
                r = dict(r)
                r['panel'] = sub['title']
                rows.append(r)
    return rows


def render_dashboard(
    manifest_path: str, dpi: int = DPI_DEFAULT,
    figsize: Optional[tuple] = None, cols: Optional[int] = None,
    sharex: bool = True, strict: bool = False,
    stats_csv: Optional[str] = None,
) -> plt.Figure:
    """Load a manifest and render its panels into a single figure."""
    manifest = _load_manifest(manifest_path)
    _check_keys(manifest, GLOBAL_KEYS, strict, 'manifest')
    for panel in manifest['panels']:
        _check_keys(panel, PANEL_KEYS, strict, 'panel')

    subs: List[dict] = []
    for panel in manifest['panels']:
        subs.extend(_build_subpanels(manifest, panel))

    if not subs:
        raise ValueError('manifest produced no panels')

    n_cols = cols or manifest.get('cols') or 2
    n_rows = (len(subs) + n_cols - 1) // n_cols
    size = figsize or manifest.get('figsize') or (14, max(6, n_rows * FIGURE_SIZE_MULTI_ROW_HEIGHT))

    def _sub_ds(sub):
        return sub.get('ds') or (sub['datasets'][0] if sub.get('datasets') else None)

    _all_time = True
    for sub in subs:
        ds = _sub_ds(sub)
        if ds is None or not ds.x_is_time:
            _all_time = False
            break
    sharex = sharex and manifest.get('sharex', True) and _all_time

    fig, axes = plt.subplots(n_rows, n_cols, figsize=size, squeeze=False,
                             sharex=sharex)
    axes_flat = list(axes.flatten())

    style = StyleOptions(grid=True)
    for i, sub in enumerate(subs):
        _draw_subpanel(axes_flat[i], sub, style, chr(65 + i))
    for i in range(len(subs), len(axes_flat)):
        axes_flat[i].set_visible(False)

    if manifest.get('title'):
        fig.suptitle(manifest['title'], fontsize=15)
    fig.tight_layout()

    if stats_csv:
        rows = _collect_stats(subs)
        cols_out = ['panel'] + CSV_COLUMNS
        df = pd.DataFrame(rows, columns=cols_out)
        parent = os.path.dirname(stats_csv)
        if parent:
            os.makedirs(parent, exist_ok=True)
        df.to_csv(stats_csv, index=False, float_format='%.6g')

    return fig
