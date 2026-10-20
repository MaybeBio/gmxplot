"""Generate synthetic-but-realistic GROMACS XVG files for the README examples.

Each file carries a genuine GROMACS-style header (``@ title``, ``@ xaxis
label``, ``@ yaxis label``, ``@ sN legend``) so ``gmxplot`` auto-detects the
correct family/kind. Data are drawn from seeded RNGs so the examples are
reproducible.

Run from the repository root::

    python examples/generate_data.py

Output is written to ``examples/data/``.
"""

from pathlib import Path

import numpy as np

RNG = np.random.default_rng(20260101)
OUT = Path(__file__).resolve().parent / 'data'
OUT.mkdir(parents=True, exist_ok=True)


def header(title, xlabel, ylabel, legends=(), subtitle=''):
    lines = ['# This file was created by gmxplot examples (synthetic data)']
    lines.append(f'@ title "{title}"')
    if subtitle:
        lines.append(f'@ subtitle "{subtitle}"')
    lines.append(f'@ xaxis label "{xlabel}"')
    lines.append(f'@ yaxis label "{ylabel}"')
    for i, lg in enumerate(legends):
        lines.append(f'@ s{i} legend "{lg}"')
    return '\n'.join(lines) + '\n'


def relax_curve(t, y0, plateau, tau, sigma, seed):
    """Exponential relaxation to a plateau with noise (an equilibrating observable)."""
    rng = np.random.default_rng(seed)
    y = plateau + (y0 - plateau) * np.exp(-t / tau)
    return y + rng.normal(0.0, sigma, size=len(t))


def write_rmsd(name, seed, y0=0.46, plateau=0.28, tau=25.0, sigma=0.02):
    t = np.linspace(0.0, 200.0, 2001)
    y = relax_curve(t, y0, plateau, tau, sigma, seed)
    with open(OUT / name, 'w') as f:
        f.write(header('RMSD', 'Time (ns)', '(nm)', ['RMSD']))
        for tt, yy in zip(t, y):
            f.write(f'{tt:.3f} {yy:.4f}\n')


def write_gyrate(name, seed, r0=1.86, rp=1.78, tau=15.0, sigma=0.008):
    t = np.linspace(0.0, 200.0, 2001)
    rng = np.random.default_rng(seed)
    rg = relax_curve(t, r0, rp, tau, sigma, seed)
    rgx = relax_curve(t, 0.98, 0.95, tau, 0.006, seed + 1)
    rgy = relax_curve(t, 1.02, 0.97, tau, 0.006, seed + 2)
    rgz = relax_curve(t, 1.00, 0.96, tau, 0.006, seed + 3)
    with open(OUT / name, 'w') as f:
        f.write(header('Radius of gyration (total and around axes)', 'Time (ns)', '(nm)',
                       ['Rg', 'RgX', 'RgY', 'RgZ']))
        for tt, a, b, c, d in zip(t, rg, rgx, rgy, rgz):
            f.write(f'{tt:.3f} {a:.4f} {b:.4f} {c:.4f} {d:.4f}\n')


def write_hbnum(name, seed, n0=13.0, np_=8.0, tau=20.0, sigma=1.4):
    t = np.linspace(0.0, 200.0, 2001)
    y = relax_curve(t, n0, np_, tau, sigma, seed)
    with open(OUT / name, 'w') as f:
        f.write(header('Number of Hydrogen Bonds', 'Time (ns)', 'number'))
        for tt, yy in zip(t, y):
            f.write(f'{tt:.3f} {yy:.3f}\n')


