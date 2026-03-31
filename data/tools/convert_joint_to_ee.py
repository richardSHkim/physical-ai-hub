"""Convert a joint-based Piper LeRobot v3.0 dataset to end-effector pose space.

For each frame, applies forward kinematics (FK) to convert the 6 joint angles
in ``action`` and ``observation.state`` into (x, y, z, rx, ry, rz) end-effector
poses (meters + radians).  The gripper dimension is kept as-is.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

# ---------------------------------------------------------------------------
# FK helper
# ---------------------------------------------------------------------------

# Allow importing piper_sdk from the robots/piper venv even when running with
# a different interpreter.
_PIPER_SITE = Path(__file__).resolve().parents[2] / "robots" / "piper" / ".venv"
for _candidate in sorted(_PIPER_SITE.glob("lib/python*/site-packages")):
    if str(_candidate) not in sys.path:
        sys.path.insert(0, str(_candidate))

from piper_sdk.kinematics.piper_fk import C_PiperForwardKinematics  # noqa: E402

_MM_TO_M = 0.001
_DEG_TO_RAD = math.pi / 180.0

EE_FEATURE_NAMES = ["x", "y", "z", "rx", "ry", "rz", "gripper.pos"]


def _fk_to_ee(fk: C_PiperForwardKinematics, joints_rad: list[float]) -> list[float]:
    """Run FK and return EE pose as [x_m, y_m, z_m, rx_rad, ry_rad, rz_rad]."""
    link_poses = fk.CalFK(joints_rad)
    ee = link_poses[-1]  # [x_mm, y_mm, z_mm, rx_deg, ry_deg, rz_deg]
    return [
        ee[0] * _MM_TO_M,
        ee[1] * _MM_TO_M,
        ee[2] * _MM_TO_M,
        ee[3] * _DEG_TO_RAD,
        ee[4] * _DEG_TO_RAD,
        ee[5] * _DEG_TO_RAD,
    ]


def convert_column(
    fk: C_PiperForwardKinematics,
    values: np.ndarray,
) -> np.ndarray:
    """Convert an (N, 7) joint array to (N, 7) EE-pose array."""
    assert values.shape[1] == 7, f"Expected 7 columns, got {values.shape[1]}"
    out = np.empty_like(values)
    for i in range(len(values)):
        ee = _fk_to_ee(fk, values[i, :6].tolist())
        out[i, :6] = ee
        out[i, 6] = values[i, 6]  # gripper passthrough
    return out


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

QUANTILES = {"q01": 0.01, "q10": 0.10, "q50": 0.50, "q90": 0.90, "q99": 0.99}


def compute_feature_stats(values: np.ndarray) -> dict:
    """Compute per-dimension stats matching LeRobot stats.json format."""
    stats: dict = {
        "min": values.min(axis=0).tolist(),
        "max": values.max(axis=0).tolist(),
        "mean": values.mean(axis=0).tolist(),
        "std": values.std(axis=0).tolist(),
        "count": [int(values.shape[0])],
    }
    for name, q in QUANTILES.items():
        stats[name] = np.quantile(values, q, axis=0).tolist()
    return stats


def compute_episode_stats(
    values: np.ndarray,
    episode_indices: np.ndarray,
) -> dict[int, dict]:
    """Compute per-episode stats for a feature."""
    per_ep: dict[int, dict] = {}
    for ep_idx in np.unique(episode_indices):
        mask = episode_indices == ep_idx
        per_ep[int(ep_idx)] = compute_feature_stats(values[mask])
    return per_ep


# ---------------------------------------------------------------------------
# Dataset conversion
# ---------------------------------------------------------------------------


def convert_dataset(src: Path, dst: Path, dh_is_offset: int = 0x01) -> None:
    if dst.exists():
        raise FileExistsError(f"Destination already exists: {dst}")

    src_info = json.loads((src / "meta" / "info.json").read_text())
    if src_info.get("codebase_version") != "v3.0":
        raise ValueError("Only v3.0 datasets are supported.")

    fk = C_PiperForwardKinematics(dh_is_offset)

    # --- Read all data parquet files ---
    data_dir = src / "data"
    parquet_files = sorted(data_dir.rglob("*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(f"No parquet files in {data_dir}")

    tables = [pq.read_table(p) for p in parquet_files]
    table = pa.concat_tables(tables) if len(tables) > 1 else tables[0]

    actions = np.array(table.column("action").to_pylist(), dtype=np.float32)
    states = np.array(table.column("observation.state").to_pylist(), dtype=np.float32)
    episode_indices = np.array(table.column("episode_index").to_pylist(), dtype=np.int64).squeeze()

    print(f"Converting {len(actions)} frames ({len(np.unique(episode_indices))} episodes)...")

    ee_actions = convert_column(fk, actions)
    ee_states = convert_column(fk, states)

    # --- Build new parquet table ---
    new_columns: dict[str, pa.Array] = {}
    for name in table.column_names:
        if name == "action":
            new_columns[name] = pa.array(ee_actions.tolist(), type=pa.list_(pa.float32()))
        elif name == "observation.state":
            new_columns[name] = pa.array(ee_states.tolist(), type=pa.list_(pa.float32()))
        else:
            new_columns[name] = table.column(name)

    new_table = pa.table(new_columns)

    # --- Write data parquet(s) mirroring source layout ---
    dst.mkdir(parents=True, exist_ok=True)
    for pq_path in parquet_files:
        rel = pq_path.relative_to(src)
        out_path = dst / rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
    # For simplicity, write the full concatenated table to the first file path
    first_rel = parquet_files[0].relative_to(src)
    pq.write_table(new_table, dst / first_rel)

    # --- Symlink videos ---
    src_videos = src / "videos"
    if src_videos.exists():
        dst_videos = dst / "videos"
        dst_videos.symlink_to(src_videos.resolve())
        print(f"Symlinked videos → {src_videos.resolve()}")

    # --- Update info.json ---
    new_info = json.loads(json.dumps(src_info))
    for key in ("action", "observation.state"):
        new_info["features"][key]["names"] = list(EE_FEATURE_NAMES)
    meta_dir = dst / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    (meta_dir / "info.json").write_text(json.dumps(new_info, indent=4))

    # --- Copy tasks ---
    src_tasks = src / "meta" / "tasks.parquet"
    if src_tasks.exists():
        shutil.copy2(src_tasks, meta_dir / "tasks.parquet")

    # --- Compute & write global stats ---
    src_stats = json.loads((src / "meta" / "stats.json").read_text())
    new_stats = dict(src_stats)
    new_stats["action"] = compute_feature_stats(ee_actions)
    new_stats["observation.state"] = compute_feature_stats(ee_states)
    (meta_dir / "stats.json").write_text(json.dumps(new_stats, indent=4))

    # --- Copy & update episode metadata ---
    src_episodes_dir = src / "meta" / "episodes"
    if src_episodes_dir.exists():
        dst_episodes_dir = meta_dir / "episodes"
        action_ep_stats = compute_episode_stats(ee_actions, episode_indices)
        state_ep_stats = compute_episode_stats(ee_states, episode_indices)

        for ep_pq_path in sorted(src_episodes_dir.rglob("*.parquet")):
            ep_table = pq.read_table(ep_pq_path)
            records = ep_table.to_pylist()

            for record in records:
                ep_idx = int(record["episode_index"])
                # Replace action and state stats columns
                for col_name in list(record.keys()):
                    if col_name.startswith("stats/action/"):
                        stat_key = col_name.split("stats/action/")[1]
                        if ep_idx in action_ep_stats and stat_key in action_ep_stats[ep_idx]:
                            record[col_name] = action_ep_stats[ep_idx][stat_key]
                    elif col_name.startswith("stats/observation.state/"):
                        stat_key = col_name.split("stats/observation.state/")[1]
                        if ep_idx in state_ep_stats and stat_key in state_ep_stats[ep_idx]:
                            record[col_name] = state_ep_stats[ep_idx][stat_key]

            new_ep_table = pa.Table.from_pylist(records, schema=ep_table.schema)
            rel = ep_pq_path.relative_to(src / "meta" / "episodes")
            out_path = dst_episodes_dir / rel
            out_path.parent.mkdir(parents=True, exist_ok=True)
            pq.write_table(new_ep_table, out_path)

    print(f"Done. Converted dataset written to {dst}")

    # --- Quick sanity check ---
    sample_state = ee_states[0]
    print(f"\nSanity check — first frame EE state:")
    print(f"  xyz (m):   {sample_state[:3]}")
    print(f"  rpy (rad): {sample_state[3:6]}")
    print(f"  gripper:   {sample_state[6]}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert joint-based Piper dataset to EE pose space.")
    parser.add_argument("--src", type=Path, required=True, help="Source joint-based dataset root.")
    parser.add_argument("--dst", type=Path, required=True, help="Destination EE-pose dataset root.")
    parser.add_argument(
        "--dh-is-offset",
        type=lambda x: int(x, 0),
        default=0x01,
        help="DH parameter offset flag (default: 0x01).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    convert_dataset(
        src=args.src.expanduser().resolve(),
        dst=args.dst.expanduser().resolve(),
        dh_is_offset=args.dh_is_offset,
    )
