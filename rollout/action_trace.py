from __future__ import annotations

import csv
import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

_MPL_CONFIG_DIR = Path(tempfile.gettempdir()) / "physical_ai_hub_matplotlib"
_MPL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_MPL_CONFIG_DIR))

JOINT_NAMES = (
    "joint_1.pos",
    "joint_2.pos",
    "joint_3.pos",
    "joint_4.pos",
    "joint_5.pos",
    "joint_6.pos",
    "gripper.pos",
)


@dataclass
class ActionTrace:
    timestamps_s: list[float] = field(default_factory=list)
    actions: list[np.ndarray] = field(default_factory=list)
    new_chunk_times_s: list[float] = field(default_factory=list)
    new_chunk_step_indices: list[int] = field(default_factory=list)
    infer_latency_ms: list[float] = field(default_factory=list)

    def record(
        self,
        *,
        timestamp_s: float,
        step: int,
        action: np.ndarray,
        started_new_chunk: bool,
        infer_latency_ms: float | None,
    ) -> None:
        self.timestamps_s.append(float(timestamp_s))
        self.actions.append(np.asarray(action, dtype=np.float32).copy())
        if started_new_chunk:
            self.new_chunk_times_s.append(float(timestamp_s))
            self.new_chunk_step_indices.append(int(step))
            if infer_latency_ms is not None:
                self.infer_latency_ms.append(float(infer_latency_ms))

    def is_empty(self) -> bool:
        return not self.timestamps_s

    def action_matrix(self) -> np.ndarray:
        if self.is_empty():
            return np.empty((0, len(JOINT_NAMES)), dtype=np.float32)
        return np.stack(self.actions, axis=0)


def save_action_trace_csv(trace: ActionTrace, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    chunk_steps = set(trace.new_chunk_step_indices)
    actions = trace.action_matrix()
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["step", "time_s", *JOINT_NAMES, "new_chunk"])
        for step, (timestamp_s, action) in enumerate(zip(trace.timestamps_s, actions, strict=True)):
            writer.writerow(
                [
                    step,
                    f"{timestamp_s:.6f}",
                    *[f"{float(value):.8f}" for value in action],
                    int(step in chunk_steps),
                ]
            )


def plot_action_trace(
    trace: ActionTrace,
    *,
    output_path: Path | None,
    dpi: int,
    show_plot: bool,
    title: str,
    show_chunk_transitions: bool = False,
) -> None:
    if output_path is None and not show_plot:
        return
    if trace.is_empty():
        logger.warning("No action samples were recorded, skipping plot generation.")
        return

    if not show_plot:
        import matplotlib

        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    times = np.asarray(trace.timestamps_s, dtype=np.float64)
    actions = trace.action_matrix()

    fig, axes = plt.subplots(len(JOINT_NAMES), 1, figsize=(14, 2.25 * len(JOINT_NAMES)), sharex=True)
    axes_array = np.atleast_1d(axes)

    for joint_idx, (ax, joint_name) in enumerate(zip(axes_array, JOINT_NAMES, strict=True)):
        ax.plot(times, actions[:, joint_idx], color="tab:blue", linewidth=1.5)
        if show_chunk_transitions:
            for chunk_time_s in trace.new_chunk_times_s:
                ax.axvline(chunk_time_s, color="red", linewidth=1.0, alpha=0.45)
        ax.set_ylabel(joint_name)
        ax.grid(True, alpha=0.3)

    axes_array[-1].set_xlabel("time [s]")
    chunk_count = len(trace.new_chunk_times_s)
    if show_chunk_transitions:
        fig.suptitle(f"{title}\nRecorded {len(times)} actions, {chunk_count} chunk transitions")
    else:
        fig.suptitle(f"{title}\nRecorded {len(times)} actions")
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.98))

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
        logger.info("Saved action plot to %s", output_path)

    if show_plot:
        plt.show()
    plt.close(fig)
