from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np

from rollout.action_trace import ActionTrace, plot_action_trace, save_action_trace_csv
from rollout.async_inference import AsyncInferenceRunner, TimedObservation
from rollout.clients.openpi import OpenPIWebsocketClient
from rollout.piper import (
    PiperHardwareConfig,
    action_dict_to_vector,
    make_piper_follower,
    observation_to_openpi_input,
    vector_to_robot_action,
)

logger = logging.getLogger(__name__)


class ActionSmoother:
    def __init__(
        self,
        *,
        joint_alpha: float,
        gripper_alpha: float,
    ) -> None:
        self._joint_alpha = float(joint_alpha)
        self._gripper_alpha = float(gripper_alpha)

        if not 0.0 < self._joint_alpha <= 1.0:
            raise ValueError(f"--joint-alpha must be in (0, 1], got {self._joint_alpha}")
        if not 0.0 < self._gripper_alpha <= 1.0:
            raise ValueError(f"--gripper-alpha must be in (0, 1], got {self._gripper_alpha}")

    @property
    def enabled(self) -> bool:
        return self._joint_alpha < 1.0 or self._gripper_alpha < 1.0

    def smooth(self, action: Any, observation: dict[str, Any]) -> Any:
        action_vector = action_dict_to_vector({"actions": action}).astype("float32", copy=True)
        if action_vector.shape != (7,):
            raise ValueError(f"Expected one Piper action with shape (7,), got {action_vector.shape}.")

        measured = np.asarray(
            [
                observation["joint_1.pos"],
                observation["joint_2.pos"],
                observation["joint_3.pos"],
                observation["joint_4.pos"],
                observation["joint_5.pos"],
                observation["joint_6.pos"],
                observation["gripper.pos"],
            ],
            dtype=np.float32,
        )

        smoothed = action_vector.copy()
        smoothed[:6] = measured[:6] + self._joint_alpha * (action_vector[:6] - measured[:6])
        smoothed[6] = measured[6] + self._gripper_alpha * (action_vector[6] - measured[6])
        smoothed[6] = float(np.clip(smoothed[6], 0.0, 1.0))
        return smoothed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run real-robot Piper rollout against an OpenPI websocket server.")
    parser.add_argument("--host", default="127.0.0.1", help="OpenPI websocket host.")
    parser.add_argument("--port", type=int, default=8000, help="OpenPI websocket port.")
    parser.add_argument("--api-key", default=None, help="Optional API key for the OpenPI server.")
    parser.add_argument("--task", required=True, help="Natural-language task prompt sent to the policy.")
    parser.add_argument("--fps", type=float, default=10.0, help="Robot control frequency in Hz.")
    parser.add_argument(
        "--actions-per-chunk",
        type=int,
        default=50,
        help="Maximum number of actions kept from each policy response.",
    )
    parser.add_argument(
        "--chunk-size-threshold",
        type=float,
        default=0.5,
        help="Request a fresh observation when queued actions fall below this fraction of the chunk size.",
    )
    parser.add_argument(
        "--aggregate-fn",
        default="weighted_average",
        choices=("weighted_average", "latest_only", "average", "conservative"),
        help="How to merge overlapping future actions from consecutive policy chunks.",
    )
    parser.add_argument(
        "--observation-state-epsilon",
        type=float,
        default=1.0,
        help="Skip non-forced observations whose state is within this L2 distance of the last processed observation.",
    )
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
        "--joint-alpha",
        type=float,
        default=1.0,
        help="Per-step low-pass blend toward policy joint targets. 1.0 disables smoothing, smaller is smoother/slower.",
    )
    parser.add_argument(
        "--gripper-alpha",
        type=float,
        default=1.0,
        help="Per-step low-pass blend toward policy gripper targets. 1.0 disables smoothing, smaller is smoother/slower.",
    )
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
    parser.add_argument(
        "--plot-output",
        default=None,
        help="Optional path to save a joint-action plot.",
    )
    parser.add_argument(
        "--csv-output",
        default=None,
        help="Optional CSV path for the recorded joint-action time series.",
    )
    parser.add_argument("--plot-dpi", type=int, default=150, help="Saved plot DPI.")
    parser.add_argument(
        "--plot-chunk-transitions",
        action="store_true",
        help="Overlay red vertical lines where the executed action stream switches to a new chunk.",
    )
    parser.add_argument("--show-plot", action="store_true", help="Display the action plot after rollout ends.")
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
    async_runner = AsyncInferenceRunner(
        client,
        fps=args.fps,
        actions_per_chunk=args.actions_per_chunk,
        chunk_size_threshold=args.chunk_size_threshold,
        aggregate_fn_name=args.aggregate_fn,
        observation_state_epsilon=args.observation_state_epsilon,
    )
    action_smoother = ActionSmoother(
        joint_alpha=args.joint_alpha,
        gripper_alpha=args.gripper_alpha,
    )

    logger.info("Connected to OpenPI server at %s:%d", args.host, args.port)
    if client.metadata:
        logger.info("Server metadata: %s", client.metadata)

    robot.connect()
    async_runner.start()
    logger.info("PiPER follower connected. Starting rollout for task: %s", args.task)
    logger.info(
        "Rollout controls: fps=%.1f actions_per_chunk=%d chunk_size_threshold=%.2f aggregate_fn=%s speed_ratio=%d max_relative_target=%s joint_alpha=%.2f gripper_alpha=%.2f",
        args.fps,
        args.actions_per_chunk,
        args.chunk_size_threshold,
        args.aggregate_fn,
        args.speed_ratio,
        args.max_relative_target,
        args.joint_alpha,
        args.gripper_alpha,
    )

    control_period_s = 1.0 / args.fps
    step = 0
    rollout_start = time.perf_counter()
    trace = ActionTrace() if args.plot_output or args.csv_output or args.show_plot else None

    try:
        while args.num_steps <= 0 or step < args.num_steps:
            step_start = time.perf_counter()
            raw_observation = robot.get_observation()

            fetched_new_chunk = False
            infer_latency_ms: float | None = None
            if async_runner.actions_available():
                timed_action = async_runner.pop_action()
                command_vector = action_smoother.smooth(timed_action.action, raw_observation)
                action_timestamp_s = time.perf_counter() - rollout_start
                robot.send_action(vector_to_robot_action(command_vector))
                fetched_new_chunk = timed_action.is_refresh
                infer_latency_ms = timed_action.infer_latency_ms
                if trace is not None:
                    trace.record(
                        timestamp_s=action_timestamp_s,
                        step=step,
                        action=command_vector,
                        started_new_chunk=fetched_new_chunk,
                        infer_latency_ms=infer_latency_ms,
                    )

            observation_accepted = False
            if async_runner.ready_for_observation():
                observation_accepted = async_runner.submit_observation(
                    TimedObservation(
                        timestamp=time.time(),
                        timestep=max(async_runner.latest_action_timestep, 0),
                        observation=observation_to_openpi_input(raw_observation, args.task),
                        must_go=async_runner.should_force_observation(),
                    )
                )

            if args.log_every > 0 and step % args.log_every == 0:
                infer_ms = f"{infer_latency_ms:.1f}" if infer_latency_ms is not None and fetched_new_chunk else "-"
                logger.info(
                    "step=%d fetched_chunk=%s infer_ms=%s queue_size=%d chunk_size=%s observation_accepted=%s latest_action=%d",
                    step,
                    fetched_new_chunk,
                    infer_ms,
                    async_runner.queue_size(),
                    async_runner.raw_chunk_size,
                    observation_accepted,
                    async_runner.latest_action_timestep,
                )

            elapsed = time.perf_counter() - step_start
            remaining = control_period_s - elapsed
            if remaining > 0:
                time.sleep(remaining)
            else:
                logger.warning("Control loop overran by %.1f ms at step %d", -remaining * 1000.0, step)
            step += 1
    except KeyboardInterrupt:
        logger.info("Rollout interrupted by user.")
    finally:
        async_runner.stop()
        robot.disconnect()
        logger.info("Rollout stopped after %d steps in %.1f s", step, time.perf_counter() - rollout_start)
        if trace is not None:
            plot_action_trace(
                trace,
                output_path=Path(args.plot_output) if args.plot_output else None,
                dpi=args.plot_dpi,
                show_plot=args.show_plot,
                title=f"PiPER action trace for task: {args.task}",
                show_chunk_transitions=args.plot_chunk_transitions,
            )
            if args.csv_output:
                csv_output = Path(args.csv_output)
                save_action_trace_csv(trace, csv_output)
                logger.info("Saved action trace CSV to %s", csv_output)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    run_rollout(parse_args())


if __name__ == "__main__":
    main()
