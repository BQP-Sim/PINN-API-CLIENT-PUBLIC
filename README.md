# PINN API Client

A Jupyter notebook client for calling the PINN (Physics-Informed Neural Network) satellite orbit propagation API.

## Overview

This tool:
1. Reads satellite state vectors from an input JSON file
2. Processes sequential states with dynamic duration calculation
3. Calls the PINN API endpoint to get trajectory predictions
4. Saves API responses to an output JSON file
5. Generates 3D trajectory plots (combined and individual) and saves them as images

## Project Structure

```
pinn-api-client/
├── api_client.ipynb    # Main notebook (run this)
├── pinn_client.py      # API functions (implementation)
├── input_states.json   # Sample input file
├── requirements.txt    # Python dependencies
└── README.md
```

## Prerequisites

- Python 3.8+
- pip (Python package manager)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/divyanshde/pinn-api-client.git
   cd pinn-api-client
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. **Prepare input file**: Edit `input_states.json` with your satellite state vectors (see format below)

2. **Run the notebook**: Open `api_client.ipynb` in Jupyter and run all cells
   ```bash
   jupyter notebook api_client.ipynb
   ```

3. **View outputs**:
   - `sequential_results.json` - API responses with trajectory data
   - `combined_trajectory.png` - Combined 3D plot of all trajectories
   - `trajectory_X.png` - Individual 3D trajectory plots for each input

## Input File Format

The input file (`input_states.json`) supports multiple formats:

### JSON Array (recommended)
```json
[
  {
    "initial_position": [-3373940.962, 954637.389, -6038104.174],
    "initial_velocity": [-5466.05319, 3727.802041, 3649.934323],
    "T_STEP_DURATION": 5000,
    "N_STEPS": 1,
    "POINTS_PER_STEP": 50,
    "start_date": "2025-11-11T14:17:48.827Z"
  },
  {
    ...
  }
]
```

### Concatenated JSON Objects
```json
{
  "initial_position": [...],
  ...
}

{
  "initial_position": [...],
  ...
}
```

### Alternate Format (auto-converted)

The client also supports an alternate format with separate position/velocity fields in kilometers. This format is auto-detected and converted to the API format.

```json
{
  "xpos": -41825.915857758,
  "ypos": -5226.43453712596,
  "zpos": 1386.1644692968,
  "xvel": 0.377893637472634,
  "yvel": -3.04789052585241,
  "zvel": -0.130866937678928,
  "epoch": "2025-12-03T02:20:57.497920Z"
}
```

**Auto-conversion:**
- `xpos/ypos/zpos` (km) → `initial_position` (meters)
- `xvel/yvel/zvel` (km/s) → `initial_velocity` (m/s)
- `epoch` → `start_date`
- Default values applied: `T_STEP_DURATION=5000`, `N_STEPS=1`, `POINTS_PER_STEP=50`

## Input Parameters

### API Format

| Parameter | Type | Description |
|-----------|------|-------------|
| `initial_position` | [x, y, z] | Position in meters (EME2000 frame) |
| `initial_velocity` | [vx, vy, vz] | Velocity in m/s (EME2000 frame) |
| `T_STEP_DURATION` | number | Propagation duration per step (seconds) |
| `N_STEPS` | integer | Number of propagation steps |
| `POINTS_PER_STEP` | integer | Output points per step |
| `start_date` | string | ISO 8601 timestamp |

### Alternate Format

| Parameter | Type | Description |
|-----------|------|-------------|
| `xpos`, `ypos`, `zpos` | number | Position in kilometers |
| `xvel`, `yvel`, `zvel` | number | Velocity in km/s |
| `epoch` | string | ISO 8601 timestamp |

## API Response

```json
{
  "trajectory": [
    [x1, y1, z1],
    [x2, y2, z2],
    ...
  ]
}
```

The trajectory contains position coordinates in meters for each time step.

## Configuration

Edit these variables in the notebook (Cell 1) to customize paths:

```python
INPUT_FILE = "input_states.json"
OUTPUT_FILE = "sequential_results.json"
PLOT_OUTPUT = "combined_trajectory.png"
```

The API URL is configured in `pinn_client.py`:

```python
API_URL = "https://dev-pinn.bosonqpsi.com/pinn"
```

## License

Private - BosonQ Psi
