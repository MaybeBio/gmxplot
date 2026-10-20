"""XVG file parsing, column naming, and family/kind classification."""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import pandas as pd

from .config import CANONICAL_Y_COLUMNS, KINDS, TIME_UNITS


@dataclass
class XVGMetadata:
    """Metadata extracted from an XVG file header."""

    title: str = ''
    subtitle: str = ''
    x_label: str = ''
    y_label: str = ''
    # family: semantic content (energy, rmsd, hbond_dist, ...)
    family: str = 'unknown'
    # kind: rendering/statistics semantics (timeseries, histogram, ...)
    kind: str = 'xy'
    x_unit: str = ''
    y_unit: str = ''
    time_unit: str = ''          # detected from x axis label, e.g. 'ps'
    x_is_time: bool = False
    legend_labels: List[str] = field(default_factory=list)
    n_columns: int = 0
    file_path: str = ''
    command: str = ''
    gmx_version: str = ''
    # x_col: name of the x column (None for PCA, which has no x column)
    x_col: Optional[str] = None
    y_cols: List[str] = field(default_factory=list)
    primary_y_cols: List[str] = field(default_factory=list)
    df: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def plot_type(self) -> str:
        """Backward-compatible alias for family."""
        return self.family


def read_xvg(file_path: str) -> Tuple[pd.DataFrame, XVGMetadata]:
    """Read an XVG file and return (DataFrame, XVGMetadata)."""
    metadata = XVGMetadata(file_path=file_path)
    title = subtitle = x_label = y_label = ''
    legend_labels = {}
    command = ''
    gmx_version = ''
    data_lines: List[str] = []

    with open(file_path, 'r') as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            if s.startswith('#'):
                m = re.search(r'GROMACS(?: - gmx (\w+))?,?\s*(\d+)', s)
                if m:
                    command = m.group(1) or command
                    gmx_version = m.group(2)
                continue
            if s.startswith('@'):
                directive = s[1:].strip()
                if directive.startswith('title'):
                    m = re.search(r'"([^"]*)"', s)
                    if m:
                        title = m.group(1)
                elif directive.startswith('subtitle'):
                    m = re.search(r'"([^"]*)"', s)
                    if m:
                        subtitle = m.group(1)
                elif re.match(r'^xaxis\s+label\s*', directive):
                    m = re.search(r'"([^"]*)"', s)
                    if m:
                        x_label = m.group(1)
                elif re.match(r'^yaxis\s+label\s*', directive):
                    m = re.search(r'"([^"]*)"', s)
                    if m:
                        y_label = m.group(1)
                elif re.match(r's\d+\s+legend', directive):
                    m = re.search(r's(\d+)\s+legend\s+"([^"]+)"', s)
                    if m:
                        legend_labels[int(m.group(1))] = m.group(2)
                elif 'command' in directive.lower() and 'gmx' in s:
                    m = re.search(r'gmx (\w+)', s)
                    if m:
                        command = m.group(1)
                continue
            # numeric data line
            if s.startswith(('&', '#')):
                continue
            parts = s.split()
            if len(parts) >= 2:
                try:
                    float(parts[0])
                    float(parts[1])
                    data_lines.append(s)
                except ValueError:
                    continue

    metadata.title = title
    metadata.subtitle = subtitle
    metadata.x_label = x_label
    metadata.y_label = y_label
    metadata.command = command
    metadata.gmx_version = gmx_version

    if not data_lines:
        metadata.df = pd.DataFrame()
        return metadata.df, metadata

    n_cols = len(data_lines[0].split())
    metadata.n_columns = n_cols
    metadata.legend_labels = [legend_labels.get(i, f'Col{i}') for i in range(n_cols - 1)]

    family = _detect_family(title, x_label, y_label, n_cols)
    metadata.family = family

    columns = _name_columns(family, n_cols, metadata.legend_labels, x_label, title)
    parsed = []
    for line in data_lines:
        parsed.append([float(v) for v in line.split()])
    df = pd.DataFrame(parsed, columns=columns)

    # Determine x/y columns.
    if family == 'pca':
        metadata.x_col = None
        metadata.y_cols = [c for c in columns]
        metadata.primary_y_cols = [c for c in columns[:2]]
    else:
        metadata.x_col = columns[0]
        metadata.y_cols = columns[1:]
        metadata.primary_y_cols = _primary_y_cols(family, metadata.y_cols)

    metadata.time_unit = _detect_time_unit(x_label)
    metadata.x_is_time = _x_is_time(family, x_label)
    metadata.kind = _detect_kind(family, x_label, y_label, n_cols)
    metadata.df = df

    return df, metadata


# --------------------------------------------------------------------------
# family detection
# --------------------------------------------------------------------------

