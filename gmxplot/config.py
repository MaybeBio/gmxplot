"""Default configuration constants for gmxplot.

Everything here is overridable from the CLI; these are only the defaults.
"""

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

# Multi-file color palette (tab10)
MULTI_COLORS = [
    '#1f77b4', '#d62728', '#2ca02c', '#9467bd',
    '#ff7f0e', '#8c564b', '#e377c2', '#7f7f7f',
    '#bcbd22', '#17becf',
]

# Replica aggregation
REPLICA_LINE_ALPHA = 0.35
MEAN_LINE_COLOR = '#1f77b4'
BAND_COLOR = '#1f77b4'
BAND_ALPHA = 0.25

# Rolling average
ROLL_AVG_DEFAULT_PLOT = None  # None = auto-calculate
ROLL_AVG_DEFAULT_COMPARE = 50
ROLL_MIN = 3
ROLL_MAX_SAMPLES = 100
ROLL_MAX_FRACTION_OF_N = 0.5
ROLL_FRACTION_TIME = 0.01    # fraction of x-span (time series)
ROLL_FRACTION_NONTIME = 0.05  # fraction of x-span (ordered non-time)

# Block averaging
BLOCK_MIN_SIZE = 2
BLOCK_N_EXPONENT = 1.0 / 3.0  # block size ~ n**(1/3)

# Statistics
FLAT_THRESHOLD = 2.0

# Data families (semantic content)
FAMILIES = [
    'energy', 'rmsd', 'rmsf', 'gyration', 'sasa', 'pca',
    'hbond_num', 'hbond_dist', 'mindist', 'contacts',
    'eigenvalue', 'cluster_size', 'dssp', 'generic', 'unknown',
]

# Rendering/statistics semantics
KINDS = [
    'timeseries', 'profile', 'histogram', 'spectrum',
    'bar', 'pca', 'scatter', 'xy',
]

# Time units we can normalize
TIME_UNITS = ['auto', 'ps', 'ns', 'us', 'fs']
# ps, ns, us, fs -> ns
TIME_TO_NS = {'ps': 1e-3, 'ns': 1.0, 'us': 1e3, 'fs': 1e-6}

# Kinds that never accept rolling average smoothing
NO_SMOOTH_KINDS = {'profile', 'histogram', 'spectrum', 'bar', 'pca', 'scatter', 'xy'}

# Families whose default plotted y columns are a strict subset of all columns.
# Values are matched case-insensitively against the resolved column names.
PRIMARY_Y_COLUMNS = {
    'gyration': ['Rg'],
    'sasa': ['Area'],
    'rmsd': ['RMSD'],
    'rmsf': ['RMSF'],
    'pca': ['PC1', 'PC2'],
}

# Fallback canonical y-column names (used when no @ sN legend is present and the
# family has a single well-known y column).
CANONICAL_Y_COLUMNS = {
    'energy': ['Potential', 'Temperature', 'Pressure', 'Density',
               'Total Energy', 'Volume', 'Kinetic En.', 'Enthalpy'],
    'gyration': ['Rg', 'Rgx', 'Rgy', 'Rgz'],
    'rmsd': ['RMSD'],
    'rmsf': ['RMSF'],
    'sasa': ['Area', 'StdDev'],
    'hbond_num': ['Number of H-bonds'],
    'hbond_dist': ['Count'],
    'mindist': ['Distance'],
    'contacts': ['Contacts'],
    'eigenvalue': ['Eigenvalue'],
    'cluster_size': ['Cluster size'],
    'dssp': ['DSSP'],
}
