"""Shared fixtures and synthetic-XVG builders for gmxplot tests."""

import os
import sys

import numpy as np
import pytest

# Ensure the package under test is importable when running pytest from anywhere.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def write_xvg(path, title, xlabel, ylabel, data, legends=None, header=None):
    """Write a synthetic XVG file.

    ``data`` is a 2D array-like of rows; the first column is x, the rest are y.
    ``legends`` is an optional list of y-column legend strings (0-indexed ``@ s0``).
    """
    lines = []
    if header:
        lines.append(header)
    lines.append(f'@ title "{title}"')
    lines.append(f'@ xaxis label "{xlabel}"')
    lines.append(f'@ yaxis label "{ylabel}"')
    if legends:
        for i, lg in enumerate(legends):
            lines.append(f'@ s{i} legend "{lg}"')
    for row in data:
        lines.append(' '.join(f'{float(v):.6g}' for v in row))
    with open(path, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    return path


@pytest.fixture
def tmp_xvg(tmp_path):
    def _write(name, title, xlabel, ylabel, data, legends=None, header=None):
        return write_xvg(str(tmp_path / name), title, xlabel, ylabel, data,
                         legends=legends, header=header)
    return _write
