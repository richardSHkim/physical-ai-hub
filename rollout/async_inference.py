from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

from rollout.clients.base import PolicyClient
from rollout.piper import action_dict_to_vector

logger = logging.getLogger(__name__)

AggregateFn = Callable[[np.ndarray, np.ndarray], np.ndarray]

AGGREGATE_FUNCTIONS: dict[str, AggregateFn] = {
    "weighted_average": lambda old, new: 0.3 * old + 0.7 * new,
    "latest_only": lambda old, new: new.copy(),
    "average": lambda old, new: 0.5 * old + 0.5 * new,
    "conservative": lambda old, new: 0.7 * old + 0.3 * new,
}


def get_aggregate_function(name: str) -> AggregateFn:
    if name not in AGGREGATE_FUNCTIONS:
        available = ", ".join(sorted(AGGREGATE_FUNCTIONS))
        raise ValueError(f"Unknown aggregate function '{name}'. Available: {available}")
    return AGGREGATE_FUNCTIONS[name]


@dataclass
class TimedObservation:
    timestamp: float
    timestep: int
    observation: dict[str, Any]
    must_go: bool = False


@dataclass
class TimedAction:
    timestamp: float
    timestep: int
    action: np.ndarray
    is_refresh: bool = False
    infer_latency_ms: float | None = None


