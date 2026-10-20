"""Palette resolution for multi-series coloring."""

import pytest

from gmxplot.plotting import resolve_palette


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
