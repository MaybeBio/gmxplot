"""Parser: family/kind detection, column naming, time-unit detection."""

import numpy as np
import pytest

from gmxplot.parser import read_xvg


def _detect(title, xlabel, ylabel, n_cols=2):
    import os
    import tempfile
    fd, path = tempfile.mkstemp(suffix='.xvg')
    os.close(fd)
    data = [[i, float(i) * 0.1] for i in range(5)]
    with open(path, 'w') as f:
        f.write(f'@ title "{title}"\n@ xaxis label "{xlabel}"\n@ yaxis label "{ylabel}"\n')
        for row in data:
            f.write(' '.join(f'{float(v):.6g}' for v in row) + '\n')
    _, meta = read_xvg(path)
    os.unlink(path)
    return meta


@pytest.mark.parametrize('title,xlabel,ylabel,family,kind', [
    ('Hydrogen bond distribution', 'Distance (nm)', 'Count', 'hbond_dist', 'histogram'),
    ('Number of hydrogen bonds', 'Time (ps)', 'Number', 'hbond_num', 'timeseries'),
    ('Minimum distance', 'Time (ps)', 'Distance (nm)', 'mindist', 'timeseries'),
    ('Number of contacts', 'Time (ps)', 'Contacts', 'contacts', 'timeseries'),
    ('Eigenvalues of the covariance matrix', 'Eigenvalue index (1)', 'Eigenvalue', 'eigenvalue', 'spectrum'),
    ('Cluster size distribution', 'Cluster #', '# Structures', 'cluster_size', 'bar'),
    ('Secondary structure', 'Time (ps)', 'Structure', 'dssp', 'timeseries'),
    ('Solvent Accessible Surface', 'Residue', 'Area (nm\\S2\\N)', 'sasa', 'profile'),
    ('Solvent Accessible Surface', 'Time (ps)', 'Area (nm\\S2\\N)', 'sasa', 'timeseries'),
    ('Radius of gyration', 'Time (ps)', 'Rg (nm)', 'gyration', 'timeseries'),
    ('RMSD', 'Time (ps)', 'RMSD (nm)', 'rmsd', 'timeseries'),
    ('RMS fluctuation', 'Residue', 'RMSF (nm)', 'rmsf', 'profile'),
    ('2D projection of trajectory', 'PC1', 'PC2', 'pca', 'pca'),
])
def test_family_kind_detection(title, xlabel, ylabel, family, kind):
    meta = _detect(title, xlabel, ylabel)
    assert meta.family == family
    assert meta.kind == kind


def test_legend_column_names(tmp_xvg):
    p = tmp_xvg('e.xvg', 'GROMACS Energies', 'Time (ps)', '(K)',
                [[0, 300.0], [1, 301.0], [2, 302.0]],
                legends=['Temperature'])
    _, meta = read_xvg(p)
    assert meta.y_cols == ['Temperature']
    assert meta.primary_y_cols == ['Temperature']


def test_time_unit_detection(tmp_xvg):
    p = tmp_xvg('t.xvg', 'Energies', 'Time (ps)', '(K)', [[0, 1.0], [1, 2.0]])
    _, meta = read_xvg(p)
    assert meta.time_unit == 'ps'
    assert meta.x_is_time is True


def test_pca_has_no_x_column(tmp_xvg):
    data = [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]
    p = tmp_xvg('p.xvg', '2D projection of trajectory', 'PC1', 'PC2', data)
    _, meta = read_xvg(p)
    assert meta.x_col is None
    assert meta.y_cols == ['PC1', 'PC2']
