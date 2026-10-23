"""Statistical summary for XVG data.

Statistics are computed on the resolved, windowed dataset.  Time-series data
get a half-window drift test with naive and block-averaged SEM; histograms get
count-weighted x statistics; PCA analyzes every column (there is no x column).
"""

import math
import os
import re
from dataclasses import replace
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from rich.console import Console
from rich.table import Table

from .config import BLOCK_MIN_SIZE, BLOCK_N_EXPONENT, FLAT_THRESHOLD
from .dataset import Dataset, DatasetOptions, prepare_dataset
from .parser import read_xvg

CSV_COLUMNS = [
    'dir', 'file', 'plot', 'family', 'kind',
    'n', 'mean', 'sd', 'sem', 'sem_block', 'sem_used',
    'min', 'q10', 'q50', 'q90', 'max',
    'mean_first_half', 'mean_second_half', 'drift',
    'drift_over_sem', 'drift_over_sem_naive', 'flag',
    'n_blocks', 'block_size',
    'x_weighted_mean', 'x_weighted_sd', 'x_weighted_median', 'x_mode',
    'n_eff', 'sem_weighted',
    'window_start', 'window_end', 'x_unit', 'y_unit',
]


def _clean(x: np.ndarray, y: np.ndarray):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    ok = np.isfinite(x) & np.isfinite(y)
    return x[ok], y[ok]


def _descriptive(y: np.ndarray) -> Dict:
    n = int(len(y))
    if n == 0:
        return {'n': 0, 'mean': np.nan, 'sd': np.nan, 'min': np.nan,
                'q10': np.nan, 'q50': np.nan, 'q90': np.nan, 'max': np.nan}
    mean = float(np.mean(y))
    sd = float(np.std(y, ddof=1)) if n > 1 else 0.0
    return {
        'n': n, 'mean': mean, 'sd': sd,
        'min': float(np.min(y)), 'q10': float(np.quantile(y, 0.1)),
        'q50': float(np.quantile(y, 0.5)), 'q90': float(np.quantile(y, 0.9)),
        'max': float(np.max(y)),
    }


def _block_sem(y: np.ndarray, block_size: int) -> Dict:
    n = int(len(y))
    if n == 0:
        return {'sem_block': np.nan, 'n_blocks': 0, 'block_size': block_size}
    bs = max(BLOCK_MIN_SIZE, int(block_size))
    n_blocks = n // bs
    if n_blocks < 2:
        return {'sem_block': np.nan, 'n_blocks': n_blocks, 'block_size': bs}
    trimmed = y[:n_blocks * bs].reshape(n_blocks, bs)
    block_means = trimmed.mean(axis=1)
    sem_block = float(np.std(block_means, ddof=1) / np.sqrt(n_blocks))
    return {'sem_block': sem_block, 'n_blocks': n_blocks, 'block_size': bs}


def _default_block_size(n: int) -> int:
    return max(BLOCK_MIN_SIZE, int(round(n ** BLOCK_N_EXPONENT)))


def _sem_summary(y: np.ndarray, block_size: Optional[int]) -> Dict:
    d = _descriptive(y)
    n = d['n']
    if n < 2:
        return {**d, 'sem': np.nan, 'sem_block': np.nan, 'sem_used': np.nan,
                'n_blocks': 0, 'block_size': block_size or BLOCK_MIN_SIZE}
    sem_naive = d['sd'] / np.sqrt(n)
    bs = block_size if block_size else _default_block_size(n)
    b = _block_sem(y, bs)
    sem_block = b['sem_block']
    sem_used = sem_naive if not np.isfinite(sem_block) else max(sem_naive, sem_block)
    return {**d, 'sem': sem_naive, 'sem_block': sem_block, 'sem_used': sem_used,
            'n_blocks': b['n_blocks'], 'block_size': b['block_size']}


