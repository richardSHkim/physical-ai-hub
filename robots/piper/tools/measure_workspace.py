#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Measure PiPER end-effector workspace bounds from live feedback."""

import argparse
import json
import math
import time
from pathlib import Path

from piper_sdk import C_PiperInterface_V2

_001MM_TO_M = 1.0 / 1_000_000.0
_001DEG_TO_RAD = math.pi / 180000.0


def read_endpose_m_rad(arm: C_PiperInterface_V2) -> tuple[float, float, float, float, float, float]:
    end_pose = arm.GetArmEndPoseMsgs().end_pose
    return (
        float(end_pose.X_axis) * _001MM_TO_M,
        float(end_pose.Y_axis) * _001MM_TO_M,
        float(end_pose.Z_axis) * _001MM_TO_M,
        float(end_pose.RX_axis) * _001DEG_TO_RAD,
        float(end_pose.RY_axis) * _001DEG_TO_RAD,
        float(end_pose.RZ_axis) * _001DEG_TO_RAD,
    )


def format_bounds(bounds: dict[str, list[float]]) -> str:
    return (
        "workspace_limits:\n"
        f"  x: [{bounds['x'][0]:.4f}, {bounds['x'][1]:.4f}]\n"
        f"  y: [{bounds['y'][0]:.4f}, {bounds['y'][1]:.4f}]\n"
        f"  z: [{bounds['z'][0]:.4f}, {bounds['z'][1]:.4f}]"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--can-name", default="can_follower", help="PiPER CAN interface name")
    parser.add_argument(
        "--judge-flag",
        action="store_true",
        help="Enable CAN judge flag when creating the PiPER SDK interface",
    )
    parser.add_argument(
        "--period",
        type=float,
        default=0.05,
        help="Sampling period in seconds (default: 0.05 = 20 Hz)",
    )
    parser.add_argument(
        "--print-period",
        type=float,
        default=0.5,
        help="Console refresh period in seconds",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON file path to save the measured bounds on exit",
    )
    parser.add_argument(
        "--margin",
        type=float,
        default=0.0,
        help="Subtract/add this safety margin in meters from the measured min/max before printing",
    )
    args = parser.parse_args()

    if args.period <= 0:
        raise ValueError("period must be > 0")
    if args.print_period <= 0:
        raise ValueError("print-period must be > 0")
    if args.margin < 0:
        raise ValueError("margin must be >= 0")

    arm = C_PiperInterface_V2(args.can_name, args.judge_flag)
    arm.ConnectPort()
    time.sleep(0.2)

    pose = read_endpose_m_rad(arm)
    bounds = {
        "x": [pose[0], pose[0]],
        "y": [pose[1], pose[1]],
        "z": [pose[2], pose[2]],
    }
    sample_count = 1
    started_at = time.time()
    last_print = 0.0

    print("[start] Measuring PiPER workspace from live end-effector feedback.")
    print("[hint] Move the robot through the full safe workspace. Press Ctrl-C to finish.")

    try:
        while True:
            pose = read_endpose_m_rad(arm)
            xyz = {"x": pose[0], "y": pose[1], "z": pose[2]}
            for axis, value in xyz.items():
                bounds[axis][0] = min(bounds[axis][0], value)
                bounds[axis][1] = max(bounds[axis][1], value)
            sample_count += 1

            now = time.time()
            if now - last_print >= args.print_period:
                elapsed = now - started_at
                print(
                    "[run] "
                    f"t={elapsed:6.1f}s "
                    f"xyz=({xyz['x']:+.4f}, {xyz['y']:+.4f}, {xyz['z']:+.4f}) "
                    f"x=[{bounds['x'][0]:+.4f}, {bounds['x'][1]:+.4f}] "
                    f"y=[{bounds['y'][0]:+.4f}, {bounds['y'][1]:+.4f}] "
                    f"z=[{bounds['z'][0]:+.4f}, {bounds['z'][1]:+.4f}]"
                )
                last_print = now

            time.sleep(args.period)
    except KeyboardInterrupt:
        print("\n[stop] Measurement stopped by user.")
    finally:
        arm.DisconnectPort()

    adjusted_bounds = {
        axis: [bounds[axis][0] + args.margin, bounds[axis][1] - args.margin]
        for axis in ("x", "y", "z")
    }

    print(f"[result] samples={sample_count}, duration={time.time() - started_at:.1f}s")
    print("[result] Raw bounds (meters):")
    print(format_bounds(bounds))
    if args.margin > 0:
        print(f"[result] Margin-adjusted bounds with margin={args.margin:.4f} m:")
        print(format_bounds(adjusted_bounds))

    if args.output is not None:
        payload = {
            "can_name": args.can_name,
            "sample_count": sample_count,
            "duration_s": time.time() - started_at,
            "raw_workspace_limits": bounds,
            "margin_m": args.margin,
            "adjusted_workspace_limits": adjusted_bounds,
        }
        args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"[saved] {args.output}")


if __name__ == "__main__":
    main()
