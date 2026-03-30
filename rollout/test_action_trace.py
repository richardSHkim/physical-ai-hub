from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from rollout.action_trace import ActionTrace, JOINT_NAMES, plot_action_trace, save_action_trace_csv


class ActionTraceTest(unittest.TestCase):
    def test_record_tracks_prediction_boundaries(self):
        trace = ActionTrace()

        trace.record(
            timestamp_s=0.1,
            step=0,
            action=np.arange(len(JOINT_NAMES), dtype=np.float32),
            fetched_new_chunk=True,
            infer_latency_ms=12.5,
        )
        trace.record(
            timestamp_s=0.2,
            step=1,
            action=np.arange(len(JOINT_NAMES), dtype=np.float32) + 1.0,
            fetched_new_chunk=False,
            infer_latency_ms=None,
        )

        self.assertEqual(trace.timestamps_s, [0.1, 0.2])
        self.assertEqual(trace.new_prediction_times_s, [0.1])
        self.assertEqual(trace.prediction_step_indices, [0])
        self.assertEqual(trace.infer_latency_ms, [12.5])
        self.assertEqual(trace.action_matrix().shape, (2, len(JOINT_NAMES)))

    def test_plot_and_csv_outputs_are_written(self):
        trace = ActionTrace()
        for step in range(4):
            trace.record(
                timestamp_s=step * 0.1,
                step=step,
                action=np.full(len(JOINT_NAMES), step, dtype=np.float32),
                fetched_new_chunk=step in {0, 2},
                infer_latency_ms=5.0 if step in {0, 2} else None,
            )

        with tempfile.TemporaryDirectory() as tmp_dir:
            plot_path = Path(tmp_dir) / "trace.png"
            csv_path = Path(tmp_dir) / "trace.csv"

            plot_action_trace(
                trace,
                output_path=plot_path,
                dpi=100,
                show_plot=False,
                title="test trace",
            )
            save_action_trace_csv(trace, csv_path)

            self.assertTrue(plot_path.exists())
            self.assertGreater(plot_path.stat().st_size, 0)
            self.assertTrue(csv_path.exists())
            csv_lines = csv_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(csv_lines), 5)
            self.assertEqual(
                csv_lines[0],
                "step,time_s,joint_1.pos,joint_2.pos,joint_3.pos,joint_4.pos,joint_5.pos,joint_6.pos,gripper.pos,new_prediction",
            )


if __name__ == "__main__":
    unittest.main()
