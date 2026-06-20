"""GROMACS xmgrace escape code conversion for matplotlib."""

import re
from typing import Tuple

_GROMACS_FONT_RE = re.compile(r'\\f\{[^}]*\}')
_GROMACS_SUP_RE = re.compile(r'\\S(.*?)\\N')
_GROMACS_SUB_RE = re.compile(r'\\s(.*?)\\N')


def clean_gromacs_label(text: str) -> str:
    """Convert GROMACS xmgrace escape codes into matplotlib-compatible notation.

    - \\f{...} font switches -> removed
    - \\S...\\N superscript -> $^{...}$ (matplotlib mathtext/LaTeX)
    - \\s...\\N subscript -> $_{...}$ (matplotlib mathtext/LaTeX)
    """
    if not text:
        return text
    cleaned = _GROMACS_FONT_RE.sub('', text)
    cleaned = _GROMACS_SUP_RE.sub(r'$^{\1}$', cleaned)
    cleaned = _GROMACS_SUB_RE.sub(r'$_{\1}$', cleaned)
    return cleaned


# Per-type fallback axis titles
TYPE_FALLBACKS: dict[str, tuple[str, str]] = {
    'energy':   ('Time (ps)', ''),
    'gyration': ('Time (ps)', 'Rg (nm)'),
    'rmsd':     ('Time (ns)', 'RMSD (nm)'),
    'rmsf':     ('Residue', 'RMSF (nm)'),
    'sasa':     ('Time (ns)', 'Area (nm$^{2}$)'),
    'pca':      ('PC1', 'PC2'),
    'xy':       ('X', 'Y'),
}


def resolve_axis_titles(
    metadata,
    fallback_x: str = '',
    fallback_y: str = '',
) -> Tuple[str, str]:
    """Return (x_title, y_title) preferring metadata, cleaned of GROMACS codes.

    Uses TYPE_FALLBACKS when no fallback is explicitly provided.
    """
    if not fallback_x and metadata.plot_type in TYPE_FALLBACKS:
        fallback_x = TYPE_FALLBACKS[metadata.plot_type][0]
    if not fallback_y and metadata.plot_type in TYPE_FALLBACKS:
        fallback_y = TYPE_FALLBACKS[metadata.plot_type][1]

    x_title = clean_gromacs_label(metadata.x_label) if metadata.x_label else fallback_x
    y_title = clean_gromacs_label(metadata.y_label) if metadata.y_label else fallback_y
    return x_title, y_title
