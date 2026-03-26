#!/usr/bin/env python3

from __future__ import annotations

import argparse
from dataclasses import dataclass

import pyrealsense2 as rs


DEFAULT_CAMERAS = {
    "base": "207222072736",
    "wrist": "207522074203",
}


@dataclass(frozen=True)
class CameraRequest:
    label: str
    serial: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Print RealSense intrinsics for the active stream profile. "
            "Defaults match examples/record.sh: 640x480 @ 30 FPS, color only."
        )
    )
    parser.add_argument(
        "--serial",
        action="append",
        dest="serials",
        metavar="LABEL=SERIAL",
        help=(
            "Camera to inspect. Repeatable. Example: --serial base=207222072736 "
            "If omitted, uses the base and wrist serials from examples/record.sh."
        ),
    )
    parser.add_argument("--width", type=int, default=640, help="Requested stream width.")
    parser.add_argument("--height", type=int, default=480, help="Requested stream height.")
    parser.add_argument("--fps", type=int, default=30, help="Requested stream FPS.")
    parser.add_argument(
        "--use-depth",
        action="store_true",
        help="Also enable the depth stream and print its intrinsics.",
    )
    return parser.parse_args()


def parse_camera_requests(serial_args: list[str] | None) -> list[CameraRequest]:
    if not serial_args:
        return [CameraRequest(label, serial) for label, serial in DEFAULT_CAMERAS.items()]

    requests: list[CameraRequest] = []
    for item in serial_args:
        if "=" in item:
            label, serial = item.split("=", 1)
        else:
            label, serial = item, item
        label = label.strip()
        serial = serial.strip()
        if not label or not serial:
            raise ValueError(f"Invalid --serial value: {item!r}")
        requests.append(CameraRequest(label=label, serial=serial))
    return requests


def print_stream_intrinsics(
    profile: rs.pipeline_profile,
    stream_kind: rs.stream,
    label: str,
) -> None:
    stream_profile = profile.get_stream(stream_kind).as_video_stream_profile()
    intr = stream_profile.get_intrinsics()
    print(f"  [{label}]")
    print(f"    width={intr.width}")
    print(f"    height={intr.height}")
    print(f"    fx={intr.fx}")
    print(f"    fy={intr.fy}")
    print(f"    cx={intr.ppx}")
    print(f"    cy={intr.ppy}")
    print(f"    model={intr.model}")
    print(f"    coeffs={list(intr.coeffs)}")


def inspect_camera(camera: CameraRequest, width: int, height: int, fps: int, use_depth: bool) -> None:
    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_device(camera.serial)
    config.enable_stream(rs.stream.color, width, height, rs.format.rgb8, fps)
    if use_depth:
        config.enable_stream(rs.stream.depth, width, height, rs.format.z16, fps)

    print(f"{camera.label}: serial={camera.serial}")
    profile = pipeline.start(config)
    try:
        print_stream_intrinsics(profile, rs.stream.color, "color")
        if use_depth:
            print_stream_intrinsics(profile, rs.stream.depth, "depth")
    finally:
        pipeline.stop()


def main() -> int:
    args = parse_args()
    cameras = parse_camera_requests(args.serials)
    for index, camera in enumerate(cameras):
        if index:
            print()
        inspect_camera(camera, args.width, args.height, args.fps, args.use_depth)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
