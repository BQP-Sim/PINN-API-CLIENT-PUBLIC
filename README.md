# PINN API Client

A small client for the PINN (Physics-Informed Neural Network) satellite orbit-propagation
API. It ships a 200-satellite demo dataset and two tiny scripts that propagate it two ways —
one satellite per request (**sequential**) and all satellites in one request (**batch**) — so
you can compare them directly.

## What's in here

```
data/states_200.json          200 demo state vectors (100 LEO + 100 GEO), EME2000, metres
propagate_sequential.py       propagate the 200 states via POST /pinn        (200 calls)
propagate_batch.py            propagate the 200 states via POST /pinn_batch   (1 call)
make_samples.py               pick 5 sample sats -> step-by-step CSV + 3D plot
outputs/                      generated results (see below)
requirements.txt
```

## Quickstart

```bash
pip install -r requirements.txt

python propagate_sequential.py     # -> outputs/results_sequential.json
python propagate_batch.py          # -> outputs/results_batch.json  (+ equivalence check)
python make_samples.py             # -> outputs/sample5_steps.csv + sample5_trajectory_3d.png
```

By default the scripts call `https://dev-pinn.bosonqpsi.com`. Point them elsewhere with:

```bash
PINN_API=https://my-host python propagate_batch.py
```

**Propagation window:** each regime is propagated at its **maximum single-shot horizon** —
**LEO 5,000 s, GEO 10,000 s** (50 points each). Because the batch endpoint takes one window per
call, `propagate_batch.py` issues **one call per regime** (LEO @ 5,000 s, GEO @ 10,000 s) — still
2 calls for all 200 satellites versus 200 sequential calls.

## The dataset

`data/states_200.json` is a list of 200 satellites, each in the API-native format
(EME2000, **metres / m·s⁻¹**), with a `regime` label and epoch:

```json
{
  "id": "leo-47",
  "regime": "leo",
  "initial_position": [-4360840.15, -3501658.32, 4454859.44],
  "initial_velocity": [-678.62, -5327.25, -5146.17],
  "start_date": "2026-01-29T14:12:23.109262Z"
}
```

100 LEO + 100 GEO, taken from the internal benchmarking sets. `states_200.json` is
self-contained — the source spreadsheets are not needed to run the client.

## Outputs

| File | Produced by | Contents |
|---|---|---|
| `outputs/results_sequential.json` | `propagate_sequential.py` | all 200 trajectories + timing (`meta`) |
| `outputs/results_batch.json` | `propagate_batch.py` | all 200 trajectories + `device`/`gpu_fallback`/timing |
| `outputs/sample5_steps.csv` | `make_samples.py` | 5 sample satellites, **every** step (50 points): position + velocity per timestamp |
| `outputs/sample5_trajectory_3d.png` | `make_samples.py` | 3D trajectories of the 5 samples (LEO and GEO on separate axes) |

Each trajectory is 50 points of `{ "statevector": [x, y, z, vx, vy, vz], "timestamp": ... }`
(positions in km, velocities in km·s⁻¹).

## Benchmark: speed & accuracy vs Orekit

Full-dataset benchmark of the deployed API (how users call it) against Orekit run locally
(how users generate truth). Datasets: **3,011 LEO** and **1,411 GEO** unseen states, 5000 s arc,
50 points each. Speed is API round-trip; Orekit is a warm local J2 propagation.

| Regime | n | Sequential `/pinn` | Batch `/pinn_batch` | Local Orekit | Batch vs Orekit | Mean accuracy* |
|---|---:|---:|---:|---:|---:|---:|
| LEO | 3,011 | 859 s (285 ms/call) | **9.4 s** | 29 s | **3.1× faster** | 1.40 km |
| GEO | 1,411 | 416 s (295 ms/call) | **5.5 s** | 18 s | **3.2× faster** | 0.054 km (54 m) |

<sub>*Mean position deviation, PINN vs Orekit, over the 5000 s arc.</sub>

Takeaways:
- **Sequential per-call is HTTP-bound** (~0.28 s/call) — for many objects it loses to a local
  Orekit loop. **Batch amortises one round-trip over the whole set** and beats local Orekit ~3×.
- **Batch vs sequential ≈ 91× (LEO) / 76× (GEO)**; positions are identical between the two modes
  (agree to a few metres). The demo scripts here reproduce the pattern: sequential ≈ 55 s vs
  batch ≈ 6 s (2 regime calls) for the 200-satellite set.
- The batch call currently reports `device: cpu`, `gpu_fallback: true` (the deploy box has no
  CUDA GPU); on a GPU-backed deployment the batch lead widens further.
- **Recommendation:** to propagate many objects, use `POST /pinn_batch`, not a per-satellite loop.

## API reference (summary)

**`POST /pinn`** — one satellite. Body: `initial_position`/`initial_velocity` (metres, EME2000),
`T_STEP_DURATION`, `N_STEPS`, `POINTS_PER_STEP`, `start_date`. Returns
`{ "trajectories": [{statevector, timestamp}], "satellite_type" }`.

**`POST /pinn_batch`** — many satellites in one call. Body: `states: [{initial_position,
initial_velocity, start_date}]`, plus `T_STEP_DURATION`/`N_STEPS`/`POINTS_PER_STEP`,
`regime` (`auto`|`leo`|`geo`), `use_gpu`. Returns
`{ "device", "gpu_fallback", "count", "results": [{satellite_type, trajectories}] }`
in input order. Max 4096 states per call.
