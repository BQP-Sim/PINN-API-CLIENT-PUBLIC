"""
PINN API Client Module

Functions for calling the PINN satellite orbit propagation API
and visualizing trajectory results.
"""

import json
import requests
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# API Configuration
API_URL = "https://dev-pinn.bosonqpsi.com/pinn"

# Default propagation parameters
DEFAULT_T_STEP_DURATION = 5000
DEFAULT_N_STEPS = 1
DEFAULT_POINTS_PER_STEP = 50


def is_alternate_format(state: dict) -> bool:
    """
    Detect if the input state uses alternate format (xpos/ypos/zpos fields).

    Args:
        state: Satellite state dictionary

    Returns:
        True if alternate format, False if API format
    """
    return all(key in state for key in ['xpos', 'ypos', 'zpos'])


def transform_state(state: dict) -> dict:
    """
    Transform alternate satellite state format to API-expected format.

    Handles conversion from:
    - xpos/ypos/zpos (km) -> initial_position (meters)
    - xvel/yvel/zvel (km/s) -> initial_velocity (m/s)
    - epoch -> start_date

    Args:
        state: Satellite state dictionary (either format)

    Returns:
        API-compatible state dictionary
    """
    # If already in API format, return as-is
    if 'initial_position' in state:
        return state

    # Check if it's alternate format
    if not is_alternate_format(state):
        # Unknown format, return as-is and let API validate
        return state

    # Transform alternate format to API format
    transformed = {
        'initial_position': [
            state['xpos'] * 1000,  # km to meters
            state['ypos'] * 1000,
            state['zpos'] * 1000
        ],
        'initial_velocity': [
            state['xvel'] * 1000,  # km/s to m/s
            state['yvel'] * 1000,
            state['zvel'] * 1000
        ],
        'start_date': state.get('epoch'),
        'T_STEP_DURATION': state.get('T_STEP_DURATION', DEFAULT_T_STEP_DURATION),
        'N_STEPS': state.get('N_STEPS', DEFAULT_N_STEPS),
        'POINTS_PER_STEP': state.get('POINTS_PER_STEP', DEFAULT_POINTS_PER_STEP)
    }

    return transformed


def load_satellite_states(filepath: str) -> list:
    """
    Parse input file containing satellite states.
    Supports both JSON array format [ {...}, {...} ] and concatenated JSON objects.

    Args:
        filepath: Path to the input JSON file

    Returns:
        List of satellite state dictionaries
    """
    with open(filepath, 'r') as f:
        content = f.read().strip()

    # Try to parse as JSON array first
    try:
        parsed = json.loads(content)
        if isinstance(parsed, list):
            print(f"Loaded {len(parsed)} satellite state(s) from {filepath}")
            return parsed
        elif isinstance(parsed, dict):
            print(f"Loaded 1 satellite state from {filepath}")
            return [parsed]
    except json.JSONDecodeError:
        pass

    # Parse multiple concatenated JSON objects
    decoder = json.JSONDecoder()
    states = []
    idx = 0

    while idx < len(content):
        while idx < len(content) and content[idx] in ' \t\n\r':
            idx += 1
        if idx >= len(content):
            break

        try:
            obj, end_idx = decoder.raw_decode(content[idx:])
            states.append(obj)
            idx += end_idx
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON at position {idx}: {e}")
            break

    print(f"Loaded {len(states)} satellite state(s) from {filepath}")
    return states


def call_pinn_api(payload: dict) -> dict:
    """
    Call the PINN API endpoint to get trajectory prediction.

    Args:
        payload: Dictionary with initial_position, initial_velocity,
                 T_STEP_DURATION, N_STEPS, POINTS_PER_STEP, start_date

    Returns:
        API response dictionary with 'success' status and data/error
    """
    headers = {
        'Content-Type': 'application/json',
        'accept': 'application/json'
    }

    try:
        response = requests.post(API_URL, json=payload, headers=headers, timeout=60)

        if response.status_code == 200:
            return {'success': True, 'data': response.json()}
        elif response.status_code == 422:
            return {'success': False, 'error': 'Validation error', 'details': response.json()}
        else:
            return {'success': False, 'error': f'HTTP {response.status_code}', 'details': response.text}

    except requests.exceptions.Timeout:
        return {'success': False, 'error': 'Request timeout'}
    except requests.exceptions.ConnectionError as e:
        return {'success': False, 'error': f'Connection error: {e}'}
    except Exception as e:
        return {'success': False, 'error': f'Unexpected error: {e}'}


