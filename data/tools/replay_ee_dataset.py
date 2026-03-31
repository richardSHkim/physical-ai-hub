"""Replay an EE-pose Piper dataset on the real robot using EndPoseCtrl.

Reads actions from a LeRobot v3.0 dataset whose action space is
(x, y, z, rx, ry, rz, gripper.pos) in meters/radians, and sends them to the
Piper arm via ``EndPoseCtrl`` (MOVE P mode).
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

# Allow importing piper_sdk from the robots/piper venv.
_PIPER_SITE = Path(__file__).resolve().parents[2] / "robots" / "piper" / ".venv"
for _candidate in sorted(_PIPER_SITE.glob("lib/python*/site-packages")):
    if str(_candidate) not in sys.path:
        sys.path.insert(0, str(_candidate))

from piper_sdk import C_PiperInterface_V2  # noqa: E402

M_TO_001MM = 1_000_000.0
RAD_TO_001DEG = 180_000.0 / math.pi


def connect_arm(can_name: str, speed_ratio: int) -> C_PiperInterface_V2:
    arm = C_PiperInterface_V2(can_name)
    arm.ConnectPort()

    deadline = time.time() + 5.0
    while time.time() < deadline:
        if arm.EnablePiper():
            break
        time.sleep(0.05)
    else:
        raise RuntimeError("PiPER enable timeout")

    # MOVE P (position/cartesian) mode
    arm.MotionCtrl_2(0x01, 0x00, speed_ratio, 0x00)
    # Initialize gripper
    arm.GripperCtrl(0, 1000, 0x01, 0x00)
    return arm


def send_ee_action(
    arm: C_PiperInterface_V2,
    x: float,
    y: float,
    z: float,
    rx: float,
    ry: float,
    rz: float,
    gripper: float,
    gripper_opening_m: float = 0.07,
    gripper_effort: int = 1000,
    speed_ratio: int = 60,
) -> None:
    arm.MotionCtrl_2(0x01, 0x00, speed_ratio, 0x00)
    arm.EndPoseCtrl(
        int(round(x * M_TO_001MM)),
        int(round(y * M_TO_001MM)),
        int(round(z * M_TO_001MM)),
        int(round(rx * RAD_TO_001DEG)),
        int(round(ry * RAD_TO_001DEG)),
        int(round(rz * RAD_TO_001DEG)),
    )
    stroke_001mm = int(round(max(0.0, min(1.0, gripper)) * gripper_opening_m * M_TO_001MM))
    arm.GripperCtrl(abs(stroke_001mm), gripper_effort, 0x01, 0x00)


def load_episode(dataset_path: Path, episode: int) -> np.ndarray:
    """Load actions for a single episode from a v3.0 dataset."""
    parquet_files = sorted((dataset_path / "data").rglob("*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(f"No parquet files in {dataset_path / 'data'}")

    tables = [pq.read_table(p) for p in parquet_files]
    import pyarrow as pa

    table = pa.concat_tables(tables) if len(tables) > 1 else tables[0]

    episode_indices = np.array(table.column("episode_index").to_pylist()).squeeze()
    mask = episode_indices == episode
    if not mask.any():
        available = sorted(set(episode_indices.tolist()))
        raise ValueError(f"Episode {episode} not found. Available: {available}")

    actions = np.array(table.column("action").to_pylist(), dtype=np.float64)
    return actions[mask]


def replay(
    dataset_path: Path,
    episode: int,
    can_name: str,
    fps: int,
    speed_ratio: int,
    gripper_opening_m: float,
    gripper_effort: int,
    dry_run: bool,
) -> None:
    actions = load_episode(dataset_path, episode)
    print(f"Loaded episode {episode}: {len(actions)} frames @ {fps} fps")
    print(f"  EE range x: [{actions[:,0].min():.4f}, {actions[:,0].max():.4f}] m")
    print(f"  EE range z: [{actions[:,2].min():.4f}, {actions[:,2].max():.4f}] m")

    if dry_run:
        print("\n[DRY RUN] Printing first 5 actions:")
        for i, a in enumerate(actions[:5]):
            print(f"  [{i}] xyz=({a[0]:.4f}, {a[1]:.4f}, {a[2]:.4f}) "
                  f"rpy=({a[3]:.3f}, {a[4]:.3f}, {a[5]:.3f}) grip={a[6]:.3f}")
        print(f"  ... ({len(actions) - 5} more frames)")
        return

    arm = connect_arm(can_name, speed_ratio)
    print(f"Connected to PiPER on {can_name} (MOVE P mode, speed={speed_ratio}%)")

    dt = 1.0 / fps
    try:
        for i, action in enumerate(actions):
            t0 = time.time()
            send_ee_action(
                arm,
                x=action[0],
                y=action[1],
                z=action[2],
                rx=action[3],
                ry=action[4],
                rz=action[5],
                gripper=action[6],
                gripper_opening_m=gripper_opening_m,
                gripper_effort=gripper_effort,
                speed_ratio=speed_ratio,
            )
            elapsed = time.time() - t0
            sleep_time = dt - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

            if (i + 1) % 30 == 0 or i == len(actions) - 1:
                print(f"  Frame {i + 1}/{len(actions)}")
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        arm.DisconnectPort()
        print("Disconnected.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay EE-pose dataset on Piper robot.")
    parser.add_argument("--dataset", type=Path, required=True, help="Path to EE-pose dataset root.")
    parser.add_argument("--episode", type=int, default=0, help="Episode index to replay (default: 0).")
    parser.add_argument("--can", type=str, default="can_follower", help="CAN interface name.")
    parser.add_argument("--fps", type=int, default=30, help="Target replay FPS (default: 30).")
    parser.add_argument("--speed-ratio", type=int, default=60, help="Motor speed ratio 0-100 (default: 60).")
    parser.add_argument("--gripper-opening-m", type=float, default=0.07, help="Max gripper opening in meters.")
    parser.add_argument("--gripper-effort", type=int, default=1000, help="Gripper effort.")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without sending to robot.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    replay(
        dataset_path=args.dataset.expanduser().resolve(),
        episode=args.episode,
        can_name=args.can,
        fps=args.fps,
        speed_ratio=args.speed_ratio,
        gripper_opening_m=args.gripper_opening_m,
        gripper_effort=args.gripper_effort,
        dry_run=args.dry_run,
    )
