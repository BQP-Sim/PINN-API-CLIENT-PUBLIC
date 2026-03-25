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
from datetime import datetime

# API Configuration
API_URL = "https://dev-pinn.bosonqpsi.com/pinn"

# Default propagation parameters
DEFAULT_T_STEP_DURATION = 5000
DEFAULT_N_STEPS = 1
DEFAULT_POINTS_PER_STEP = 50

# Maximum propagation duration (for dynamic duration calculation)
MAX_DURATION = 5000


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


def calculate_epoch_difference(epoch1: str, epoch2: str) -> float:
    """
    Calculate time difference between two epochs in seconds.

    Args:
        epoch1: Start epoch (ISO 8601 string)
        epoch2: End epoch (ISO 8601 string)

    Returns:
        Duration in seconds
    """
    # Handle multiple timestamp formats
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S"
    ]

    def parse_epoch(epoch_str):
        for fmt in formats:
            try:
                return datetime.strptime(epoch_str, fmt)
            except ValueError:
                continue
        raise ValueError(f"Unable to parse epoch: {epoch_str}")

    t1 = parse_epoch(epoch1)
    t2 = parse_epoch(epoch2)
    return (t2 - t1).total_seconds()


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


def process_sequential_states(input_file: str, output_file: str) -> list:
    """
    Process sequential satellite states with dynamic duration.

    For states at epochs E1, E2, E3, ..., En:
    - Duration for E1 to E(n-1) = min(E(i+1) - E(i), MAX_DURATION)
    - Duration for En (last) = MAX_DURATION seconds

    Args:
        input_file: Path to input JSON with sequential states
        output_file: Path to save results

    Returns:
        List of propagation results
    """
    states = load_satellite_states(input_file)

    if not states:
        print("No states found in input file.")
        return []

    # Sort by epoch
    states = sorted(states, key=lambda s: s.get('epoch') or s.get('start_date'))

    results = []

    for i, current_state in enumerate(states):
        epoch_current = current_state.get('epoch') or current_state.get('start_date')

        # Calculate duration
        if i < len(states) - 1:
            # Not last state: use epoch difference (capped at MAX_DURATION)
            next_state = states[i + 1]
            epoch_next = next_state.get('epoch') or next_state.get('start_date')
            calculated_duration = calculate_epoch_difference(epoch_current, epoch_next)
            duration = min(calculated_duration, MAX_DURATION)
            target_epoch = epoch_next
        else:
            # Last state: fixed MAX_DURATION seconds
            duration = MAX_DURATION
            target_epoch = None

        print(f"Propagation {i+1}/{len(states)}: {epoch_current} ({duration:.1f}s)", end=" ")

        # Transform and override duration
        transformed = transform_state(current_state)
        transformed['T_STEP_DURATION'] = duration

        # Call API
        api_result = call_pinn_api(transformed)

        result = {
            'propagation_index': i + 1,
            'from_epoch': epoch_current,
            'to_epoch': target_epoch,
            'duration_seconds': duration,
            'input': current_state,
            'success': api_result['success']
        }

        if api_result['success']:
            result['response'] = api_result['data']
            print("Success")
        else:
            result['error'] = api_result.get('error')
            result['details'] = api_result.get('details')
            print(f"Failed: {result['error']}")

        results.append(result)

    # Save results
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    success_count = sum(1 for r in results if r['success'])
    print(f"\nResults saved to {output_file}")
    print(f"Summary: {success_count}/{len(results)} successful propagations")

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


