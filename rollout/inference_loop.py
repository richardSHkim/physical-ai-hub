from __future__ import annotations

import argparse
import collections
import logging
import time
from typing import Any

from rollout.clients.openpi import OpenPIWebsocketClient
from rollout.piper import (
    PiperHardwareConfig,
    action_dict_to_vector,
    make_piper_follower,
    observation_to_openpi_input,
    vector_to_robot_action,
)

logger = logging.getLogger(__name__)


class ActionChunkBuffer:
    def __init__(self, client: OpenPIWebsocketClient) -> None:
        self._client = client
        self._pending_actions: collections.deque[Any] = collections.deque()
        self.last_response: dict[str, Any] | None = None
        self.last_infer_latency_ms: float | None = None

    def reset(self) -> None:
        self._pending_actions.clear()
        self.last_response = None
        self.last_infer_latency_ms = None
        self._client.reset()

    def pop_action(self, observation: dict[str, Any]) -> tuple[Any, bool]:
        fetched_new_chunk = False
        if not self._pending_actions:
            infer_start = time.perf_counter()
            response = self._client.infer(observation)
            action_chunk = action_dict_to_vector(response)
            self.last_response = response
            self.last_infer_latency_ms = (time.perf_counter() - infer_start) * 1000.0
            if action_chunk.ndim == 1:
                self._pending_actions.append(action_chunk)
            else:
                self._pending_actions.extend(action_chunk)
            fetched_new_chunk = True

        return self._pending_actions.popleft(), fetched_new_chunk

    def pending_count(self) -> int:
        return len(self._pending_actions)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run real-robot Piper rollout against an OpenPI websocket server.")
    parser.add_argument("--host", default="127.0.0.1", help="OpenPI websocket host.")
    parser.add_argument("--port", type=int, default=8000, help="OpenPI websocket port.")
    parser.add_argument("--api-key", default=None, help="Optional API key for the OpenPI server.")
    parser.add_argument("--task", required=True, help="Natural-language task prompt sent to the policy.")
    parser.add_argument("--fps", type=float, default=10.0, help="Robot control frequency in Hz.")
    parser.add_argument(
        "--num-steps",
        type=int,
        default=0,
        help="Maximum rollout steps. Use 0 to keep running until interrupted.",
    )
    parser.add_argument("--log-every", type=int, default=10, help="Emit one status log every N control steps.")
    parser.add_argument("--can-name", default="can_follower", help="PiPER follower CAN interface name.")
    parser.add_argument("--robot-id", default="piper_follower_01", help="LeRobot robot id.")
    parser.add_argument("--base-serial", required=True, help="RealSense serial for the base camera.")
    parser.add_argument("--wrist-serial", required=True, help="RealSense serial for the wrist camera.")
    parser.add_argument("--width", type=int, default=640, help="RealSense width.")
    parser.add_argument("--height", type=int, default=480, help="RealSense height.")
    parser.add_argument("--camera-fps", type=int, default=30, help="RealSense capture FPS.")
    parser.add_argument("--use-depth", action="store_true", help="Enable RealSense depth streams.")
    parser.add_argument("--speed-ratio", type=int, default=60, help="PiPER speed ratio in [0, 100].")
    parser.add_argument("--gripper-opening-m", type=float, default=0.07, help="Max gripper opening in meters.")
    parser.add_argument(
        "--startup-enable-timeout-s",
        type=float,
        default=5.0,
        help="Timeout while enabling the arm on connect.",
    )
    parser.add_argument(
        "--max-relative-target",
        type=float,
        default=None,
        help="Optional per-step joint delta clamp in radians.",
    )
    return parser.parse_args()


def run_rollout(args: argparse.Namespace) -> None:
    if args.fps <= 0:
        raise ValueError(f"--fps must be > 0, got {args.fps}")

    client = OpenPIWebsocketClient(host=args.host, port=args.port, api_key=args.api_key)
    robot = make_piper_follower(
        PiperHardwareConfig(
            can_name=args.can_name,
            base_serial=args.base_serial,
            wrist_serial=args.wrist_serial,
            width=args.width,
            height=args.height,
            fps=args.camera_fps,
            use_depth=args.use_depth,
            robot_id=args.robot_id,
            speed_ratio=args.speed_ratio,
            gripper_opening_m=args.gripper_opening_m,
            startup_enable_timeout_s=args.startup_enable_timeout_s,
            max_relative_target=args.max_relative_target,
        )
    )
    chunk_buffer = ActionChunkBuffer(client)

    logger.info("Connected to OpenPI server at %s:%d", args.host, args.port)
    if client.metadata:
        logger.info("Server metadata: %s", client.metadata)

    robot.connect()
    logger.info("PiPER follower connected. Starting rollout for task: %s", args.task)

    control_period_s = 1.0 / args.fps
    step = 0
    rollout_start = time.perf_counter()

    try:
        while args.num_steps <= 0 or step < args.num_steps:
            step_start = time.perf_counter()
            raw_observation = robot.get_observation()
            policy_observation = observation_to_openpi_input(raw_observation, args.task)

            action_vector, fetched_new_chunk = chunk_buffer.pop_action(policy_observation)
            robot.send_action(vector_to_robot_action(action_vector))

            if args.log_every > 0 and step % args.log_every == 0:
                pending = chunk_buffer.pending_count()
                infer_ms = (
                    f"{chunk_buffer.last_infer_latency_ms:.1f}"
                    if chunk_buffer.last_infer_latency_ms is not None and fetched_new_chunk
                    else "-"
                )
                logger.info(
                    "step=%d fetched_chunk=%s pending_actions=%d infer_ms=%s",
                    step,
                    fetched_new_chunk,
                    pending,
                    infer_ms,
                )

            elapsed = time.perf_counter() - step_start
            remaining = control_period_s - elapsed
            if remaining > 0:
                time.sleep(remaining)
            else:
                logger.warning("Control loop overran by %.1f ms at step %d", -remaining * 1000.0, step)
            step += 1
    finally:
        chunk_buffer.reset()
        robot.disconnect()
        logger.info("Rollout stopped after %d steps in %.1f s", step, time.perf_counter() - rollout_start)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    run_rollout(parse_args())


if __name__ == "__main__":
    main()
