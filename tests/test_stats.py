"""Statistics: naive/block SEM, half-window drift, PCA, histogram weighting."""

import numpy as np
import pytest

from gmxplot.dataset import DatasetOptions, prepare_dataset
from gmxplot.parser import read_xvg
from gmxplot.stats import compute_series_stats, compute_dataset_stats


def test_naive_sem_exact():
    y = np.array([1.0, 2.0, 3.0, 4.0])
    r = compute_series_stats(np.arange(4.0), y, 'timeseries', block_size=None)
    assert r['n'] == 4
    assert np.isclose(r['mean'], 2.5)
    sd = np.std(y, ddof=1)
    assert np.isclose(r['sd'], sd)
    assert np.isclose(r['sem'], sd / np.sqrt(4))


def test_half_window_drift():
    # first half constant 1, second half constant 3 -> drift = 2
    x = np.arange(10.0)
    y = np.array([1.0] * 5 + [3.0] * 5)
    r = compute_series_stats(x, y, 'timeseries')
    assert np.isclose(r['mean_first_half'], 1.0)
    assert np.isclose(r['mean_second_half'], 3.0)
    assert np.isclose(r['drift'], 2.0)
    assert r['flag'] == 'DRIFT'  # zero within-group variance -> huge ratio


def test_flat_series_flag():
    y = np.full(50, 5.0)
    r = compute_series_stats(np.arange(50.0), y, 'timeseries')
    assert r['flag'] == 'flat'
    assert np.isclose(r['drift'], 0.0)


def test_block_sem_present():
    rng = np.random.default_rng(0)
    y = rng.normal(size=1000)
    r = compute_series_stats(np.arange(1000.0), y, 'timeseries')
    assert r['n_blocks'] > 1
    assert np.isfinite(r['sem_block'])
    assert r['sem_used'] >= r['sem']


def test_histogram_weighted_stats():
    x = np.array([0.0, 1.0, 2.0, 3.0])
    y = np.array([1.0, 4.0, 2.0, 1.0])  # mode at x=1
    r = compute_series_stats(x, y, 'histogram')
    assert np.isclose(r['x_mode'], 1.0)
    assert r['x_weighted_mean'] > 0.0
    assert r['n_eff'] > 0.0
    assert np.isfinite(r['sem_weighted'])


def test_pca_stats_both_columns(tmp_xvg):
    data = [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, 8.0]]
    p = tmp_xvg('p.xvg', '2D projection of trajectory', 'PC1', 'PC2', data)
    df, meta = read_xvg(p)
    ds = prepare_dataset(df, meta, DatasetOptions(path=p, label='p'))
    rows = compute_dataset_stats(ds)
    plots = sorted(r['plot'] for r in rows)
    assert plots == ['PC1', 'PC2']


def test_profile_no_drift_columns(tmp_xvg):
    data = [[float(i), float(i)] for i in range(10)]
    p = tmp_xvg('r.xvg', 'RMS fluctuation', 'Residue', 'RMSF (nm)', data)
    df, meta = read_xvg(p)
    ds = prepare_dataset(df, meta, DatasetOptions(path=p, label='r'))
    rows = compute_dataset_stats(ds)
    assert np.isnan(rows[0]['drift_over_sem'])
    assert rows[0]['kind'] == 'profile'