def _half_window(x: np.ndarray, y: np.ndarray, block_size: Optional[int]) -> Dict:
    mid = 0.5 * (float(x.min()) + float(x.max()))
    a = y[x <= mid]
    b = y[x > mid]
    out = {}
    if len(a) >= 2 and len(b) >= 2:
        sa = _sem_summary(a, block_size)
        sb = _sem_summary(b, block_size)
        ma, mb = sa['mean'], sb['mean']
        drift = mb - ma
        out['mean_first_half'] = ma
        out['mean_second_half'] = mb
        out['drift'] = drift
        # naive ratio (comparable to xvg_stats.py)
        sema_naive = sa['sd'] / np.sqrt(len(a))
        semb_naive = sb['sd'] / np.sqrt(len(b))
        denom_naive = sema_naive ** 2 + semb_naive ** 2
        out['drift_over_sem_naive'] = (
            abs(drift) / np.sqrt(denom_naive) if denom_naive > 0
            else (np.inf if abs(drift) > 0 else np.nan)
        )
        # conservative ratio (max of naive and block SEM per half)
        sema_used = sa['sem_used'] if np.isfinite(sa['sem_used']) else sema_naive
        semb_used = sb['sem_used'] if np.isfinite(sb['sem_used']) else semb_naive
        denom = sema_used ** 2 + semb_used ** 2
        out['drift_over_sem'] = (
            abs(drift) / np.sqrt(denom) if denom > 0
            else (np.inf if abs(drift) > 0 else 0.0)
        )
    else:
        out = {'mean_first_half': np.nan, 'mean_second_half': np.nan,
               'drift': np.nan, 'drift_over_sem': np.nan, 'drift_over_sem_naive': np.nan}
    return out


def _weighted_histogram(x: np.ndarray, y: np.ndarray) -> Dict:
    out = {}
    w = np.clip(y, 0.0, None)
    wsum = float(w.sum())
    if wsum <= 0:
        return {'x_weighted_mean': np.nan, 'x_weighted_sd': np.nan,
                'x_weighted_median': np.nan, 'x_mode': np.nan,
                'n_eff': 0.0, 'sem_weighted': np.nan}
    wmean = float(np.sum(w * x) / wsum)
    wvar = float(np.sum(w * (x - wmean) ** 2) / wsum)
    wsd = np.sqrt(wvar)
    n_eff = wsum * wsum / float(np.sum(w * w)) if np.sum(w * w) > 0 else 0.0
    sem_w = wsd / np.sqrt(n_eff) if n_eff > 0 else np.nan
    # weighted median
    order = np.argsort(x)
    xs, ws = x[order], w[order]
    csum = np.cumsum(ws)
    half = wsum / 2.0
    idx = int(np.searchsorted(csum, half))
    wmedian = float(xs[min(idx, len(xs) - 1)])
    mode = float(xs[int(np.argmax(ws))])
    out = {'x_weighted_mean': wmean, 'x_weighted_sd': wsd,
           'x_weighted_median': wmedian, 'x_mode': mode,
           'n_eff': n_eff, 'sem_weighted': sem_w}
    return out


def compute_series_stats(x: Optional[np.ndarray], y: np.ndarray, kind: str,
                         flat_threshold: float = FLAT_THRESHOLD,
                         block_size: Optional[int] = None) -> Dict:
    """Return a single row dict of statistics for one series."""
    y = np.asarray(y, dtype=float)
    if x is not None:
        x = np.asarray(x, dtype=float)
        x, y = _clean(x, y)
    else:
        y = y[np.isfinite(y)]

    if kind == 'histogram':
        row = _descriptive(y)
        row.update(_weighted_histogram(x, y))
        row.update({'sem': np.nan, 'sem_block': np.nan, 'sem_used': np.nan,
                    'n_blocks': 0, 'block_size': 0,
                    'mean_first_half': np.nan, 'mean_second_half': np.nan,
                    'drift': np.nan, 'drift_over_sem': np.nan,
                    'drift_over_sem_naive': np.nan, 'flag': ''})
        return row

    if kind == 'timeseries':
        row = _sem_summary(y, block_size)
        row.update(_half_window(x, y, block_size))
        d = row['drift_over_sem']
        row['flag'] = 'flat' if np.isfinite(d) and d <= flat_threshold else 'DRIFT'
        return row

    # profile / spectrum / bar / pca / scatter / xy: descriptive only
    row = _descriptive(y)
    row.update({'sem': np.nan, 'sem_block': np.nan, 'sem_used': np.nan,
                'n_blocks': 0, 'block_size': 0,
                'mean_first_half': np.nan, 'mean_second_half': np.nan,
                'drift': np.nan, 'drift_over_sem': np.nan,
                'drift_over_sem_naive': np.nan, 'flag': ''})
    return row


