"""
make_samples.py — from the full results, pick 5 representative satellites
(3 LEO spanning low/mid/high altitude + 2 GEO) and emit:

  outputs/sample5_steps.csv           every propagation step (50 points) per sample:
                                       id, regime, step, timestamp, x,y,z (km), vx,vy,vz (km/s)
  outputs/sample5_trajectory_3d.png   3D trajectories, LEO and GEO on separate axes
                                       (their radii differ ~6x, so one shared axis hides LEO)

Reads outputs/results_batch.json by default (batch == sequential); run after a propagate_*.py.
"""
import json
import csv
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 (enables 3d projection)

RESULTS = "outputs/results_batch.json"
res = {r["id"]: r for r in json.load(open(RESULTS))["results"]}


def altitude_km(r):
    """Initial geocentric radius - Earth radius, from the first statevector (km)."""
    x, y, z = r["trajectories"][0]["statevector"][:3]
    return (x * x + y * y + z * z) ** 0.5 - 6378.137


leo = sorted([r for r in res.values() if r["regime"] == "leo"], key=altitude_km)
geo = [r for r in res.values() if r["regime"] == "geo"]
# 3 LEO spanning the altitude range (lowest, median, highest) + first 2 GEO
samples = [leo[0], leo[len(leo) // 2], leo[-1], geo[0], geo[1]]

# ---- 1. step-by-step CSV ----
with open("outputs/sample5_steps.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "regime", "step", "timestamp", "x_km", "y_km", "z_km",
                "vx_kms", "vy_kms", "vz_kms"])
    for r in samples:
        for i, pt in enumerate(r["trajectories"]):
            sv = pt["statevector"]
            w.writerow([r["id"], r["regime"], i, pt["timestamp"], *sv])

# ---- 2. 3D trajectory plot (LEO and GEO on separate axes) ----
fig = plt.figure(figsize=(13, 6))
for col, (title, group) in enumerate([("LEO samples", samples[:3]), ("GEO samples", samples[3:])]):
    ax = fig.add_subplot(1, 2, col + 1, projection="3d")
    for r in group:
        p = np.array([pt["statevector"][:3] for pt in r["trajectories"]])
        ax.plot(p[:, 0], p[:, 1], p[:, 2], lw=1.6, label=r["id"])
        ax.scatter(*p[0], s=25, marker="o")   # start marker
    ax.set_title(title)
    ax.set_xlabel("x (km)"); ax.set_ylabel("y (km)"); ax.set_zlabel("z (km)")
    ax.legend(fontsize=8)
fig.suptitle("Sample satellite trajectories (EME2000, 5000 s arc)")
fig.tight_layout()
fig.savefig("outputs/sample5_trajectory_3d.png", dpi=150)
print("wrote outputs/sample5_steps.csv and outputs/sample5_trajectory_3d.png "
      f"for: {[r['id'] for r in samples]}")
