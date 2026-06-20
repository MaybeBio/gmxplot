"""XVG file parsing and plot type classification."""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import pandas as pd


@dataclass
class XVGMetadata:
    """Metadata extracted from an XVG file header."""
    title: str = ''
    subtitle: str = ''
    x_label: str = ''
    y_label: str = ''
    plot_type: str = ''  # energy, gyration, rmsd, rmsf, sasa, pca, xy, unknown
    x_unit: str = ''
    y_unit: str = ''
    legend_labels: List[str] = field(default_factory=list)
    n_columns: int = 0
    file_path: str = ''
    command: str = ''  # Original GROMACS command (e.g., rms, gyrate)
    gmx_version: str = ''


def read_xvg(file_path: str) -> Tuple[pd.DataFrame, XVGMetadata]:
    """Read an XVG file and return (DataFrame, XVGMetadata)."""
    metadata = XVGMetadata(file_path=file_path)
    data_lines: List[str] = []
    legend_labels: dict = {}
    command = ''
    gmx_version = ''

    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # Comment lines — extract GROMACS version info
            if line.startswith('#'):
                if 'GROMACS' in line:
                    m = re.search(r'GROMACS(?: - gmx (\w+))?,?\s*(\d+)', line)
                    if m:
                        command = m.group(1) or command
                        gmx_version = m.group(2)
                continue

            # @ directives
            if line.startswith('@'):
                directive = line[1:].strip()

                # Title
                if directive.startswith('title'):
                    m = re.search(r'"([^"]*)"', line)
                    if m:
                        metadata.title = m.group(1)

                # Subtitle
                elif directive.startswith('subtitle'):
                    m = re.search(r'"([^"]*)"', line)
                    if m:
                        metadata.subtitle = m.group(1)

                # X axis label (handle variable spacing)
                elif re.match(r'^xaxis\s+label\s*', directive):
                    m = re.search(r'"([^"]*)"', line)
                    if m:
                        metadata.x_label = m.group(1)

                # Y axis label
                elif re.match(r'^yaxis\s+label\s*', directive):
                    m = re.search(r'"([^"]*)"', line)
                    if m:
                        metadata.y_label = m.group(1)

                # Legend labels (s0, s1, etc.)
                elif re.match(r's\d+\s+legend', directive):
                    m = re.search(r's(\d+)\s+legend\s+"([^"]+)"', line)
                    if m:
                        legend_labels[int(m.group(1))] = m.group(2)

                # Command line info
                elif 'command' in directive.lower() and 'gmx' in line:
                    m = re.search(r'gmx (\w+)', line)
                    if m:
                        command = m.group(1)

                continue

            # Numeric data lines — skip &, @, #
            if line.startswith(('&', '#', '@')):
                continue

            parts = line.split()
            if len(parts) >= 2:
                try:
                    float(parts[0])
                    float(parts[1])
                    data_lines.append(line)
                except ValueError:
                    continue

    metadata.command = command
    metadata.gmx_version = gmx_version
    metadata.legend_labels = [
        legend_labels.get(i, f'Col{i}') for i in range(len(legend_labels))
    ]

    # Parse numeric data
    if data_lines:
        metadata = _parse_data_to_dataframe(data_lines, metadata)

    # Classify plot type
    metadata.plot_type = _classify_plot_type(metadata)

    if not hasattr(metadata, 'df') or metadata.df is None:
        metadata.df = pd.DataFrame()

    return metadata.df, metadata


