"""CLI smoke tests via Typer's CliRunner."""

import numpy as np
import pytest
from typer.testing import CliRunner

from gmxplot.cli import app

runner = CliRunner()


def _write_timeseries(tmp_path, name='t.xvg'):
    p = tmp_path / name
    p.write_text('@ title "Energies"\n@ xaxis label "Time (ps)"\n@ yaxis label "(K)"\n'
                 + ''.join(f'{i} {300 + (i % 7)}\n' for i in range(20)))
    return str(p)


def test_detect(tmp_path):
    p = _write_timeseries(tmp_path)
    result = runner.invoke(app, ['detect', p])
    assert result.exit_code == 0
    assert 'energy' in result.stdout


def test_plot_saves_png(tmp_path):
    p = _write_timeseries(tmp_path)
    out = tmp_path / 'out.png'
    result = runner.invoke(app, ['plot', p, '-o', str(out)])
    assert result.exit_code == 0
    assert out.exists()


def test_stats_csv(tmp_path):
    p = _write_timeseries(tmp_path)
    out = tmp_path / 'stats.csv'
    result = runner.invoke(app, ['stats', p, '-o', str(out)])
    assert result.exit_code == 0
    assert out.exists()
    assert 'mean' in out.read_text()


def test_replicas_requires_two_files(tmp_path):
    p = _write_timeseries(tmp_path)
    result = runner.invoke(app, ['replicas', p])
    assert result.exit_code == 1


def test_dashboard_renders(tmp_path):
    f1 = _write_timeseries(tmp_path, 'a.xvg')
    f2 = _write_timeseries(tmp_path, 'b.xvg')
    manifest = tmp_path / 'm.json'
    manifest.write_text(
        '{"title":"t","panels":[{"file":"%s","title":"A"}]}' % f1
    )
    out = tmp_path / 'dash.pdf'
    result = runner.invoke(app, ['dashboard', str(manifest), '-o', str(out)])
    assert result.exit_code == 0
    assert out.exists()


def test_plot_csv_resolved_data(tmp_path):
    p = _write_timeseries(tmp_path)
    out = tmp_path / 'data.csv'
    result = runner.invoke(app, ['plot', p, '-o', str(tmp_path / 'out.png'),
                                 '--csv', str(out)])
    assert result.exit_code == 0
    lines = out.read_text().strip().splitlines()
    header = lines[0]
    assert header.split(',')[0] == 'Time'  # x column first, then y columns
    assert 'mean' not in header  # resolved data, not a stats CSV
    assert len(header.split(',')) == 2
    assert len(lines) == 21  # header + 20 data rows


def test_batch_recursive_preserves_relative_path(tmp_path):
    sub = tmp_path / 'sub'
    sub.mkdir()
    (sub / 't.xvg').write_text(
        '@ title "Energies"\n@ xaxis label "Time (ps)"\n@ yaxis label "(K)"\n'
        + ''.join(f'{i} {300 + (i % 7)}\n' for i in range(20)))
    outdir = tmp_path / 'out'
    result = runner.invoke(app, ['batch', str(tmp_path), '-o', str(outdir),
                                 '--recursive', '--no-stats'])
    assert result.exit_code == 0
    assert (outdir / 'sub' / 't_plot.png').exists()
