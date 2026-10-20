"""Replica alignment: union / first / intersection, NaN handling."""

import numpy as np
import pytest

from gmxplot.dataset import DatasetOptions, prepare_dataset
from gmxplot.parser import read_xvg
from gmxplot.replicas import _align_grid, _replica_matrix


def _ds(tmp_xvg, name, xs):
    data = [[float(x), float(x)] for x in xs]
    p = tmp_xvg(name, 'Energies', 'Time (ps)', '(K)', data)
    df, meta = read_xvg(p)
    return prepare_dataset(df, meta, DatasetOptions(path=p, label=name,
                                                    normalize_time=False))


def test_align_union(tmp_xvg):
    d1 = _ds(tmp_xvg, 'a.xvg', [0, 1, 2, 3])
    d2 = _ds(tmp_xvg, 'b.xvg', [2, 3, 4, 5])
    g = _align_grid([d1, d2], 'union')
    assert list(g) == [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]


def test_align_intersection(tmp_xvg):
    d1 = _ds(tmp_xvg, 'a.xvg', [0, 1, 2, 3])
    d2 = _ds(tmp_xvg, 'b.xvg', [2, 3, 4, 5])
    g = _align_grid([d1, d2], 'intersection')
    assert list(g) == [2.0, 3.0]


def test_align_first(tmp_xvg):
    d1 = _ds(tmp_xvg, 'a.xvg', [0, 1, 2])
    d2 = _ds(tmp_xvg, 'b.xvg', [1, 2, 3, 4])
    g = _align_grid([d1, d2], 'first')
    assert list(g) == [0.0, 1.0, 2.0]


def test_matrix_nan_outside_support(tmp_xvg):
    d1 = _ds(tmp_xvg, 'a.xvg', [0, 1, 2])
    d2 = _ds(tmp_xvg, 'b.xvg', [1, 2, 3])
    grid = np.array([0.0, 1.0, 2.0, 3.0])
    mat = _replica_matrix(grid, [d1, d2], d1.y_cols[0], smooth=False)
    assert np.isnan(mat[0, 3])   # d1 has no x=3
    assert np.isnan(mat[1, 0])   # d2 has no x=0
    assert not np.isnan(mat[0, 1])
    assert not np.isnan(mat[1, 3])
