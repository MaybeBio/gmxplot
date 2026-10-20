"""Dashboard: manifest validation, panel expansion, strict mode."""

import json

import pytest

from gmxplot.dashboard import _check_keys, GLOBAL_KEYS, PANEL_KEYS, _build_subpanels, _load_manifest


def test_check_keys_unknown_warns(monkeypatch, capsys):
    _check_keys({'bogus': 1}, GLOBAL_KEYS, strict=False, context='manifest')
    assert 'bogus' in capsys.readouterr().out


def test_check_keys_unknown_strict():
    with pytest.raises(ValueError):
        _check_keys({'bogus': 1}, GLOBAL_KEYS, strict=True, context='manifest')


def test_load_manifest_requires_panels(tmp_path):
    p = tmp_path / 'm.json'
    p.write_text(json.dumps({'title': 'x'}))
    with pytest.raises(ValueError):
        _load_manifest(str(p))


def test_build_single_panel(tmp_path):
    f = tmp_path / 't.xvg'
    f.write_text('@ title "Energies"\n@ xaxis label "Time (ps)"\n@ yaxis label "(K)"\n'
                 '@ s0 legend "Temperature"\n0 300\n1 310\n2 320\n')
    manifest = {}
    panel = {'file': str(f), 'title': 'Temp', 'kind': 'timeseries'}
    subs = _build_subpanels(manifest, panel)
    assert len(subs) == 1
    assert subs[0]['kind'] == 'single'
    assert subs[0]['col'] == 'Temperature'


def test_build_replica_panel_expands_columns(tmp_path):
    fs = []
    for i in range(2):
        f = tmp_path / f'e{i}.xvg'
        f.write_text('@ title "Energies"\n@ xaxis label "Time (ps)"\n@ yaxis label "(K)"\n'
                     '@ s0 legend "Temperature"\n0 300\n1 310\n2 320\n')
        fs.append(str(f))
    manifest = {}
    panel = {'files': fs, 'labels': ['r1', 'r2'], 'title': 'T'}
    subs = _build_subpanels(manifest, panel)
    assert len(subs) == 1
    assert subs[0]['kind'] == 'replicas'
    assert subs[0]['col'] == 'Temperature'
