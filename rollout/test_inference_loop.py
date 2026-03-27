from __future__ import annotations

import unittest

import numpy as np

from rollout.inference_loop import ActionChunkBuffer


class _FakeClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0
        self.metadata = {}
        self.reset_calls = 0

    def infer(self, observation):
        del observation
        response = self._responses[self.calls]
        self.calls += 1
        return {"actions": response}

    def reset(self):
        self.reset_calls += 1


class _FakeLiPoSolver:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls = []

    def solve(self, actions, past_actions, len_past_actions):
        self.calls.append(
            {
                "actions": np.asarray(actions).copy(),
                "past_actions": np.asarray(past_actions).copy(),
                "len_past_actions": len_past_actions,
            }
        )
        solved = np.asarray(actions, dtype=np.float32) + 100.0
        return solved, np.asarray(actions, dtype=np.float32)


class ActionChunkBufferTest(unittest.TestCase):
    def test_overlap_replan_without_lipo_fetches_every_execution_horizon(self):
        chunk_a = np.arange(50 * 7, dtype=np.float32).reshape(50, 7)
        chunk_b = chunk_a + 1000.0
        client = _FakeClient([chunk_a, chunk_b])
        buffer = ActionChunkBuffer(
            client,
            fps=10.0,
            blend=10,
            use_lipo=False,
            lipo_time_delay=3,
            lipo_epsilon_blending=0.02,
            lipo_epsilon_path=0.003,
        )

        first_flags = []
        first_actions = []
        for _ in range(40):
            action, fetched = buffer.pop_action({"obs": 1})
            first_actions.append(action)
            first_flags.append(fetched)

        self.assertEqual(client.calls, 1)
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

    def test_lipo_uses_previous_output_chunk_and_stores_solved_chunk(self):
        chunk_a = np.arange(50 * 7, dtype=np.float32).reshape(50, 7)
        chunk_b = chunk_a + 1000.0
        client = _FakeClient([chunk_a, chunk_b])
        created_solvers = []

        def solver_factory(**kwargs):
            solver = _FakeLiPoSolver(**kwargs)
            created_solvers.append(solver)
            return solver

        buffer = ActionChunkBuffer(
            client,
            fps=10.0,
            blend=10,
            use_lipo=True,
            lipo_time_delay=3,
            lipo_epsilon_blending=0.02,
            lipo_epsilon_path=0.003,
            solver_factory=solver_factory,
        )

        action, fetched = buffer.pop_action({"obs": 1})
        self.assertTrue(fetched)
        np.testing.assert_allclose(action, chunk_a[0] + 100.0)
        self.assertEqual(len(created_solvers), 1)
        self.assertEqual(created_solvers[0].calls[0]["len_past_actions"], 0)

        for _ in range(39):
            buffer.pop_action({"obs": 1})

        next_action, fetched = buffer.pop_action({"obs": 2})
        self.assertTrue(fetched)
        np.testing.assert_allclose(next_action, chunk_b[0] + 100.0)
        self.assertEqual(created_solvers[0].calls[1]["len_past_actions"], 10)
        np.testing.assert_allclose(created_solvers[0].calls[1]["past_actions"], chunk_a + 100.0)

    def test_single_step_action_falls_back_without_overlap(self):
        client = _FakeClient([np.arange(7, dtype=np.float32)])
        buffer = ActionChunkBuffer(
            client,
            fps=10.0,
            blend=10,
            use_lipo=False,
            lipo_time_delay=3,
            lipo_epsilon_blending=0.02,
            lipo_epsilon_path=0.003,
        )

        action, fetched = buffer.pop_action({"obs": 1})
        self.assertTrue(fetched)
        np.testing.assert_allclose(action, np.arange(7, dtype=np.float32))
        self.assertEqual(buffer.execution_horizon, 1)
        self.assertEqual(buffer.remaining_in_cycle(), 0)

    def test_invalid_blend_and_time_delay_are_rejected(self):
        chunk = np.zeros((10, 7), dtype=np.float32)

        blend_client = _FakeClient([chunk])
        blend_buffer = ActionChunkBuffer(
            blend_client,
            fps=10.0,
            blend=10,
            use_lipo=False,
            lipo_time_delay=3,
            lipo_epsilon_blending=0.02,
            lipo_epsilon_path=0.003,
        )
        with self.assertRaisesRegex(ValueError, "blend"):
            blend_buffer.pop_action({"obs": 1})

        delay_client = _FakeClient([chunk])
        delay_buffer = ActionChunkBuffer(
            delay_client,
            fps=10.0,
            blend=4,
            use_lipo=True,
            lipo_time_delay=4,
            lipo_epsilon_blending=0.02,
            lipo_epsilon_path=0.003,
            solver_factory=lambda **kwargs: _FakeLiPoSolver(**kwargs),
        )
        with self.assertRaisesRegex(ValueError, "time_delay"):
            delay_buffer.pop_action({"obs": 1})

    def test_reset_clears_cycle_state(self):
        chunk = np.arange(20 * 7, dtype=np.float32).reshape(20, 7)
        client = _FakeClient([chunk])
        buffer = ActionChunkBuffer(
            client,
            fps=10.0,
            blend=5,
            use_lipo=False,
            lipo_time_delay=3,
            lipo_epsilon_blending=0.02,
            lipo_epsilon_path=0.003,
        )

        buffer.pop_action({"obs": 1})
        buffer.reset()

        self.assertIsNone(buffer.raw_chunk_size)
        self.assertEqual(buffer.execution_horizon, 0)
        self.assertEqual(buffer.remaining_in_cycle(), 0)
        self.assertEqual(client.reset_calls, 1)


if __name__ == "__main__":
    unittest.main()
