"""Default configuration constants for gmxplot."""

# Figure defaults
FIGURE_SIZE_SINGLE = (10, 6)
FIGURE_SIZE_MULTI_ROW_HEIGHT = 4  # inches per row for multi-panel
DPI_DEFAULT = 300

# Line styling
LINE_WIDTH_RAW = 1.0
LINE_WIDTH_RA = 1.5
RAW_ALPHA = 0.5

# Colors
RA_COLOR = '#1f77b4'
RAW_COLOR = '#aec6cf'
COMPARE_COLORS = ('#1f77b4', '#d62728')

# Multi-file color palette (tab10)
MULTI_COLORS = [
    '#1f77b4', '#d62728', '#2ca02c', '#9467bd',
    '#ff7f0e', '#8c564b', '#e377c2', '#7f7f7f',
    '#bcbd22', '#17becf',
]

# Rolling average
ROLL_AVG_DEFAULT_PLOT = None  # None = auto-calculate
ROLL_AVG_DEFAULT_COMPARE = 50
ROLL_AVG_MIN = 3
ROLL_AVG_MAX = 100
ROLL_AVG_FRACTION = 0.05  # 5% of data range

# Plot type names
PLOT_TYPES = ['energy', 'gyration', 'rmsd', 'rmsf', 'sasa', 'pca', 'xy', 'unknown']

# Energy subplot layout
ENERGY_MAX_COLS = 2
ENERGY_PER_ROW = 2