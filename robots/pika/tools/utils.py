"""Shared PIKA Sense utilities used by check_single.py and check_dual.py."""

import math


def quaternion_to_rpy(x: float, y: float, z: float, w: float) -> tuple[float, float, float]:
    """Convert quaternion (x, y, z, w) to roll-pitch-yaw Euler angles."""
    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = math.atan2(sinr_cosp, cosr_cosp)

    sinp = 2.0 * (w * y - z * x)
    if abs(sinp) >= 1.0:
        pitch = math.copysign(math.pi / 2.0, sinp)
    else:
        pitch = math.asin(sinp)

    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = math.atan2(siny_cosp, cosy_cosp)
    return roll, pitch, yaw


def format_pose_6d(pose_obj) -> str:
    """Format a PIKA pose object (or dict of poses) as a human-readable string."""
    if pose_obj is None:
        return "none"

    if isinstance(pose_obj, dict):
        if not pose_obj:
            return "{}"
        parts = []
        for name, p in pose_obj.items():
            if p is None:
                parts.append(f"{name}: none")
                continue

            x, y, z = p.position
            qx, qy, qz, qw = p.rotation
            roll, pitch, yaw = quaternion_to_rpy(qx, qy, qz, qw)
            parts.append(
                f"{name}: x={x:.4f}, y={y:.4f}, z={z:.4f}, "
                f"roll={roll:.4f}, pitch={pitch:.4f}, yaw={yaw:.4f}"
            )
        return " | ".join(parts)

    x, y, z = pose_obj.position
    qx, qy, qz, qw = pose_obj.rotation
    roll, pitch, yaw = quaternion_to_rpy(qx, qy, qz, qw)
    return (
        f"x={x:.4f}, y={y:.4f}, z={z:.4f}, "
        f"roll={roll:.4f}, pitch={pitch:.4f}, yaw={yaw:.4f}"
    )