def _parse_single_unit(label: str) -> str:
    m = re.findall(r'\(([^()]+)\)', label)
    if len(m) == 1:
        return m[0].strip()
    return ''


def compute_dataset_stats(ds: Dataset, flat_threshold: float = FLAT_THRESHOLD,
                          block_size: Optional[int] = None) -> List[Dict]:
    """Compute stats for every selected y column of a resolved dataset."""
    rows = []
    fp = Path(ds.path or ds.meta.file_path or '')
    x = ds.df_win[ds.x_col] if ds.x_col is not None else None
    y_unit = _parse_single_unit(ds.meta.y_label) if len(ds.y_cols) == 1 else ''
    for col in ds.y_cols:
        y = ds.df_win[col]
        r = compute_series_stats(
            x.values if x is not None else None,
            y.values, ds.kind, flat_threshold, block_size,
        )
        r.update({
            'dir': str(fp.parent) if str(fp.parent) else '.',
            'file': fp.name,
            'plot': col,
            'family': ds.family,
            'kind': ds.kind,
            'window_start': ds.window[0],
            'window_end': ds.window[1],
            'x_unit': ds.x_unit or '',
            'y_unit': y_unit,
        })
        rows.append(r)
    return rows


def generate_stats_csv(
    file_paths: List[str],
    output_path: str,
    opts: Optional[DatasetOptions] = None,
    flat_threshold: float = FLAT_THRESHOLD,
    block_size: Optional[int] = None,
    block_time: Optional[float] = None,
    ignore_series: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Read files, resolve datasets, and write a statistics CSV."""
    import re as _re
    ignore_res = [_re.compile(p) for p in (ignore_series or [])]

    all_rows: List[Dict] = []
    for fp in file_paths:
        if not os.path.exists(fp):
            continue
        df, meta = read_xvg(fp)
        if df.empty:
            continue
        # Per-file copy: mutating a shared options object would pin every later
        # row to the first file's label/path.
        label = os.path.basename(fp)
        o = replace(opts, label=label, path=fp) if opts else DatasetOptions(label=label, path=fp)
        ds = prepare_dataset(df, meta, o)
        bs = block_size
        if block_time is not None and bs is None and ds.x_col is not None:
            x = np.sort(ds.df_win[ds.x_col].astype(float).values)
            dx = np.diff(x)
            dx = dx[dx > 0]
            med_dx = float(np.median(dx)) if len(dx) else 1.0
            bs = max(BLOCK_MIN_SIZE, int(round(block_time / med_dx)))
        for row in compute_dataset_stats(ds, flat_threshold, bs):
            if any(rx.search(row['plot']) for rx in ignore_res):
                continue
            all_rows.append(row)

    if all_rows:
        stats_df = pd.DataFrame(all_rows, columns=CSV_COLUMNS)
        parent = os.path.dirname(output_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        stats_df.to_csv(output_path, index=False, float_format='%.6g')
    else:
        stats_df = pd.DataFrame(columns=CSV_COLUMNS)
    return stats_df


def format_stats_table(stats_df: pd.DataFrame, console: Optional[Console] = None) -> Table:
    console = console or Console()
    table = Table(title='XVG Statistics Summary')
    table.add_column('File', style='cyan')
    table.add_column('Plot', style='green')
    table.add_column('Kind', style='magenta')
    table.add_column('N', justify='right')
    table.add_column('Mean', justify='right')
    table.add_column('SD', justify='right')
    table.add_column('SEM', justify='right')
    table.add_column('|d|/SEM', justify='right')
    table.add_column('Flag', justify='right')

    def _fmt(v):
        if v is None or (isinstance(v, float) and (math.isnan(v) if v is not None else False)):
            return ''
        return f'{v:.4g}'

    for _, row in stats_df.iterrows():
        drift = row.get('drift_over_sem', None)
        table.add_row(
            str(row.get('file', '')),
            str(row.get('plot', '')),
            str(row.get('kind', '')),
            str(int(row.get('n', 0) or 0)),
            _fmt(row.get('mean')),
            _fmt(row.get('sd')),
            _fmt(row.get('sem')),
            _fmt(drift),
            str(row.get('flag', '')),
        )
    return table