class AsyncInferenceRunner:
    def __init__(
        self,
        client: PolicyClient,
        *,
        fps: float,
        actions_per_chunk: int,
        chunk_size_threshold: float,
        aggregate_fn_name: str,
        observation_state_epsilon: float = 1.0,
    ) -> None:
        if fps <= 0:
            raise ValueError(f"--fps must be > 0, got {fps}")
        if actions_per_chunk <= 0:
            raise ValueError(f"--actions-per-chunk must be > 0, got {actions_per_chunk}")
        if not 0.0 <= chunk_size_threshold <= 1.0:
            raise ValueError(
                f"--chunk-size-threshold must be in [0, 1], got {chunk_size_threshold}"
            )
        if observation_state_epsilon < 0.0:
            raise ValueError(
                f"--observation-state-epsilon must be >= 0, got {observation_state_epsilon}"
            )

        self._client = client
        self._dt = 1.0 / fps
        self._actions_per_chunk = int(actions_per_chunk)
        self._chunk_size_threshold = float(chunk_size_threshold)
        self._aggregate_fn = get_aggregate_function(aggregate_fn_name)
        self._observation_state_epsilon = float(observation_state_epsilon)

        self._shutdown = threading.Event()
        self._worker = threading.Thread(
            target=self._run,
            name="rollout-async-inference",
            daemon=True,
        )

        self._action_lock = threading.Lock()
        self._action_queue: list[TimedAction] = []
        self._latest_action = -1
        self._action_chunk_size = -1
        self._raw_chunk_size: int | None = None
        self.action_queue_size: list[int] = []

        self._observation_lock = threading.Lock()
        self._pending_observation: TimedObservation | None = None
        self._observation_ready = threading.Event()
        self._last_processed_observation: TimedObservation | None = None
        self._predicted_timesteps: set[int] = set()

        self._must_go = threading.Event()
        self._must_go.set()

        self._error_lock = threading.Lock()
        self._worker_error: BaseException | None = None

        self.last_infer_latency_ms: float | None = None

    @property
    def raw_chunk_size(self) -> int | None:
        return self._raw_chunk_size

    @property
    def action_chunk_size(self) -> int:
        return self._action_chunk_size

    @property
    def latest_action_timestep(self) -> int:
        return self._latest_action

    def start(self) -> None:
        if self._worker.is_alive():
            return
        self._shutdown.clear()
        self._worker.start()

    def stop(self) -> None:
        self._shutdown.set()
        self._observation_ready.set()
        if self._worker.is_alive():
            self._worker.join(timeout=2.0)
        self._client.reset()

    def actions_available(self) -> bool:
        self._raise_if_worker_failed()
        with self._action_lock:
            return bool(self._action_queue)

    def pop_action(self) -> TimedAction:
        self._raise_if_worker_failed()
        with self._action_lock:
            if not self._action_queue:
                raise RuntimeError("No action is available for execution.")
            self.action_queue_size.append(len(self._action_queue))
            action = self._action_queue.pop(0)
            self._latest_action = action.timestep
            return action

    def ready_for_observation(self) -> bool:
        self._raise_if_worker_failed()
        with self._action_lock:
            if self._action_chunk_size <= 0:
                return True
            return len(self._action_queue) / self._action_chunk_size <= self._chunk_size_threshold

    def should_force_observation(self) -> bool:
        self._raise_if_worker_failed()
        with self._action_lock:
            queue_empty = not self._action_queue
        return self._must_go.is_set() and queue_empty

    def submit_observation(self, observation: TimedObservation) -> bool:
        self._raise_if_worker_failed()
        if self._shutdown.is_set():
            raise RuntimeError("Async inference runner is not running.")
        if not self._should_enqueue_observation(observation):
            return False

        with self._observation_lock:
            self._pending_observation = observation
            self._observation_ready.set()

        if observation.must_go:
            self._must_go.clear()

        return True

    def queue_size(self) -> int:
        with self._action_lock:
            return len(self._action_queue)

    def _raise_if_worker_failed(self) -> None:
        with self._error_lock:
            error = self._worker_error
        if error is not None:
            raise RuntimeError("Async inference worker failed.") from error

    def _run(self) -> None:
        while not self._shutdown.is_set():
            self._observation_ready.wait(timeout=0.1)
            if self._shutdown.is_set():
                return

            with self._observation_lock:
                observation = self._pending_observation
                self._pending_observation = None
                self._observation_ready.clear()

            if observation is None:
                continue

            try:
                infer_start = time.perf_counter()
                response = self._client.infer(observation.observation)
                infer_latency_ms = (time.perf_counter() - infer_start) * 1000.0
                timed_actions = self._response_to_timed_actions(
                    response,
                    observation=observation,
                    infer_latency_ms=infer_latency_ms,
                )
                with self._observation_lock:
                    self._last_processed_observation = observation
                    self._predicted_timesteps.add(observation.timestep)

                self.last_infer_latency_ms = infer_latency_ms
                self._merge_actions(timed_actions)
                self._must_go.set()
            except BaseException as exc:  # pragma: no cover - exercised via public re-raise path
                logger.exception("Async inference worker crashed.")
                with self._error_lock:
                    self._worker_error = exc
                self._shutdown.set()
                self._observation_ready.set()
                return

    def _response_to_timed_actions(
        self,
        response: dict[str, Any],
        *,
        observation: TimedObservation,
        infer_latency_ms: float,
    ) -> list[TimedAction]:
        action_chunk = action_dict_to_vector(response)
        if action_chunk.ndim == 1:
            action_chunk = action_chunk[None, :]
        action_chunk = action_chunk[: self._actions_per_chunk]

        chunk_size = int(action_chunk.shape[0])
        self._raw_chunk_size = chunk_size
        self._action_chunk_size = max(self._action_chunk_size, chunk_size)

        timed_actions: list[TimedAction] = []
        for index, action in enumerate(action_chunk):
            timed_actions.append(
                TimedAction(
                    timestamp=observation.timestamp + index * self._dt,
                    timestep=observation.timestep + index,
                    action=np.asarray(action, dtype=np.float32).copy(),
                    is_refresh=index == 0,
                    infer_latency_ms=infer_latency_ms if index == 0 else None,
                )
            )
        return timed_actions

    def _should_enqueue_observation(self, observation: TimedObservation) -> bool:
        if observation.must_go:
            return True

        with self._observation_lock:
            last_processed = self._last_processed_observation
            predicted_timesteps = set(self._predicted_timesteps)

        if last_processed is None:
            return True
        if observation.timestep in predicted_timesteps:
            return False
        if self._observations_similar(observation, last_processed):
            return False
        return True

    def _observations_similar(self, left: TimedObservation, right: TimedObservation) -> bool:
        left_state = np.asarray(left.observation.get("state"))
        right_state = np.asarray(right.observation.get("state"))
        if left_state.size == 0 or right_state.size == 0:
            return False
        return float(np.linalg.norm(left_state - right_state)) < self._observation_state_epsilon

    def _merge_actions(self, incoming_actions: list[TimedAction]) -> None:
        with self._action_lock:
            future_actions = {
                action.timestep: action
                for action in self._action_queue
                if action.timestep > self._latest_action
            }

            for new_action in incoming_actions:
                if new_action.timestep <= self._latest_action:
                    continue

                existing_action = future_actions.get(new_action.timestep)
                if existing_action is None:
                    future_actions[new_action.timestep] = new_action
                    continue

                infer_latency_ms = existing_action.infer_latency_ms
                if new_action.is_refresh and new_action.infer_latency_ms is not None:
                    infer_latency_ms = new_action.infer_latency_ms

                future_actions[new_action.timestep] = TimedAction(
                    timestamp=new_action.timestamp,
                    timestep=new_action.timestep,
                    action=self._aggregate_fn(existing_action.action, new_action.action).astype(
                        np.float32,
                        copy=False,
                    ),
                    is_refresh=existing_action.is_refresh or new_action.is_refresh,
                    infer_latency_ms=infer_latency_ms,
                )

            self._action_queue = [future_actions[timestep] for timestep in sorted(future_actions)]
