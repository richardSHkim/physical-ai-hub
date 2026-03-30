from __future__ import annotations

import threading
import time
import unittest

import numpy as np

from rollout.inference_loop import ActionChunkBuffer, ActionSmoother


class _FakeClient:
    def __init__(self, responses, delays=None):
        self._responses = list(responses)
        self._delays = list(delays or [0.0] * len(self._responses))
        self._lock = threading.Lock()
        self.calls = 0
        self.metadata = {}
        self.reset_calls = 0
        self.call_events = [threading.Event() for _ in self._responses]

    def infer(self, observation):
        del observation
        with self._lock:
            call_idx = self.calls
            response = self._responses[call_idx]
            self.calls += 1
            self.call_events[call_idx].set()
            delay = self._delays[call_idx]
        if delay > 0:
            time.sleep(delay)
        return {"actions": response}

    def reset(self):
        self.reset_calls += 1


class ActionChunkBufferTest(unittest.TestCase):
    def test_overlap_replan_fetches_every_execution_horizon(self):
        chunk_a = np.arange(50 * 7, dtype=np.float32).reshape(50, 7)
        chunk_b = chunk_a + 1000.0
        client = _FakeClient([chunk_a, chunk_b])
        buffer = ActionChunkBuffer(
            client,
            fps=10.0,
            blend=10,
        )

        first_flags = []
        first_actions = []
        for _ in range(40):
            action, fetched = buffer.pop_action({"obs": 1})
            first_actions.append(action)
            first_flags.append(fetched)

        self.assertEqual(client.calls, 2)
        self.assertTrue(first_flags[0])
        self.assertTrue(all(not flag for flag in first_flags[1:]))
        np.testing.assert_allclose(np.asarray(first_actions), chunk_a[:40])
        self.assertEqual(buffer.remaining_in_cycle(), 0)

        next_action, fetched = buffer.pop_action({"obs": 2})
        self.assertTrue(fetched)
        self.assertEqual(client.calls, 2)
        np.testing.assert_allclose(next_action, chunk_b[0])
        self.assertEqual(buffer.execution_horizon, 40)
        self.assertEqual(buffer.raw_chunk_size, 50)
        self.assertIsNotNone(buffer.last_prefetch_wait_ms)

    def test_single_step_action_falls_back_without_overlap(self):
        client = _FakeClient([np.arange(7, dtype=np.float32)])
        buffer = ActionChunkBuffer(
            client,
            fps=10.0,
            blend=10,
        )

        action, fetched = buffer.pop_action({"obs": 1})
        self.assertTrue(fetched)
        np.testing.assert_allclose(action, np.arange(7, dtype=np.float32))
        self.assertEqual(buffer.execution_horizon, 1)
        self.assertEqual(buffer.remaining_in_cycle(), 0)

    def test_prefetch_completes_before_cycle_boundary(self):
        chunk_a = np.arange(6 * 7, dtype=np.float32).reshape(6, 7)
        chunk_b = chunk_a + 100.0
        client = _FakeClient([chunk_a, chunk_b], delays=[0.0, 0.15])
        buffer = ActionChunkBuffer(client, fps=10.0, blend=2)

        for _ in range(3):
            buffer.pop_action({"obs": 1})

        self.assertTrue(client.call_events[1].wait(timeout=1.0))
        time.sleep(0.2)
        buffer.pop_action({"obs": 1})

        switch_start = time.perf_counter()
        next_action, fetched = buffer.pop_action({"obs": 2})
        switch_elapsed_ms = (time.perf_counter() - switch_start) * 1000.0

        self.assertTrue(fetched)
        np.testing.assert_allclose(next_action, chunk_b[0])
        self.assertLess(switch_elapsed_ms, 50.0)
        self.assertLess(buffer.last_prefetch_wait_ms or 0.0, 50.0)

    def test_invalid_blend_is_rejected(self):
        chunk = np.zeros((10, 7), dtype=np.float32)

        blend_client = _FakeClient([chunk])
        blend_buffer = ActionChunkBuffer(
            blend_client,
            fps=10.0,
            blend=10,
        )
        with self.assertRaisesRegex(ValueError, "blend"):
            blend_buffer.pop_action({"obs": 1})

    def test_reset_clears_cycle_state(self):
        chunk = np.arange(20 * 7, dtype=np.float32).reshape(20, 7)
        client = _FakeClient([chunk])
        buffer = ActionChunkBuffer(
            client,
            fps=10.0,
            blend=5,
        )

        buffer.pop_action({"obs": 1})
        buffer.reset()

        self.assertIsNone(buffer.raw_chunk_size)
        self.assertEqual(buffer.execution_horizon, 0)
        self.assertEqual(buffer.remaining_in_cycle(), 0)
        self.assertEqual(client.reset_calls, 1)


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
