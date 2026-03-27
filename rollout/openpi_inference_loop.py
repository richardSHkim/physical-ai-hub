#!/usr/bin/env python3

"""Run a real-robot PiPER inference loop against an OpenPI websocket server."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import numpy as np

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
OPENPI_CLIENT_SRC = REPO_ROOT / "vla" / "openpi" / "packages" / "openpi-client" / "src"
PIPER_SRC = REPO_ROOT / "robots" / "piper"
for extra_path in (OPENPI_CLIENT_SRC, PIPER_SRC):
    if str(extra_path) not in sys.path:
        sys.path.insert(0, str(extra_path))

from openpi_client import image_tools  # noqa: E402
from openpi_client import websocket_client_policy  # noqa: E402

if TYPE_CHECKING:
    from lerobot_robot_piper_follower.piper_follower import PiperFollower

JOINT_KEYS = tuple(f"joint_{idx}.pos" for idx in range(1, 7))
DEFAULT_PROMPT = "Put banana into basket."


@dataclass(frozen=True)
class ServerEndpoint:
    host: str
    port: int | None


def parse_server_endpoint(server_url: str) -> ServerEndpoint:
    raw = server_url.strip()
    if not raw:
        raise ValueError("server_url must not be empty.")

    has_explicit_scheme = "://" in raw
    parsed = urlparse(raw if has_explicit_scheme else f"ws://{raw}")

    if parsed.scheme not in {"http", "https", "ws", "wss"}:
        raise ValueError(f"Unsupported server URL scheme: {parsed.scheme!r}")
    if not parsed.hostname:
        raise ValueError(f"Could not parse hostname from server URL: {server_url!r}")
    if parsed.path not in {"", "/"}:
        raise ValueError("server_url must not include a path; use host[:port] or ws://host[:port].")

    if not has_explicit_scheme or parsed.scheme == "http":
        host = parsed.hostname
    elif parsed.scheme in {"ws", "wss"}:
        host = f"{parsed.scheme}://{parsed.hostname}"
    else:
        host = f"wss://{parsed.hostname}"

    return ServerEndpoint(host=host, port=parsed.port or 8000)


def build_robot(
    *,
    can_name: str,
    base_serial: str,
    wrist_serial: str,
    width: int,
    height: int,
    fps: int,
    use_depth: bool,
    speed_ratio: int,
    max_relative_target: float,
) -> PiperFollower:
    from lerobot.cameras.realsense.configuration_realsense import RealSenseCameraConfig
    from lerobot_robot_piper_follower.config_piper_follower import PiperFollowerConfig
    from lerobot_robot_piper_follower.piper_follower import PiperFollower

    config = PiperFollowerConfig(
        can_name=can_name,
        id="piper_follower_openpi",
        speed_ratio=speed_ratio,
        max_relative_target=max_relative_target,
        disable_torque_on_disconnect=False,
        cameras={
            "base": RealSenseCameraConfig(
                serial_number_or_name=base_serial,
                width=width,
                height=height,
                fps=fps,
                use_depth=use_depth,
            ),
            "wrist": RealSenseCameraConfig(
                serial_number_or_name=wrist_serial,
                width=width,
                height=height,
                fps=fps,
                use_depth=use_depth,
            ),
        },
    )
    return PiperFollower(config)


def observation_to_openpi(
    observation: dict[str, Any],
    *,
    prompt: str,
    image_size: int,
    base_camera_key: str,
    wrist_camera_key: str,
) -> dict[str, Any]:
    try:
        base_image = np.asarray(observation[base_camera_key])
        wrist_image = np.asarray(observation[wrist_camera_key])
    except KeyError as exc:
        missing = exc.args[0]
        raise KeyError(f"Missing camera observation {missing!r}. Available keys: {sorted(observation)}") from exc

    state = np.asarray([float(observation[key]) for key in (*JOINT_KEYS, "gripper.pos")], dtype=np.float32)

    return {
        "images": {
            "base": image_tools.convert_to_uint8(image_tools.resize_with_pad(base_image, image_size, image_size)),
            "wrist": image_tools.convert_to_uint8(image_tools.resize_with_pad(wrist_image, image_size, image_size)),
        },
        "state": state,
        "prompt": prompt,
    }


def action_chunk_to_robot_actions(action_chunk: np.ndarray, *, max_actions: int) -> list[dict[str, float]]:
    actions = np.asarray(action_chunk, dtype=np.float32)
    if actions.ndim != 2 or actions.shape[1] < 7:
        raise ValueError(f"Expected action chunk with shape [T, 7+], got {actions.shape}.")

    robot_actions: list[dict[str, float]] = []
    for row in actions[:max_actions]:
        robot_actions.append(
            {
                **{joint_key: float(row[idx]) for idx, joint_key in enumerate(JOINT_KEYS)},
                "gripper.pos": float(np.clip(row[6], 0.0, 1.0)),
            }
        )
    return robot_actions


def sleep_to_rate(loop_start: float, hz: float) -> None:
    if hz <= 0:
        return
    period = 1.0 / hz
    remaining = period - (time.monotonic() - loop_start)
    if remaining > 0:
        time.sleep(remaining)


def run(args: argparse.Namespace) -> None:
    endpoint = parse_server_endpoint(args.server_url)
    prompt = args.prompt.strip()
    if not prompt:
        raise ValueError("prompt must not be empty.")

    policy = websocket_client_policy.WebsocketClientPolicy(
        host=endpoint.host,
        port=endpoint.port,
        api_key=args.api_key,
    )
    logger.info("Connected to OpenPI server at %s (metadata=%s)", args.server_url, policy.get_server_metadata())

    robot = build_robot(
        can_name=args.can_name,
        base_serial=args.base_serial,
        wrist_serial=args.wrist_serial,
        width=args.width,
        height=args.height,
        fps=args.fps,
        use_depth=args.use_depth,
        speed_ratio=args.speed_ratio,
        max_relative_target=args.max_relative_target,
    )

    pending_actions: list[dict[str, float]] = []
    inference_calls = 0
    executed_actions = 0

    try:
        robot.connect()
        logger.info("PiPER robot connected on %s", args.can_name)

        while True:
            if args.max_steps is not None and executed_actions >= args.max_steps:
                logger.info("Reached max_steps=%d; stopping loop.", args.max_steps)
                break

            loop_start = time.monotonic()

            if not pending_actions:
                observation = robot.get_observation()
                openpi_observation = observation_to_openpi(
                    observation,
                    prompt=prompt,
                    image_size=args.image_size,
                    base_camera_key=args.base_camera_key,
                    wrist_camera_key=args.wrist_camera_key,
                )
                inference_start = time.monotonic()
                inference_result = policy.infer(openpi_observation)
                inference_ms = (time.monotonic() - inference_start) * 1000.0
                pending_actions = action_chunk_to_robot_actions(
                    inference_result["actions"],
                    max_actions=args.actions_per_inference,
                )
                inference_calls += 1
                logger.info(
                    "Inference %d returned %d actions in %.1f ms",
                    inference_calls,
                    len(pending_actions),
                    inference_ms,
                )

            next_action = pending_actions.pop(0)
            if args.dry_run:
                logger.info("Dry-run action %d: %s", executed_actions + 1, next_action)
            else:
                robot.send_action(next_action)
                logger.info("Executed action %d", executed_actions + 1)
            executed_actions += 1
            sleep_to_rate(loop_start, args.control_hz)

    finally:
        if robot.is_connected:
            robot.disconnect()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-url", default="http://localhost:8000", help="OpenPI server URL or host[:port].")
    parser.add_argument("--api-key", default=None, help="Optional API key for the OpenPI server.")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="Task prompt sent to the policy server.")
    parser.add_argument("--control-hz", type=float, default=10.0, help="Target control loop frequency.")
    parser.add_argument(
        "--actions-per-inference",
        type=int,
        default=1,
        help="How many actions from each returned action chunk to execute before re-querying the server.",
    )
    parser.add_argument("--max-steps", type=int, default=None, help="Stop after this many actions. Default: run forever.")
    parser.add_argument("--dry-run", action="store_true", help="Run inference and log actions without commanding the arm.")
    parser.add_argument("--image-size", type=int, default=224, help="Resize camera frames to this square size.")
    parser.add_argument("--can-name", default="can_follower", help="PiPER follower CAN interface name.")
    parser.add_argument("--base-serial", required=True, help="RealSense serial for the base camera.")
    parser.add_argument("--wrist-serial", required=True, help="RealSense serial for the wrist camera.")
    parser.add_argument("--base-camera-key", default="base", help="Observation key for the base camera.")
    parser.add_argument("--wrist-camera-key", default="wrist", help="Observation key for the wrist camera.")
    parser.add_argument("--width", type=int, default=640, help="Camera capture width.")
    parser.add_argument("--height", type=int, default=480, help="Camera capture height.")
    parser.add_argument("--fps", type=int, default=30, help="Camera capture FPS.")
    parser.add_argument("--use-depth", action="store_true", help="Enable RealSense depth stream.")
    parser.add_argument("--speed-ratio", type=int, default=60, help="PiPER arm speed ratio in [0, 100].")
    parser.add_argument(
        "--max-relative-target",
        type=float,
        default=0.08,
        help="Per-step max joint delta in radians before the robot clips the command.",
    )
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = build_arg_parser().parse_args()
    if args.actions_per_inference <= 0:
        raise ValueError("actions_per_inference must be >= 1.")
    run(args)


if __name__ == "__main__":
    main()
