from __future__ import annotations

import threading
import time
import unittest

import numpy as np

from rollout.async_inference import AsyncInferenceRunner, TimedObservation
from rollout.inference_loop import ActionSmoother


class _FakeClient:
    def __init__(self, responses, delays=None):
        self._responses = list(responses)
        self._delays = list(delays or [0.0] * len(self._responses))
        self._lock = threading.Lock()
        self.calls = 0
        self.metadata = {}
        self.reset_calls = 0
        self.call_events = [threading.Event() for _ in self._responses]
        self.observations: list[dict[str, np.ndarray]] = []

    def infer(self, observation):
        with self._lock:
            call_idx = self.calls
            response = self._responses[call_idx]
            delay = self._delays[call_idx]
            self.calls += 1
            self.call_events[call_idx].set()
            self.observations.append(observation)
        if delay > 0:
            time.sleep(delay)
        return {"actions": response}

    def reset(self):
        self.reset_calls += 1


def _observation(step: int, *, must_go: bool = False) -> TimedObservation:
    return TimedObservation(
        timestamp=float(step),
        timestep=step,
        observation={
            "state": np.full(7, step, dtype=np.float32),
        },
        must_go=must_go,
    )


class AsyncInferenceRunnerTest(unittest.TestCase):
    def test_runner_processes_initial_observation_and_exposes_actions(self):
        chunk = np.arange(4 * 7, dtype=np.float32).reshape(4, 7)
        client = _FakeClient([chunk])
        runner = AsyncInferenceRunner(
            client,
            fps=10.0,
            actions_per_chunk=4,
            chunk_size_threshold=0.5,
            aggregate_fn_name="latest_only",
        )
        runner.start()
        try:
            accepted = runner.submit_observation(_observation(0, must_go=True))
            self.assertTrue(accepted)
            self.assertTrue(client.call_events[0].wait(timeout=1.0))

            deadline = time.time() + 1.0
            while not runner.actions_available() and time.time() < deadline:
                time.sleep(0.01)

            self.assertTrue(runner.actions_available())
            popped = [runner.pop_action().action for _ in range(4)]
            np.testing.assert_allclose(np.asarray(popped), chunk)
            self.assertEqual(runner.latest_action_timestep, 3)
            self.assertEqual(runner.raw_chunk_size, 4)
        finally:
            runner.stop()

        self.assertEqual(client.reset_calls, 1)

    def test_runner_threshold_requests_fresh_observation_when_queue_runs_low(self):
        chunk = np.arange(4 * 7, dtype=np.float32).reshape(4, 7)
        client = _FakeClient([chunk])
        runner = AsyncInferenceRunner(
            client,
            fps=10.0,
            actions_per_chunk=4,
            chunk_size_threshold=0.5,
            aggregate_fn_name="latest_only",
        )
        runner.start()
        try:
            runner.submit_observation(_observation(0, must_go=True))
            self.assertTrue(client.call_events[0].wait(timeout=1.0))

            deadline = time.time() + 1.0
            while runner.queue_size() < 4 and time.time() < deadline:
                time.sleep(0.01)

            self.assertFalse(runner.ready_for_observation())
            runner.pop_action()
            self.assertFalse(runner.ready_for_observation())
            runner.pop_action()
            self.assertTrue(runner.ready_for_observation())
        finally:
            runner.stop()

    def test_runner_aggregates_overlapping_future_actions(self):
        chunk_a = np.zeros((3, 7), dtype=np.float32)
        chunk_b = np.full((3, 7), 10.0, dtype=np.float32)
        client = _FakeClient([chunk_a, chunk_b])
        runner = AsyncInferenceRunner(
            client,
            fps=10.0,
            actions_per_chunk=3,
            chunk_size_threshold=1.0,
            aggregate_fn_name="average",
        )
        runner.start()
        try:
            runner.submit_observation(_observation(0, must_go=True))
            self.assertTrue(client.call_events[0].wait(timeout=1.0))
            deadline = time.time() + 1.0
            while runner.queue_size() < 3 and time.time() < deadline:
                time.sleep(0.01)

            runner.submit_observation(_observation(0, must_go=True))
            self.assertTrue(client.call_events[1].wait(timeout=1.0))
            deadline = time.time() + 1.0
            while runner.queue_size() < 3 and time.time() < deadline:
                time.sleep(0.01)

            first_action = runner.pop_action()
            np.testing.assert_allclose(first_action.action, np.full(7, 5.0, dtype=np.float32))
            self.assertTrue(first_action.is_refresh)
            self.assertIsNotNone(first_action.infer_latency_ms)
        finally:
            runner.stop()

    def test_runner_skips_similar_non_forced_observations(self):
        chunk = np.arange(2 * 7, dtype=np.float32).reshape(2, 7)
        client = _FakeClient([chunk])
        runner = AsyncInferenceRunner(
            client,
            fps=10.0,
            actions_per_chunk=2,
            chunk_size_threshold=1.0,
            aggregate_fn_name="latest_only",
            observation_state_epsilon=0.5,
        )
        runner.start()
        try:
            runner.submit_observation(_observation(1, must_go=True))
            self.assertTrue(client.call_events[0].wait(timeout=1.0))

            deadline = time.time() + 1.0
            while runner.queue_size() < 2 and time.time() < deadline:
                time.sleep(0.01)

            accepted = runner.submit_observation(
                TimedObservation(
                    timestamp=2.0,
                    timestep=2,
                    observation={"state": np.full(7, 1.1, dtype=np.float32)},
                    must_go=False,
                )
            )
            self.assertFalse(accepted)
            self.assertEqual(client.calls, 1)
        finally:
            runner.stop()


class ActionSmootherTest(unittest.TestCase):
    def test_smooth_blends_toward_measured_state(self):
        smoother = ActionSmoother(joint_alpha=0.25, gripper_alpha=0.5)
        measured = {
            "joint_1.pos": 0.0,
            "joint_2.pos": 1.0,
            "joint_3.pos": 2.0,
            "joint_4.pos": 3.0,
            "joint_5.pos": 4.0,
            "joint_6.pos": 5.0,
            "gripper.pos": 0.2,
        }
        raw_action = np.asarray([1.0, 3.0, 5.0, 7.0, 9.0, 11.0, 1.0], dtype=np.float32)

        smoothed = smoother.smooth(raw_action, measured)

        np.testing.assert_allclose(
            smoothed,
            np.asarray([0.25, 1.5, 2.75, 4.0, 5.25, 6.5, 0.6], dtype=np.float32),
        )

    def test_smooth_clips_gripper_into_valid_range(self):
        smoother = ActionSmoother(joint_alpha=1.0, gripper_alpha=0.5)
        measured = {
            "joint_1.pos": 0.0,
            "joint_2.pos": 0.0,
            "joint_3.pos": 0.0,
            "joint_4.pos": 0.0,
            "joint_5.pos": 0.0,
            "joint_6.pos": 0.0,
            "gripper.pos": 0.8,
        }
        raw_action = np.asarray([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 2.0], dtype=np.float32)

        smoothed = smoother.smooth(raw_action, measured)

        self.assertEqual(smoothed[6], 1.0)


if __name__ == "__main__":
    unittest.main()