def _parse_data_to_dataframe(
    data_lines: List[str], metadata: XVGMetadata
) -> XVGMetadata:
    """Parse data lines into DataFrame with intelligent column naming."""
    parsed = []
    for line in data_lines:
        parts = re.split(r'[,\s\t]+', line)
        parsed.append([p for p in parts if p])

    if not parsed:
        metadata.df = pd.DataFrame()
        return metadata

    num_cols = len(parsed[0])
    metadata.n_columns = num_cols
    title_lower = metadata.title.lower()
    x_label_lower = metadata.x_label.lower()

    if num_cols >= 2:
        columns: List[str] = ['X'] + [f'Y{i}' for i in range(1, num_cols)]

    # --- X column naming ---
    if 'time' in x_label_lower or 'time' in title_lower:
        columns[0] = 'Time'
    elif 'step' in x_label_lower:
        columns[0] = 'Step'
    elif 'residue' in x_label_lower or 'residue' in title_lower:
        columns[0] = 'Residue'
    elif 'atom' in x_label_lower:
        columns[0] = 'Atom'
    elif 'eigen' in x_label_lower:
        columns[0] = 'Eigenvalue'
    elif 'projection' in x_label_lower:
        columns[0] = 'PC1'
        columns[1] = 'PC2'

    # --- Y column naming ---
    if 'potential' in title_lower or 'energ' in title_lower:
        if metadata.legend_labels and len(metadata.legend_labels) >= num_cols - 1:
            columns = ['Time'] + metadata.legend_labels[:num_cols - 1]
        else:
            defaults = ['Potential', 'Temperature', 'Pressure', 'Density']
            columns = ['Time'] + defaults[:num_cols - 1]

    elif 'gyration' in title_lower or re.search(r'\brg\b', title_lower):
        if num_cols >= 4:
            columns = ['Time', 'Rg', 'RgX', 'RgY', 'RgZ']
        else:
            columns = ['Time', 'Rg']

    elif ('area' in metadata.y_label.lower()
          or 'sasa' in title_lower
          or 'solvent' in title_lower):
        if 'time' in x_label_lower:
            columns = ['Time', 'Area', 'StdDev'][:num_cols]
        else:
            columns = ['Residue', 'Area', 'StdDev'][:num_cols]

    elif 'rmsd' in title_lower or 'rmsd' in metadata.y_label.lower():
        columns = ['Time', 'RMSD']

    elif 'rmsf' in title_lower or 'fluctuation' in title_lower:
        columns = ['Residue', 'RMSF']

    elif 'pca' in title_lower or 'projection' in title_lower:
        columns = ['PC1', 'PC2']

    # Build DataFrame
    df = pd.DataFrame(parsed, columns=columns[:num_cols])
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    metadata.df = df
    return metadata


def _classify_plot_type(metadata: XVGMetadata) -> str:
    """Classify plot type from title (primary) and axis labels / column count (fallback)."""
    title = metadata.title.lower()

    # ── Title-based detection ────────────────────────────────────────
    title_rules: List[Tuple[str, str]] = [
        ('2d projection', 'pca'),
        ('projection of trajectory', 'pca'),
        ('energies', 'energy'),
        ('energy', 'energy'),
        ('solvent accessible surface', 'sasa'),
        ('area per residue', 'sasa'),
        ('sasa', 'sasa'),
        ('rms fluctuation', 'rmsf'),
        ('rmsf', 'rmsf'),
        ('rmsd', 'rmsd'),
        ('radius of gyration', 'gyration'),
        ('gyration', 'gyration'),
    ]

    for pattern, plot_type in title_rules:
        if pattern in title:
            return plot_type

    # ── Fallback heuristics ─────────────────────────────────────────
    x_label = metadata.x_label.lower()
    y_label = metadata.y_label.lower()
    n_cols = metadata.n_columns

    if n_cols >= 4 and 'time' in x_label:
        if any(kw in y_label for kw in ['kj/mol', '(k)', '(bar)', 'kg/m']):
            return 'energy'
    if 'eigenvector' in x_label and 'eigenvector' in y_label:
        return 'pca'
    if 'fluctuation' in y_label or 'rmsf' in y_label:
        return 'rmsf'
    if 'residue' in x_label and 'rmsf' in y_label:
        return 'rmsf'
    if 'rmsd' in y_label:
        return 'rmsd'
    if 'radius of gyration' in y_label or re.search(r'\brg\b', y_label):
        return 'gyration'
    if 'area' in y_label and 'nm' in y_label:
        return 'sasa'
    if n_cols >= 2:
        return 'xy'

    return 'unknown'