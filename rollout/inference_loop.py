from __future__ import annotations

import argparse
import importlib
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
    def __init__(
        self,
        client: OpenPIWebsocketClient,
        *,
        fps: float,
        blend: int,
        use_lipo: bool,
        lipo_time_delay: int,
        lipo_epsilon_blending: float,
        lipo_epsilon_path: float,
        solver_factory: Any | None = None,
    ) -> None:
        self._client = client
        self._dt = 1.0 / fps
        self._blend = blend
        self._use_lipo = use_lipo
        self._lipo_time_delay = lipo_time_delay
        self._lipo_epsilon_blending = lipo_epsilon_blending
        self._lipo_epsilon_path = lipo_epsilon_path
        self._solver_factory = solver_factory

        self._prev_output_chunk: Any | None = None
        self._current_exec_chunk: Any | None = None
        self._lipo_solver: Any | None = None
        self._raw_chunk_size: int | None = None
        self._execution_horizon: int = 0
        self._step_in_cycle: int = 0

        self.last_response: dict[str, Any] | None = None
        self.last_infer_latency_ms: float | None = None
        self.last_lipo_solve_ms: float | None = None

    @property
    def blend(self) -> int:
        return self._blend

    @property
    def raw_chunk_size(self) -> int | None:
        return self._raw_chunk_size

    @property
    def execution_horizon(self) -> int:
        return self._execution_horizon

    def _build_lipo_solver(self, chunk_size: int) -> Any:
        if self._solver_factory is not None:
            return self._solver_factory(
                chunk_size=chunk_size,
                blending_horizon=self._blend,
                action_dim=7,
                len_time_delay=self._lipo_time_delay,
                dt=self._dt,
                epsilon_blending=self._lipo_epsilon_blending,
                epsilon_path=self._lipo_epsilon_path,
            )

        try:
            action_lipo_module = importlib.import_module("action_lipo")
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "LiPo is enabled, but `action_lipo` could not be imported. "
                "Install the piper uv environment dependencies first."
            ) from exc
        except Exception as exc:
            raise RuntimeError(
                "LiPo is enabled, but importing `action_lipo` failed. "
                "Check that LiPo dependencies such as cvxpy, osqp, and scipy are installed."
            ) from exc

        return action_lipo_module.ActionLiPo(
            solver="osqp",
            chunk_size=chunk_size,
            blending_horizon=self._blend,
            action_dim=7,
            len_time_delay=self._lipo_time_delay,
            dt=self._dt,
            epsilon_blending=self._lipo_epsilon_blending,
            epsilon_path=self._lipo_epsilon_path,
        )

    def _validate_chunk(self, action_chunk: Any) -> None:
        chunk_size = int(action_chunk.shape[0])
        if self._blend >= chunk_size:
            raise ValueError(
                f"--blend must be smaller than the policy chunk size, got blend={self._blend}, chunk_size={chunk_size}"
            )
        if self._use_lipo and self._lipo_time_delay >= self._blend:
            raise ValueError(
                "--lipo-time-delay must satisfy 0 <= time_delay < blend when LiPo is enabled, "
                f"got time_delay={self._lipo_time_delay}, blend={self._blend}"
            )
        if self._raw_chunk_size is not None and chunk_size != self._raw_chunk_size:
            raise ValueError(
                "Variable action chunk sizes are not supported by the overlap-replan rollout, "
                f"got previous chunk size {self._raw_chunk_size} and new chunk size {chunk_size}."
            )

    def _start_new_cycle(self, observation: dict[str, Any]) -> bool:
        infer_start = time.perf_counter()
        response = self._client.infer(observation)
        action_chunk = action_dict_to_vector(response)
        self.last_response = response
        self.last_infer_latency_ms = (time.perf_counter() - infer_start) * 1000.0
        self.last_lipo_solve_ms = None

        if action_chunk.ndim == 1:
            self._current_exec_chunk = action_chunk[None, :].copy()
            self._execution_horizon = 1
            self._step_in_cycle = 0
            self._raw_chunk_size = 1
            self._prev_output_chunk = None
            return True

        self._validate_chunk(action_chunk)
        self._raw_chunk_size = int(action_chunk.shape[0])
        self._execution_horizon = self._raw_chunk_size - self._blend

        output_chunk = action_chunk.copy()
        if self._use_lipo:
            if self._lipo_solver is None:
                self._lipo_solver = self._build_lipo_solver(self._raw_chunk_size)
            solve_start = time.perf_counter()
            solved_chunk, _ = self._lipo_solver.solve(
                output_chunk,
                self._prev_output_chunk if self._prev_output_chunk is not None else output_chunk,
                len_past_actions=self._blend if self._prev_output_chunk is not None else 0,
            )
            self.last_lipo_solve_ms = (time.perf_counter() - solve_start) * 1000.0
            if solved_chunk is None:
                raise RuntimeError("LiPo solve failed while processing the action chunk.")
            output_chunk = solved_chunk

        self._current_exec_chunk = output_chunk.copy()
        self._prev_output_chunk = output_chunk.copy()
        self._step_in_cycle = 0
        return True

    def reset(self) -> None:
        self._prev_output_chunk = None
        self._current_exec_chunk = None
        self._lipo_solver = None
        self._raw_chunk_size = None
        self._execution_horizon = 0
        self._step_in_cycle = 0
        self.last_response = None
        self.last_infer_latency_ms = None
        self.last_lipo_solve_ms = None
        self._client.reset()

    def pop_action(self, observation: dict[str, Any]) -> tuple[Any, bool]:
        fetched_new_chunk = False
        if self._current_exec_chunk is None or self._step_in_cycle >= self._execution_horizon:
            fetched_new_chunk = self._start_new_cycle(observation)

        if self._current_exec_chunk is None:
            raise RuntimeError("No action chunk is available for execution.")

        action = self._current_exec_chunk[self._step_in_cycle].copy()
        self._step_in_cycle += 1
        return action, fetched_new_chunk

    def remaining_in_cycle(self) -> int:
        return max(self._execution_horizon - self._step_in_cycle, 0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run real-robot Piper rollout against an OpenPI websocket server.")
    parser.add_argument("--host", default="127.0.0.1", help="OpenPI websocket host.")
    parser.add_argument("--port", type=int, default=8000, help="OpenPI websocket port.")
    parser.add_argument("--api-key", default=None, help="Optional API key for the OpenPI server.")
    parser.add_argument("--task", required=True, help="Natural-language task prompt sent to the policy.")
    parser.add_argument("--fps", type=float, default=10.0, help="Robot control frequency in Hz.")
    parser.add_argument("--blend", type=int, default=2, help="Overlap size between consecutive action chunks.")
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
    parser.add_argument("--use-lipo", action="store_true", help="Use LiPo smoothing across overlapped action chunks.")
    parser.add_argument(
        "--lipo-time-delay",
        type=int,
        default=1,
        help="LiPo time delay used when smoothing overlapped chunks.",
    )
    parser.add_argument(
        "--lipo-epsilon-blending",
        type=float,
        default=0.02,
        help="LiPo epsilon bound for the blending region.",
    )
    parser.add_argument(
        "--lipo-epsilon-path",
        type=float,
        default=0.003,
        help="LiPo epsilon bound outside the blending region.",
    )
    return parser.parse_args()


def run_rollout(args: argparse.Namespace) -> None:
    if args.fps <= 0:
        raise ValueError(f"--fps must be > 0, got {args.fps}")
    if args.blend <= 0:
        raise ValueError(f"--blend must be > 0, got {args.blend}")

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
    chunk_buffer = ActionChunkBuffer(
        client,
        fps=args.fps,
        blend=args.blend,
        use_lipo=args.use_lipo,
        lipo_time_delay=args.lipo_time_delay,
        lipo_epsilon_blending=args.lipo_epsilon_blending,
        lipo_epsilon_path=args.lipo_epsilon_path,
    )

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
                remaining_in_cycle = chunk_buffer.remaining_in_cycle()
                infer_ms = (
                    f"{chunk_buffer.last_infer_latency_ms:.1f}"
                    if chunk_buffer.last_infer_latency_ms is not None and fetched_new_chunk
                    else "-"
                )
                lipo_solve_ms = (
                    f"{chunk_buffer.last_lipo_solve_ms:.1f}"
                    if args.use_lipo and chunk_buffer.last_lipo_solve_ms is not None and fetched_new_chunk
                    else "-"
                )
                logger.info(
                    "step=%d fetched_chunk=%s remaining_in_cycle=%d infer_ms=%s lipo_solve_ms=%s chunk_size=%s execution_horizon=%d blend=%d",
                    step,
                    fetched_new_chunk,
                    remaining_in_cycle,
                    infer_ms,
                    lipo_solve_ms,
                    chunk_buffer.raw_chunk_size,
                    chunk_buffer.execution_horizon,
                    chunk_buffer.blend,
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
