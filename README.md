# PINN API Client

A Jupyter notebook client for calling the PINN (Physics-Informed Neural Network) satellite orbit propagation API.

## Overview

This tool:
1. Reads satellite state vectors from an input JSON file
2. Calls the PINN API endpoint to get trajectory predictions
3. Saves API responses to an output JSON file
4. Generates 3D trajectory plots and saves them as images

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
   - `api_responses.json` - API responses with trajectory data
   - `trajectory_plot_satellite_X.png` - 3D trajectory plots for each satellite

## Input File Format

The input file (`input_states.json`) supports two formats:

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

## Input Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `initial_position` | [x, y, z] | Position in meters (EME2000 frame) |
| `initial_velocity` | [vx, vy, vz] | Velocity in m/s (EME2000 frame) |
| `T_STEP_DURATION` | number | Propagation duration per step (seconds) |
| `N_STEPS` | integer | Number of propagation steps |
| `POINTS_PER_STEP` | integer | Output points per step |
| `start_date` | string | ISO 8601 timestamp |

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
API_URL = "https://dev-pinn.bosonqpsi.com/pinn"
INPUT_FILE = "input_states.json"
OUTPUT_FILE = "api_responses.json"
PLOT_OUTPUT = "trajectory_plot.png"
```

## License

Private - BosonQ Psi
