"""Dataset resolution: columns, time normalization, windowing, rolling."""

import numpy as np
import pytest

from gmxplot.dataset import DatasetOptions, prepare_dataset, resolve_roll_samples
from gmxplot.parser import read_xvg


def _prepare(tmp_xvg, name, title, xlabel, ylabel, data, legends=None, **opts):
    p = tmp_xvg(name, title, xlabel, ylabel, data, legends=legends)
    df, meta = read_xvg(p)
    o = DatasetOptions(path=p, label=name, **opts)
    return prepare_dataset(df, meta, o)


def test_time_normalization_ps_to_ns(tmp_xvg):
    data = [[0.0, 300.0], [1000.0, 310.0]]  # ps
    ds = _prepare(tmp_xvg, 't.xvg', 'Energies', 'Time (ps)', '(K)', data)
    assert ds.x_unit == 'ns'
    assert np.isclose(ds.df['Time'].iloc[-1], 1.0)  # 1000 ps -> 1 ns


def test_no_time_normalize(tmp_xvg):
    data = [[0.0, 300.0], [1000.0, 310.0]]
    ds = _prepare(tmp_xvg, 't.xvg', 'Energies', 'Time (ps)', '(K)', data,
                  normalize_time=False)
    assert np.isclose(ds.df['Time'].iloc[-1], 1000.0)


def test_window_start_end(tmp_xvg):
    data = [[float(i), float(i)] for i in range(10)]
    ds = _prepare(tmp_xvg, 't.xvg', 'Energies', 'Time (ps)', '(K)', data,
                  normalize_time=False, start=3.0, end=6.0)
    assert len(ds.df_win) == 4  # 3,4,5,6
    assert ds.window == (3.0, 6.0)


def test_y_col_index_and_name(tmp_xvg):
    data = [[i, i * 1.0, i * 2.0] for i in range(5)]
    ds = _prepare(tmp_xvg, 'e.xvg', 'Energies', 'Time (ps)', '(K)',
                  data, legends=['A', 'B'], y_cols=['B'])
    assert ds.y_cols == ['B']
    # 1-based index into the full column list (Time=1, A=2, B=3)
    ds2 = _prepare(tmp_xvg, 'e.xvg', 'Energies', 'Time (ps)', '(K)',
                   data, legends=['A', 'B'], y_cols=['2'])
    assert ds2.y_cols == ['A']
    ds3 = _prepare(tmp_xvg, 'e.xvg', 'Energies', 'Time (ps)', '(K)',
                   data, legends=['A', 'B'], y_cols=['3'])
    assert ds3.y_cols == ['B']


def test_roll_samples_zero_for_non_timeseries(tmp_xvg):
    data = [[float(i), float(i)] for i in range(50)]
    ds = _prepare(tmp_xvg, 'h.xvg', 'Hydrogen bond distribution', 'Distance (nm)',
                  'Count', data)
    assert ds.kind == 'histogram'
    assert ds.roll_samples == 0


def test_roll_window_conversion(tmp_xvg):
    # 0..200 ps -> ns; median dx = 1 ps = 0.001 ns
    data = [[float(i) * 1.0, 300.0 + i] for i in range(201)]
    ds = _prepare(tmp_xvg, 't.xvg', 'Energies', 'Time (ps)', '(K)', data,
                  roll_window=1.0)  # 1 ns window
    assert ds.roll_samples > 0


def test_roll_samples_override(tmp_xvg):
    data = [[float(i), float(i)] for i in range(200)]
    ds = _prepare(tmp_xvg, 't.xvg', 'Energies', 'Time (ps)', '(K)', data,
                  roll_samples=10)
    assert ds.roll_samples == 10


def test_no_roll(tmp_xvg):
    data = [[float(i), float(i)] for i in range(200)]
    ds = _prepare(tmp_xvg, 't.xvg', 'Energies', 'Time (ps)', '(K)', data,
                  no_roll=True)
    assert ds.roll_samples == 0