def write_rmsf(name='rmsf.xvg'):
    resid = np.arange(1, 91)
    base = 0.10 + 0.03 * RNG.normal(size=len(resid))
    # loop peaks
    peaks = {18: 0.30, 45: 0.38, 72: 0.34}
    for r, h in peaks.items():
        idx = resid == r
        base[idx] = h
    base[5] = 0.22  # N-terminus
    base[-5] = 0.24  # C-terminus
    y = base + 0.02 * RNG.normal(size=len(resid))
    y = np.clip(y, 0.03, None)
    with open(OUT / name, 'w') as f:
        f.write(header('RMS fluctuation', 'Residue', '(nm)', ['RMSF']))
        for r, yy in zip(resid, y):
            f.write(f'{r} {yy:.4f}\n')


def write_hbond_dist(name='hbond_dist.xvg'):
    d = np.linspace(0.26, 0.40, 29)
    peak = 0.30
    sigma = 0.025
    counts = 520 * np.exp(-0.5 * ((d - peak) / sigma) ** 2)
    counts = counts + 0.02 * RNG.normal(size=len(d)) * counts.max()
    counts = np.clip(counts, 0.0, None)
    with open(OUT / name, 'w') as f:
        f.write(header('Hydrogen Bond Distribution', 'Distance (nm)', 'count',
                       ['Number of Hydrogen Bonds']))
        for dd, cc in zip(d, counts):
            f.write(f'{dd:.4f} {cc:.3f}\n')


def write_eigenvalue(name='eigenvalue.xvg'):
    idx = np.arange(1, 21)
    ev = 1.6 * np.exp(-(idx - 1) / 4.0) + 0.03 * RNG.normal(size=len(idx))
    ev = np.clip(ev, 0.005, None)
    with open(OUT / name, 'w') as f:
        f.write(header('Eigenvalues of the covariance matrix', 'Eigenvector index',
                       r'eigenvalue (nm\S2\N)', ['Eigenvalue']))
        for i, e in zip(idx, ev):
            f.write(f'{i} {e:.4f}\n')


def write_cluster_size(name='cluster_size.xvg'):
    size = np.arange(1, 16)
    counts = np.array([42, 18, 9, 6, 4, 3, 2, 2, 1, 1, 1, 1, 1, 1, 1])
    with open(OUT / name, 'w') as f:
        f.write(header('Cluster size distribution', 'Cluster size', 'Number of clusters'))
        for s, c in zip(size, counts):
            f.write(f'{s} {c}\n')


def write_proj2d(name='proj2d.xvg'):
    n = 6000
    # three basins in PC space
    centers = [(0.0, 0.0), (2.2, 1.4), (-1.8, 2.2)]
    weights = [0.5, 0.3, 0.2]
    sig = 0.45
    pc1, pc2 = [], []
    for _ in range(n):
        cx, cy = centers[RNG.choice(3, p=weights)]
        pc1.append(cx + sig * RNG.normal())
        pc2.append(cy + sig * RNG.normal())
    with open(OUT / name, 'w') as f:
        f.write(header('2d projection of trajectory',
                       'projection on eigenvector 1 (nm)',
                       'projection on eigenvector 2 (nm)', ['PC1', 'PC2']))
        for a, b in zip(pc1, pc2):
            f.write(f'{a:.4f} {b:.4f}\n')


def main():
    write_rmsd('rmsd_r1.xvg', seed=11)
    write_rmsd('rmsd_r2.xvg', seed=22, plateau=0.30)
    write_rmsd('rmsd_r3.xvg', seed=33, plateau=0.27)
    write_gyrate('gyrate_r1.xvg', seed=41)
    write_gyrate('gyrate_r2.xvg', seed=42, rp=1.80)
    write_gyrate('gyrate_r3.xvg', seed=43, rp=1.77)
    write_hbnum('hbnum_r1.xvg', seed=51)
    write_hbnum('hbnum_r2.xvg', seed=52, np_=7.5)
    write_hbnum('hbnum_r3.xvg', seed=53, np_=8.5)
    write_rmsf()
    write_hbond_dist()
    write_eigenvalue()
    write_cluster_size()
    write_proj2d()
    print(f'Wrote {len(list(OUT.glob("*.xvg")))} XVG files to {OUT}')


if __name__ == '__main__':
    main()
