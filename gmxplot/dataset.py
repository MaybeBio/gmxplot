"""Dataset resolution: columns, time normalization, windowing, rolling."""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from .config import (
    FAMILIES, KINDS, TIME_TO_NS, ROLL_MIN, ROLL_MAX_SAMPLES,
    ROLL_MAX_FRACTION_OF_N, ROLL_FRACTION_TIME,
)
from .parser import XVGMetadata, _detect_kind


@dataclass
class DatasetOptions:
    """All user overrides that affect how a single file is resolved."""

    kind: Optional[str] = None          # --kind
    family: Optional[str] = None        # --type
    x_col: Optional[str] = None         # --x-col
    y_cols: Optional[List[str]] = None  # --y-col (repeatable)
    all_cols: bool = False              # --all-cols
    time_unit: str = 'auto'             # --time-unit
    normalize_time: bool = True         # --no-time-normalize
    start: Optional[float] = None       # --start
    end: Optional[float] = None         # --end
    t_eq: Optional[float] = None        # --t-eq
    plot_full: bool = False             # --plot-full
    roll_samples: Optional[int] = None  # --roll-samples / --roll-avg
    roll_window: Optional[float] = None  # --roll-window
    roll_fraction: Optional[float] = None  # --roll-fraction
    no_roll: bool = False               # --no-roll
    label: str = ''                     # display label
    path: str = ''                      # source path


@dataclass
class Dataset:
    """A resolved, normalized, windowed XVG dataset ready for plotting/stats."""

    df: pd.DataFrame            # full, time-normalized
    df_win: pd.DataFrame        # statistics window
    df_plot: pd.DataFrame       # plotted data (full if plot_full, else window)
    meta: XVGMetadata
    family: str
    kind: str
    x_col: Optional[str]
    y_cols: List[str]
    x_is_time: bool
    time_unit: str              # 'ns' if normalized, else the input unit
    x_unit: str                 # unit of the x axis ('ns' when normalized)
    window: Tuple[Optional[float], Optional[float]]
    t_eq: Optional[float]
    plot_full: bool
    roll_samples: int
    label: str
    path: str

    @property
    def x(self) -> pd.Series:
        if self.x_col is None:
            raise ValueError('this dataset has no x column (PCA)')
        return self.df_plot[self.x_col]

    @property
    def x_win(self) -> pd.Series:
        if self.x_col is None:
            raise ValueError('this dataset has no x column (PCA)')
        return self.df_win[self.x_col]

    def y(self, col: str) -> pd.Series:
        return self.df_plot[col]


def resolve_family_kind(
    meta: XVGMetadata,
    family_override: Optional[str] = None,
    kind_override: Optional[str] = None,
) -> Tuple[str, str]:
    """Resolve (family, kind) honoring --type / --kind overrides.

    Precedence: --kind > --type-derived kind > auto-detected.
    """
    family = meta.family
    kind = meta.kind

    if family_override:
        f = family_override.lower()
        if f in FAMILIES:
            family = f
        elif f in KINDS:
            kind = f
        else:
            raise ValueError(
                f'unknown --type value {family_override!r}; '
                f'expected a family ({", ".join(FAMILIES)}) or a kind ({", ".join(KINDS)})'
            )

    if kind_override:
        k = kind_override.lower()
        if k not in KINDS:
            raise ValueError(
                f'unknown --kind value {kind_override!r}; '
                f'expected one of {", ".join(KINDS)}'
            )
        kind = k
    elif family_override and family_override.lower() in FAMILIES:
        # Family changed explicitly and kind not forced: recompute kind.
        kind = _detect_kind(family, meta.x_label, meta.y_label, meta.n_columns)

    return family, kind


def _pick_col(columns: List[str], spec: Optional[str], default: Optional[str]) -> Optional[str]:
    if spec is None:
        return default
    s = str(spec)
    # exact match (case-insensitive)
    for c in columns:
        if c.lower() == s.lower():
            return c
    if s.isdigit():
        idx = int(s) - 1
        if 0 <= idx < len(columns):
            return columns[idx]
        raise ValueError(f'column index {s} out of range (1..{len(columns)})')
    raise ValueError(
        f'column {spec!r} not found; available columns: {", ".join(columns)}'
    )


def resolve_columns(
    df: pd.DataFrame,
    meta: XVGMetadata,
    family: str,
    x_col: Optional[str],
    y_cols: Optional[List[str]],
    all_cols: bool,
) -> Tuple[Optional[str], List[str]]:
    columns = list(df.columns)

    if family == 'pca':
        if y_cols:
            y = [_pick_col(columns, c, None) for c in y_cols]
        else:
            y = list(columns)
        return None, y

    x = _pick_col(columns, x_col, meta.x_col)
    avail_y = [c for c in columns if c != x]

    if y_cols:
        y = [_pick_col(columns, c, None) for c in y_cols]
    elif all_cols:
        y = avail_y
    else:
        prim = [c for c in meta.primary_y_cols if c in avail_y]
        y = prim if prim else avail_y

    if x in y:
        y = [c for c in y if c != x]
    if not y:
        y = avail_y
    return x, y


