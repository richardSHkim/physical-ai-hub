#!/usr/bin/env python3
"""Compare SDK endpose feedback vs offline FK calculation in real-time.

Reads joint angles from the live robot, computes FK, and prints the
difference against the SDK's own endpose reading.  Use this to verify
whether the FK solver (C_PiperForwardKinematics) matches the robot
controller's internal FK before trusting offline-converted datasets.

Usage (inside piper container):
    python robots/piper/tools/compare_fk.py --can-name can_follower

Move the robot around and observe the error columns.  Press Ctrl-C to stop.
"""

from __future__ import annotations

import argparse
import math
import time

from piper_sdk import C_PiperForwardKinematics, C_PiperInterface_V2

_001MM_TO_M = 1.0 / 1_000_000.0
_001DEG_TO_RAD = math.pi / 180_000.0
_MM_TO_M = 0.001
_DEG_TO_RAD = math.pi / 180.0


def read_joint_rad(arm: C_PiperInterface_V2) -> list[float]:
    joints = arm.GetArmJointMsgs().joint_state
    return [
        float(joints.joint_1) * _001DEG_TO_RAD,
        float(joints.joint_2) * _001DEG_TO_RAD,
        float(joints.joint_3) * _001DEG_TO_RAD,
        float(joints.joint_4) * _001DEG_TO_RAD,
        float(joints.joint_5) * _001DEG_TO_RAD,
        float(joints.joint_6) * _001DEG_TO_RAD,
    ]


def read_endpose_m_rad(arm: C_PiperInterface_V2) -> tuple[float, ...]:
    ep = arm.GetArmEndPoseMsgs().end_pose
    return (
        float(ep.X_axis) * _001MM_TO_M,
        float(ep.Y_axis) * _001MM_TO_M,
        float(ep.Z_axis) * _001MM_TO_M,
        float(ep.RX_axis) * _001DEG_TO_RAD,
        float(ep.RY_axis) * _001DEG_TO_RAD,
        float(ep.RZ_axis) * _001DEG_TO_RAD,
    )


def fk_to_ee_m_rad(fk: C_PiperForwardKinematics, joints_rad: list[float]) -> tuple[float, ...]:
    ee = fk.CalFK(joints_rad)[-1]  # [x_mm, y_mm, z_mm, rx_deg, ry_deg, rz_deg]
    return (
        ee[0] * _MM_TO_M,
        ee[1] * _MM_TO_M,
        ee[2] * _MM_TO_M,
        ee[3] * _DEG_TO_RAD,
        ee[4] * _DEG_TO_RAD,
        ee[5] * _DEG_TO_RAD,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--can-name", default="can_follower")
    parser.add_argument("--dh-is-offset", type=lambda x: int(x, 0), default=0x01)
    parser.add_argument("--period", type=float, default=0.5, help="Print period in seconds (default: 0.5)")
    args = parser.parse_args()

    arm = C_PiperInterface_V2(args.can_name)
    arm.ConnectPort()
    # Disable active control so the robot can be moved by hand.
    while arm.DisablePiper():
        time.sleep(0.01)
    fk = C_PiperForwardKinematics(args.dh_is_offset)
    time.sleep(0.2)
    print("Robot disabled — you can move it by hand.")

    labels = ["x(m)", "y(m)", "z(m)", "rx(rad)", "ry(rad)", "rz(rad)"]

    print("Move the robot around. Press Ctrl-C to stop.\n")
    print(f"{'':>8s}  {'SDK endpose':>48s}  {'FK computed':>48s}  {'error':>48s}")
    print("-" * 160)

    try:
        while True:
            joints = read_joint_rad(arm)
            sdk = read_endpose_m_rad(arm)
            computed = fk_to_ee_m_rad(fk, joints)

            errs = [c - s for c, s in zip(computed, sdk)]
            xyz_err_mm = [e * 1000 for e in errs[:3]]

            sdk_str = "  ".join(f"{v:+.5f}" for v in sdk)
            fk_str = "  ".join(f"{v:+.5f}" for v in computed)
            err_str = (
                f"{xyz_err_mm[0]:+.2f}mm  {xyz_err_mm[1]:+.2f}mm  {xyz_err_mm[2]:+.2f}mm  "
                f"{math.degrees(errs[3]):+.3f}°  {math.degrees(errs[4]):+.3f}°  {math.degrees(errs[5]):+.3f}°"
            )

            print(f"  sdk:    {sdk_str}")
            print(f"  fk:     {fk_str}")
            print(f"  error:  {err_str}")
            print()

            time.sleep(args.period)
    except KeyboardInterrupt:
        print("\nDone.")
    finally:
        arm.DisconnectPort()


if __name__ == "__main__":
    main()