def plot_combined_trajectory(results: list, save_path: str = "combined_trajectory.png", title: str = "Combined Satellite Trajectory") -> str:
    """
    Plot all trajectories on a single combined 3D graph.

    Args:
        results: List of result dictionaries from process_sequential_states()
        save_path: Path to save the combined plot
        title: Title for the plot

    Returns:
        Path to saved plot file
    """
    successful = [r for r in results if r.get('success')]

    if not successful:
        print("No successful trajectories to plot.")
        return None

    fig = plt.figure(figsize=(12, 10))
    ax = fig.add_subplot(111, projection='3d')

    # Color map for different propagation segments
    colors = plt.cm.viridis(np.linspace(0, 1, len(successful)))

    for idx, result in enumerate(successful):
        trajectories = result['response'].get('trajectories', [])
        traj = np.array([t['statevector'][:3] for t in trajectories])  # positions in km

        prop_idx = result.get('propagation_index', idx + 1)

        # Plot trajectory segment
        ax.plot(traj[:, 0], traj[:, 1], traj[:, 2],
                color=colors[idx], linewidth=1.5,
                label=f'Prop {prop_idx}')

        # Mark start of each segment
        ax.scatter(traj[0, 0], traj[0, 1], traj[0, 2],
                   color=colors[idx], s=80, marker='o', edgecolors='black')

    # Mark overall start (green) and end (red)
    first_traj = np.array([t['statevector'][:3] for t in successful[0]['response']['trajectories']])
    last_traj = np.array([t['statevector'][:3] for t in successful[-1]['response']['trajectories']])

    ax.scatter(first_traj[0, 0], first_traj[0, 1], first_traj[0, 2],
               color='green', s=150, marker='o', label='Start', edgecolors='black', zorder=5)
    ax.scatter(last_traj[-1, 0], last_traj[-1, 1], last_traj[-1, 2],
               color='red', s=150, marker='s', label='End', edgecolors='black', zorder=5)

    ax.set_xlabel('X [km]')
    ax.set_ylabel('Y [km]')
    ax.set_zlabel('Z [km]')
    ax.set_title(title)
    ax.legend(loc='upper left', fontsize=8)
    ax.grid(True)

    # Set equal aspect ratio for all axes
    all_points = []
    for r in successful:
        traj = np.array([t['statevector'][:3] for t in r['response'].get('trajectories', [])])
        all_points.extend(traj)
    all_points = np.array(all_points)

    max_range = np.array([
        all_points[:, 0].max() - all_points[:, 0].min(),
        all_points[:, 1].max() - all_points[:, 1].min(),
        all_points[:, 2].max() - all_points[:, 2].min()
    ]).max() / 2.0

    mid_x = (all_points[:, 0].max() + all_points[:, 0].min()) / 2.0
    mid_y = (all_points[:, 1].max() + all_points[:, 1].min()) / 2.0
    mid_z = (all_points[:, 2].max() + all_points[:, 2].min()) / 2.0

    ax.set_xlim(mid_x - max_range, mid_x + max_range)
    ax.set_ylim(mid_y - max_range, mid_y + max_range)
    ax.set_zlim(mid_z - max_range, mid_z + max_range)

    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.show()
    plt.close(fig)

    print(f"Combined plot saved: {save_path}")
    return save_path


def plot_all_trajectories(results: list, save_prefix: str = "trajectory") -> list:
    """
    Plot all satellite trajectories and save as individual PNG files.

    Args:
        results: List of result dictionaries from process_satellites() or process_sequential_states()
        save_prefix: Prefix for output filenames

    Returns:
        List of saved plot filenames
    """
    saved_files = []
    successful = [r for r in results if r.get('success')]

    if not successful:
        print("No successful trajectories to plot.")
        return saved_files

    print(f"\nGenerating {len(successful)} individual plot(s)...")

    for result in successful:
        # Support both result formats: propagation_index (sequential) or satellite_index (batch)
        idx = result.get('propagation_index') or result.get('satellite_index', 1)
        save_path = f"{save_prefix}_{idx}.png"

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
        ax.set_title(f'Trajectory {idx}')
        ax.legend()
        ax.grid(True)

        # Set equal aspect ratio for all axes
        max_range = np.array([
            traj[:, 0].max() - traj[:, 0].min(),
            traj[:, 1].max() - traj[:, 1].min(),
            traj[:, 2].max() - traj[:, 2].min()
        ]).max() / 2.0

        mid_x = (traj[:, 0].max() + traj[:, 0].min()) / 2.0
        mid_y = (traj[:, 1].max() + traj[:, 1].min()) / 2.0
        mid_z = (traj[:, 2].max() + traj[:, 2].min()) / 2.0

        ax.set_xlim(mid_x - max_range, mid_x + max_range)
        ax.set_ylim(mid_y - max_range, mid_y + max_range)
        ax.set_zlim(mid_z - max_range, mid_z + max_range)

        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.show()
        plt.close(fig)

        saved_files.append(save_path)
        print(f"  Saved: {save_path}")

    return saved_files
