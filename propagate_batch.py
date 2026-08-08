"""
propagate_batch.py — propagate all 200 states with the batch endpoint (POST /pinn_batch),
ONE call per regime. The batch endpoint takes a single propagation window per call, and each
regime uses its own max single-shot horizon (LEO 5000 s, GEO 10000 s), so LEO and GEO go in
separate calls (2 calls for the whole 200-satellite set vs 200 sequential calls).

Output: outputs/results_batch.json
  { "meta": {...per-regime device/gpu_fallback/timing...}, "results": [ {id, regime, satellite_type, trajectories}, ... ] }

If outputs/results_sequential.json exists, this also checks that the batch positions
match the sequential ones (they should, to well under a metre) as a sanity check.

Run:  python propagate_batch.py     (PINN_API=... to change host)
"""
import os
import json
import time
import requests

API_BASE = os.environ.get("PINN_API", "https://dev-pinn.bosonqpsi.com")
N_STEPS, POINTS_PER_STEP = 1, 50
MAX_STEP = {"leo": 5000.0, "geo": 10000.0}   # per-regime max single-shot horizon

states = json.load(open("data/states_200.json"))
results = [None] * len(states)               # filled by original index -> preserves input order
calls_meta = []

t0 = time.perf_counter()
for regime in ("leo", "geo"):
    idx = [i for i, s in enumerate(states) if s["regime"] == regime]
    if not idx:
        continue
    payload = {
        "states": [
            {"initial_position": states[i]["initial_position"],
             "initial_velocity": states[i]["initial_velocity"],
             "start_date": states[i]["start_date"]}
            for i in idx
        ],
        "T_STEP_DURATION": MAX_STEP[regime],
        "N_STEPS": N_STEPS,
        "POINTS_PER_STEP": POINTS_PER_STEP,
        "regime": regime,                    # homogeneous batch -> tell the server the regime
        "use_gpu": True,                     # server uses CUDA if present, else falls back to CPU
    }
    t = time.perf_counter()
    r = requests.post(f"{API_BASE}/pinn_batch", json=payload, timeout=600)
    call_s = time.perf_counter() - t
    r.raise_for_status()
    data = r.json()                          # {device, gpu_fallback, count, results:[...]}
    for i, res in zip(idx, data["results"]):
        results[i] = {"id": states[i]["id"], "regime": regime,
                      "satellite_type": res["satellite_type"], "trajectories": res["trajectories"]}
    calls_meta.append({"regime": regime, "count": len(idx), "T_STEP_DURATION": MAX_STEP[regime],
                       "device": data.get("device"), "gpu_fallback": data.get("gpu_fallback"),
                       "wall_s": round(call_s, 3)})
wall = time.perf_counter() - t0

out = {
    "meta": {
        "mode": "batch",
        "endpoint": f"{API_BASE}/pinn_batch",
        "count": len(results),
        "calls": calls_meta,                 # one entry per regime call
        "total_wall_s": round(wall, 3),
        "ms_per_satellite": round(1e3 * wall / len(results), 2),
    },
    "results": results,
}
os.makedirs("outputs", exist_ok=True)
json.dump(out, open("outputs/results_batch.json", "w"), indent=2)
print(f"batch: {len(results)} satellites in {len(calls_meta)} calls in {wall:.2f}s "
      f"({out['meta']['ms_per_satellite']} ms/sat) -> outputs/results_batch.json")
for c in calls_meta:
    print(f"  {c['regime'].upper()}: {c['count']} sats @ {c['T_STEP_DURATION']:.0f}s in {c['wall_s']}s "
          f"(device={c['device']}, gpu_fallback={c['gpu_fallback']})")

# ---- optional equivalence check vs the sequential run ----
seq_path = "outputs/results_sequential.json"
if os.path.exists(seq_path):
    seq = {x["id"]: x for x in json.load(open(seq_path))["results"]}
    worst = 0.0
    for res in results:
        if res["id"] not in seq:
            continue
        for a, b in zip(res["trajectories"], seq[res["id"]]["trajectories"]):
            pa, pb = a["statevector"][:3], b["statevector"][:3]           # positions (km)
            worst = max(worst, max(abs(x - y) for x, y in zip(pa, pb)))
    print(f"equivalence vs sequential: worst position diff = {worst*1e3:.3f} m")