def _detect_family(title: str, x_label: str, y_label: str, n_cols: int) -> str:
    """Classify the semantic family from title (primary) and axis labels (fallback)."""
    t = title.lower()
    # Ordered by specificity: put longer / more specific patterns first.
    title_rules = [
        ('2d projection', 'pca'),
        ('projection of trajectory', 'pca'),
        ('solvent accessible surface', 'sasa'),
        ('area per residue', 'sasa'),
        ('sasa', 'sasa'),
        ('rms fluctuation', 'rmsf'),
        ('rmsf', 'rmsf'),
        ('hydrogen bond distribution', 'hbond_dist'),
        ('hbond distribution', 'hbond_dist'),
        ('number of hydrogen bonds', 'hbond_num'),
        ('hydrogen bonds', 'hbond_num'),
        ('minimum distance', 'mindist'),
        ('number of contacts', 'contacts'),
        ('contacts', 'contacts'),
        ('eigenvalues of the covariance', 'eigenvalue'),
        ('eigenvalue', 'eigenvalue'),
        ('cluster size', 'cluster_size'),
        ('secondary structure', 'dssp'),
        ('radius of gyration', 'gyration'),
        ('gyration', 'gyration'),
        ('energies', 'energy'),
        ('energy', 'energy'),
        ('rmsd', 'rmsd'),
    ]
    for pattern, family in title_rules:
        if pattern in t:
            return family

    x = x_label.lower()
    y = y_label.lower()
    if n_cols >= 4 and 'time' in x and any(k in y for k in ['kj/mol', '(k)', '(bar)', 'kg/m']):
        return 'energy'
    if 'eigenvector' in x or 'projection' in x:
        return 'pca'
    if 'fluctuation' in y or 'rmsf' in y:
        return 'rmsf'
    if 'rmsd' in y:
        return 'rmsd'
    if 'radius of gyration' in y or re.search(r'\brg\b', y):
        return 'gyration'
    if 'area' in y and 'nm' in y:
        return 'sasa'
    if 'hydrogen bond' in y:
        return 'hbond_num'
    if 'distance' in x and 'count' in y:
        return 'hbond_dist'
    if 'eigenvalue' in x or 'eigenvalue' in y:
        return 'eigenvalue'
    if 'cluster' in x:
        return 'cluster_size'
    return 'generic'


def _detect_kind(family: str, x_label: str, y_label: str, n_cols: int) -> str:
    """Map family + axis labels to a rendering/statistics kind."""
    x = x_label.lower()
    if family == 'pca':
        return 'pca'
    if family == 'hbond_dist':
        return 'histogram'
    if family == 'eigenvalue':
        return 'spectrum'
    if family == 'cluster_size':
        return 'bar'
    if family == 'rmsf':
        return 'profile'
    if family == 'sasa':
        return 'profile' if ('residue' in x or 'atom' in x) else 'timeseries'
    if family in ('generic', 'unknown'):
        if 'time' in x:
            return 'timeseries'
        if 'residue' in x or 'atom' in x:
            return 'profile'
        if 'distance' in x and 'count' in y_label.lower():
            return 'histogram'
        if 'eigenvalue' in x:
            return 'spectrum'
        if 'cluster' in x:
            return 'bar'
        return 'xy'
    # energy, rmsd, gyration, mindist, contacts, hbond_num, dssp, sasa(time)
    return 'timeseries'


def _detect_time_unit(x_label: str) -> str:
    m = re.search(r'time\s*\(\s*([a-zA-Zµμ]+)', x_label, re.IGNORECASE)
    if not m:
        return ''
    unit = m.group(1).lower().replace('µ', 'u').replace('μ', 'u')
    return unit if unit in TIME_UNITS else ''


def _x_is_time(family: str, x_label: str) -> bool:
    return 'time' in x_label.lower() or family in (
        'energy', 'rmsd', 'gyration', 'mindist', 'contacts', 'hbond_num', 'dssp'
    )


# --------------------------------------------------------------------------
# column naming
# --------------------------------------------------------------------------

def _infer_x_col(x_label: str, title: str, family: str) -> str:
    x = x_label.lower()
    if 'time' in x:
        return 'Time'
    if 'step' in x:
        return 'Step'
    if 'residue' in x:
        return 'Residue'
    if 'atom' in x:
        return 'Atom'
    if 'distance' in x:
        return 'Distance'
    if 'eigenvalue' in x:
        return 'EigenvalueIndex'
    if 'cluster' in x:
        return 'Cluster'
    if 'bin' in x:
        return 'Bin'
    if 'projection' in x:
        return 'PC1'
    return 'X'


def _name_columns(family: str, n_cols: int, legends: List[str], x_label: str, title: str) -> List[str]:
    if family == 'pca':
        return [f'PC{i}' for i in range(1, n_cols + 1)]

    x_col = _infer_x_col(x_label, title, family)
    n_y = n_cols - 1
    if legends and len(legends) == n_y:
        y_cols = legends
    else:
        defaults = CANONICAL_Y_COLUMNS.get(family, [])
        if len(defaults) >= n_y:
            y_cols = defaults[:n_y]
        else:
            y_cols = defaults + [f'Y{i}' for i in range(len(defaults) + 1, n_y + 1)]
    return [x_col] + y_cols


def _primary_y_cols(family: str, y_cols: List[str]) -> List[str]:
    from .config import PRIMARY_Y_COLUMNS
    want = PRIMARY_Y_COLUMNS.get(family)
    if not want:
        return list(y_cols)
    want_lower = [w.lower() for w in want]
    result = []
    for c in y_cols:
        if c.lower() in want_lower:
            result.append(c)
    return result or list(y_cols)
