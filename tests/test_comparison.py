"""multi-compare overlay semantics."""

import matplotlib

matplotlib.use('Agg')

from gmxplot.comparison import compare_datasets
from gmxplot.dataset import DatasetOptions, prepare_dataset
from gmxplot.parser import read_xvg
from gmxplot.plotting import StyleOptions


def _load(paths):
    out = []
    for p in paths:
        df, meta = read_xvg(p)
        out.append(prepare_dataset(df, meta, DatasetOptions(label=p, path=p)))
    return out


def test_single_column_files_compare_by_position(tmp_xvg):
    # gmx mindist/contacts name the legend after the selection, so every file
    # has a different column name; all series must still be drawn.
    paths = [
        tmp_xvg(f'ZF{i}_DNA.xvg', 'Minimum Distance', 'Time (ns)', 'Distance (nm)',
                [[t, 0.2 + i] for t in (0, 1, 2)], legends=[f'ZF{i}-DNA'])
        for i in range(1, 4)
    ]
    datasets = _load(paths)
    assert [d.y_cols for d in datasets] == [['ZF1-DNA'], ['ZF2-DNA'], ['ZF3-DNA']]

    fig = compare_datasets(datasets, ['ZF1', 'ZF2', 'ZF3'], StyleOptions(no_raw=True))
    labels = [line.get_label() for line in fig.axes[0].lines]
    assert labels == ['ZF1', 'ZF2', 'ZF3']


def test_multi_column_files_still_match_by_name(tmp_xvg):
    paths = [
        tmp_xvg(f'r{i}.xvg', 'Energies', 'Time (ns)', '(kJ/mol)',
                [[t, 1.0 * i, 2.0 * i] for t in (0, 1, 2)],
                legends=['Potential', 'Kinetic'])
        for i in (1, 2)
    ]
    datasets = _load(paths)

    fig = compare_datasets(datasets, ['r1', 'r2'], StyleOptions(no_raw=True))
    assert len(fig.axes) == 2  # one panel per shared column
    for ax in fig.axes:
        assert len(ax.lines) == 2
