#!/usr/bin/env bash
# Render the README example figures into figs/.
# Requires gmxplot on PATH (after `pip install -e .`). Run from the repo root:
#   bash examples/make_figures.sh
set -euo pipefail
cd "$(dirname "$0")/.."

D=examples/data
mkdir -p figs

# Logo: a relaxing observable with its SD band (the replica motif).
python - <<'PY'
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
t = np.linspace(0, 5, 400)
mu = 0.35 + 0.55 * np.exp(-t / 1.4)
sd = 0.05 + 0.10 * np.exp(-t / 1.4)
fig = plt.figure(figsize=(3.4, 2.0), dpi=160)
ax = fig.add_axes([0, 0, 1, 1]); ax.axis('off')
ax.fill_between(t, mu - sd, mu + sd, color='#1f77b4', alpha=0.22)
ax.plot(t, mu - sd, color='#1f77b4', lw=1.0, alpha=0.5)
ax.plot(t, mu + sd, color='#1f77b4', lw=1.0, alpha=0.5)
ax.plot(t, mu, color='#1f77b4', lw=3.2)
ax.set_xlim(0, 5); ax.set_ylim(-0.02, 1.02)
fig.savefig('figs/logo.png', transparent=True)
print('logo.png')
PY

gmxplot plot "$D/rmsd_r1.xvg" -o figs/plot_timeseries.png \
  --roll-window 5 --t-eq 50 --plot-full --mean --title "Backbone RMSD"

gmxplot plot "$D/hbond_dist.xvg" -o figs/plot_histogram.png \
  --title "Hydrogen bond distance distribution"

gmxplot plot "$D/eigenvalue.xvg" -o figs/plot_spectrum.png \
  --ylog --title "Covariance eigenvalue spectrum"

gmxplot plot "$D/cluster_size.xvg" -o figs/plot_bar.png \
  --title "Cluster size distribution"

gmxplot plot "$D/proj2d.xvg" -o figs/plot_pca.png \
  --title "Free-energy landscape (PC1-PC2)"

gmxplot plot "$D/rmsf.xvg" -o figs/plot_profile.png \
  --title "Per-residue RMSF"

gmxplot compare "$D/rmsd_r1.xvg" "$D/rmsd_r2.xvg" \
  -l1 "Run 1" -l2 "Run 2" --roll-window 5 --title "RMSD comparison" \
  -o figs/compare.png

gmxplot replicas "$D/rmsd_r1.xvg" "$D/rmsd_r2.xvg" "$D/rmsd_r3.xvg" \
  --labels r1,r2,r3 --band sd --roll-window 5 --title "Replica mean ± SD" \
  -o figs/replicas.png

gmxplot dashboard examples/dashboard.json -o figs/dashboard.png

echo "Figures written to figs/"
