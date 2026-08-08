"""
propagate_sequential.py — propagate the 200-state dataset ONE satellite per HTTP
request via the sequential endpoint (POST /pinn).

Output: outputs/results_sequential.json
  { "meta": {...timing...}, "results": [ {id, regime, satellite_type, trajectories}, ... ] }

Run:  python propagate_sequential.py
Point at a different host with:  PINN_API=https://my-host  python propagate_sequential.py
"""
import os
import json
import time
import requests

API_BASE = os.environ.get("PINN_API", "https://dev-pinn.bosonqpsi.com")
N_STEPS, POINTS_PER_STEP = 1, 50
# Each regime is propagated at its maximum single-shot horizon.
MAX_STEP = {"leo": 5000.0, "geo": 10000.0}

states = json.load(open("data/states_200.json"))
session = requests.Session()          # reuse the TCP connection across the 200 calls
results, latencies = [], []

t0 = time.perf_counter()
for s in states:
    body = {
        "initial_position": s["initial_position"],
        "initial_velocity": s["initial_velocity"],
        "T_STEP_DURATION": MAX_STEP[s["regime"]],   # LEO 5000 s, GEO 10000 s
        "N_STEPS": N_STEPS,
        "POINTS_PER_STEP": POINTS_PER_STEP,
        "start_date": s["start_date"],
    }
    t = time.perf_counter()
    r = session.post(f"{API_BASE}/pinn", json=body, timeout=60)
    latencies.append(time.perf_counter() - t)
    r.raise_for_status()
    data = r.json()
    results.append({
        "id": s["id"],
        "regime": s["regime"],
        "satellite_type": data["satellite_type"],
        "trajectories": data["trajectories"],      # 50 × {statevector[km,km/s], timestamp}
    })
wall = time.perf_counter() - t0

out = {
    "meta": {
        "mode": "sequential",
        "endpoint": f"{API_BASE}/pinn",
        "count": len(results),
        "total_wall_s": round(wall, 3),
        "mean_latency_ms": round(1e3 * sum(latencies) / len(latencies), 1),
    },
    "results": results,
}
os.makedirs("outputs", exist_ok=True)
json.dump(out, open("outputs/results_sequential.json", "w"), indent=2)
print(f"sequential: {len(results)} satellites in {wall:.1f}s "
      f"({out['meta']['mean_latency_ms']} ms/call) -> outputs/results_sequential.json")