def _relabel_time(meta: XVGMetadata, unit: str) -> None:
    if not meta.x_is_time:
        return
    new = re.sub(r'\(\s*[a-zA-Zµμ]+\s*\)', f'({unit})', meta.x_label)
    if new == meta.x_label and '(' not in new:
        new = f'Time ({unit})'
    meta.x_label = new


def normalize_time(df: pd.DataFrame, meta: XVGMetadata,
                   input_unit: str = 'auto', normalize: bool = True) -> pd.DataFrame:
    """Convert the x column to ns when it is a time axis."""
    if not meta.x_is_time:
        meta.x_unit = meta.time_unit or ''
        return df

    unit = input_unit if input_unit != 'auto' else (meta.time_unit or 'ns')
    unit = unit or 'ns'
    if not normalize:
        meta.x_unit = unit
        meta.time_unit = unit
        return df

    factor = TIME_TO_NS.get(unit, 1.0)
    if factor != 1.0:
        df = df.copy()
        df[meta.x_col] = df[meta.x_col].astype(float) * factor
    meta.x_unit = 'ns'
    meta.time_unit = 'ns'
    _relabel_time(meta, 'ns')
    return df


def apply_window(df: pd.DataFrame, meta: XVGMetadata,
                 start: Optional[float], end: Optional[float],
                 t_eq: Optional[float], plot_full: bool) -> Tuple[pd.DataFrame, pd.DataFrame, Tuple]:
    """Return (df_win, df_plot, (window_start, window_end))."""
    if meta.x_col is None:
        return df, df, (start, end)

    xvals = df[meta.x_col].astype(float)
    stats_start = start if start is not None else (t_eq if meta.x_is_time else None)
    lo = stats_start
    hi = end
    mask = np.ones(len(df), dtype=bool)
    if lo is not None:
        mask &= xvals >= lo
    if hi is not None:
        mask &= xvals <= hi

    df_win = df[mask].reset_index(drop=True)
    df_plot = df if plot_full else df_win
    return df_win, df_plot, (lo, hi)


def resolve_roll_samples(xvals: pd.Series, kind: str,
                         roll_samples: Optional[int] = None,
                         roll_window: Optional[float] = None,
                         roll_fraction: Optional[float] = None,
                         no_roll: bool = False) -> int:
    """Resolve the rolling-average window in samples (0 = no smoothing)."""
    if no_roll or kind != 'timeseries':
        return 0
    n = len(xvals)
    if n < 2 * ROLL_MIN:
        return 0

    if roll_samples is not None:
        s = int(roll_samples)
    else:
        x = np.asarray(xvals, dtype=float)
        x = np.sort(x)
        dx = np.diff(x)
        dx = dx[dx > 0]
        med_dx = float(np.median(dx)) if len(dx) else 1.0
        if roll_window is not None:
            s = int(round(roll_window / med_dx))
        else:
            frac = roll_fraction if roll_fraction is not None else ROLL_FRACTION_TIME
            span = float(x.max() - x.min())
            s = int(round(frac * span / med_dx))

    if s < ROLL_MIN:
        return 0
    s = min(ROLL_MAX_SAMPLES, int(n * ROLL_MAX_FRACTION_OF_N), s)
    return int(s) if s >= ROLL_MIN else 0


def prepare_dataset(df: pd.DataFrame, meta: XVGMetadata,
                    opts: Optional[DatasetOptions] = None) -> Dataset:
    """Resolve a single XVG into a ready-to-use Dataset."""
    opts = opts or DatasetOptions()

    family, kind = resolve_family_kind(meta, opts.family, opts.kind)

    df = normalize_time(df, meta, opts.time_unit, opts.normalize_time)

    x_col, y_cols = resolve_columns(df, meta, family, opts.x_col, opts.y_cols, opts.all_cols)

    df_win, df_plot, window = apply_window(df, meta, opts.start, opts.end, opts.t_eq, opts.plot_full)

    if x_col is not None:
        roll_samples = resolve_roll_samples(
            df_plot[x_col], kind, opts.roll_samples, opts.roll_window,
            opts.roll_fraction, opts.no_roll,
        )
    else:
        roll_samples = 0

    return Dataset(
        df=df,
        df_win=df_win,
        df_plot=df_plot,
        meta=meta,
        family=family,
        kind=kind,
        x_col=x_col,
        y_cols=y_cols,
        x_is_time=meta.x_is_time,
        time_unit=meta.time_unit,
        x_unit=meta.x_unit,
        window=window,
        t_eq=opts.t_eq,
        plot_full=opts.plot_full,
        roll_samples=roll_samples,
        label=opts.label,
        path=opts.path,
    )
