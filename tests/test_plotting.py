"""Palette resolution and per-column axis titles."""

import pytest

from gmxplot.dataset import DatasetOptions, prepare_dataset
from gmxplot.parser import read_xvg
from gmxplot.plotting import _y_titles, resolve_palette


def test_energy_units_follow_terms_not_position(tmp_xvg):
    # GROMACS merges repeated units in the y-axis label: 6 columns, 5 units.
    # The duplicate kJ/mol (Potential + Total Energy) must not shift the rest.
    p = tmp_xvg(
        'energy.xvg', 'GROMACS Energies', 'Time (ns)',
        '(kJ/mol), (K), (bar), (nm^3), (kg/m^3)',
        [[0, -1, -2, 300, 1, 10, 1000], [1, -1, -2, 301, 1, 10, 1001]],
        legends=['Potential', 'Total Energy', 'Temperature', 'Pressure',
                 'Volume', 'Density'])
    df, meta = read_xvg(p)
    ds = prepare_dataset(df, meta, DatasetOptions(path=p, label='e'))
    assert _y_titles(ds) == {
        'Potential': 'Potential (kJ/mol)',
        'Total Energy': 'Total Energy (kJ/mol)',
        'Temperature': 'Temperature (K)',
        'Pressure': 'Pressure (bar)',
        'Volume': 'Volume (nm^3)',
        'Density': 'Density (kg/m^3)',
    }


def test_single_unit_applies_to_all_columns(tmp_xvg):
    # gmx gyrate: four columns (Rg, Rgx, Rgy, Rgz) but one unit.
    p = tmp_xvg('rg.xvg', 'Radius of gyration', 'Time (ns)', 'Rg (nm)',
                [[0, 2.7, 1.5, 1.5, 1.4], [1, 2.8, 1.5, 1.5, 1.4]],
                legends=['Rg', 'Rgx', 'Rgy', 'Rgz'])
    df, meta = read_xvg(p)
    ds = prepare_dataset(df, meta, DatasetOptions(path=p, label='r'))
    titles = _y_titles(ds)
    assert titles['Rg'] == 'Rg (nm)'
    assert all(t.endswith('(nm)') for t in titles.values())


def test_palette_default_cycles_multicolors():
    colors = resolve_palette(None, 3)
    assert len(colors) == 3
    assert len(set(colors)) == 3  # distinct defaults


def test_palette_comma_list_cycles():
    colors = resolve_palette('#ff0000,#00ff00', 5)
    assert len(colors) == 5
    assert colors[0] == '#ff0000'
    assert colors[1] == '#00ff00'
    assert colors[2] == '#ff0000'  # wraps


def test_palette_named_seaborn():
    colors = resolve_palette('colorblind', 4)
    assert len(colors) == 4
    assert all(c.startswith('#') for c in colors)


def test_palette_unknown_raises():
    with pytest.raises(ValueError):
        resolve_palette('not_a_real_palette_name_xyz', 3)