def process_satellites(input_file: str, output_file: str) -> list:
    """
    Load satellite states, call API for each, and save all responses.

    Args:
        input_file: Path to input JSON file with satellite states
        output_file: Path to save API responses

    Returns:
        List of result dictionaries
    """
    states = load_satellite_states(input_file)

    if not states:
        print("No satellite states found in input file.")
        return []

    results = []

    for i, state in enumerate(states):
        print(f"Processing satellite {i+1}/{len(states)}...", end=" ")

        # Transform to API format if needed (handles alternate format auto-detection)
        transformed_state = transform_state(state)
        api_result = call_pinn_api(transformed_state)

        result = {
            'satellite_index': i + 1,
            'input': state,
            'success': api_result['success']
        }

        if api_result['success']:
            result['response'] = api_result['data']
            num_points = len(api_result['data'].get('trajectories', []))
            print(f"Success ({num_points} points)")
        else:
            result['error'] = api_result.get('error', 'Unknown error')
            result['details'] = api_result.get('details')
            print(f"Failed: {result['error']}")
            # Print detailed validation errors
            if result['details'] and isinstance(result['details'], dict):
                detail_list = result['details'].get('detail', [])
                for err in detail_list:
                    loc = ' -> '.join(str(x) for x in err.get('loc', []))
                    msg = err.get('msg', '')
                    err_type = err.get('type', '')
                    print(f"         - {loc}: {msg} (type: {err_type})")

        results.append(result)

    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    success_count = sum(1 for r in results if r['success'])
    print(f"\nResults saved to {output_file}")
    print(f"Summary: {success_count}/{len(results)} successful")

    return results


def plot_trajectory(result: dict, save_path: str = None) -> None:
    """
    Plot a single satellite trajectory in 3D.

    Args:
        result: Result dictionary containing 'response' with trajectory
        save_path: Path to save PNG (optional)
    """
    if not result.get('success'):
        print(f"Satellite {result.get('satellite_index')}: No trajectory (failed)")
        return

    trajectories = result['response'].get('trajectories', [])
    if not trajectories:
        return

    traj = np.array([t['statevector'][:3] for t in trajectories])  # positions in km
    satellite_idx = result.get('satellite_index', 1)

    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')

    ax.plot(traj[:, 0], traj[:, 1], traj[:, 2], 'b-', linewidth=1.5, label='Trajectory')
    ax.scatter(traj[0, 0], traj[0, 1], traj[0, 2], color='green', s=100, marker='o', label='Start')
    ax.scatter(traj[-1, 0], traj[-1, 1], traj[-1, 2], color='red', s=100, marker='s', label='End')

    ax.set_xlabel('X [km]')
    ax.set_ylabel('Y [km]')
    ax.set_zlabel('Z [km]')
    ax.set_title(f'Satellite {satellite_idx} Trajectory')
    ax.legend()
    ax.grid(True)

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Plot saved: {save_path}")

    plt.show()
    plt.close(fig)


def plot_all_trajectories(results: list, save_prefix: str = "trajectory_satellite") -> list:
    """
    Plot all satellite trajectories and save as individual PNG files.

    Args:
        results: List of result dictionaries from process_satellites()
        save_prefix: Prefix for output filenames

    Returns:
        List of saved plot filenames
    """
    saved_files = []
    successful = [r for r in results if r.get('success')]

    if not successful:
        print("No successful trajectories to plot.")
        return saved_files

    print(f"\nGenerating {len(successful)} plot(s)...")

    for result in successful:
        satellite_idx = result.get('satellite_index', 1)
        save_path = f"{save_prefix}_{satellite_idx}.png"

        trajectories = result['response'].get('trajectories', [])
        traj = np.array([t['statevector'][:3] for t in trajectories])  # positions in km

        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111, projection='3d')

        ax.plot(traj[:, 0], traj[:, 1], traj[:, 2], 'b-', linewidth=1.5, label='Trajectory')
        ax.scatter(traj[0, 0], traj[0, 1], traj[0, 2], color='green', s=100, marker='o', label='Start')
        ax.scatter(traj[-1, 0], traj[-1, 1], traj[-1, 2], color='red', s=100, marker='s', label='End')

        ax.set_xlabel('X [km]')
        ax.set_ylabel('Y [km]')
        ax.set_zlabel('Z [km]')
        ax.set_title(f'Satellite {satellite_idx} Trajectory')
        ax.legend()
        ax.grid(True)

        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.show()
        plt.close(fig)

        saved_files.append(save_path)
        print(f"  Saved: {save_path}")

    return saved_files
