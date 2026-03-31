#!/usr/bin/env bash
# CONTAINER: piper
#
# 변경할 상수:
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

set -a
source "${PROJECT_ROOT}/envs/.env.piper"
source "${PROJECT_ROOT}/envs/.env.openpi"
set +a

OPENPI_HOST="${OPENPI_HOST:-127.0.0.1}"
OPENPI_PORT="${OPENPI_PORT:-8000}"
ROLLOUT_TASK="${ROLLOUT_TASK:-${DATASET_SINGLE_TASK}}"
ROLLOUT_NUM_STEPS="${ROLLOUT_NUM_STEPS:-0}"
ROLLOUT_LOG_EVERY="${ROLLOUT_LOG_EVERY:-10}"
ROLLOUT_FPS="${ROLLOUT_FPS:-30}"
ROLLOUT_ACTIONS_PER_CHUNK="${ROLLOUT_ACTIONS_PER_CHUNK:-50}"
ROLLOUT_CHUNK_SIZE_THRESHOLD="${ROLLOUT_CHUNK_SIZE_THRESHOLD:-0.5}"
ROLLOUT_AGGREGATE_FN="${ROLLOUT_AGGREGATE_FN:-weighted_average}"
ROLLOUT_OBSERVATION_STATE_EPSILON="${ROLLOUT_OBSERVATION_STATE_EPSILON:-1.0}"
ROLLOUT_CAN_NAME="${ROLLOUT_CAN_NAME:-can_follower}"
ROLLOUT_ROBOT_ID="${ROLLOUT_ROBOT_ID:-piper_follower_01}"
ROLLOUT_SPEED_RATIO="${ROLLOUT_SPEED_RATIO:-100}"
ROLLOUT_GRIPPER_OPENING_M="${ROLLOUT_GRIPPER_OPENING_M:-0.07}"
ROLLOUT_STARTUP_ENABLE_TIMEOUT_S="${ROLLOUT_STARTUP_ENABLE_TIMEOUT_S:-5.0}"
ROLLOUT_MAX_RELATIVE_TARGET="${ROLLOUT_MAX_RELATIVE_TARGET:-}"
ROLLOUT_USE_EE_POSE="${ROLLOUT_USE_EE_POSE:-false}"
# EE pose mode disables smoothing by default: EndPoseCtrl has its own trajectory planning.
if [[ "${ROLLOUT_USE_EE_POSE}" == "true" ]]; then
    ROLLOUT_JOINT_ALPHA="${ROLLOUT_JOINT_ALPHA:-1.0}"
    ROLLOUT_GRIPPER_ALPHA="${ROLLOUT_GRIPPER_ALPHA:-1.0}"
else
    ROLLOUT_JOINT_ALPHA="${ROLLOUT_JOINT_ALPHA:-0.6}"
    ROLLOUT_GRIPPER_ALPHA="${ROLLOUT_GRIPPER_ALPHA:-0.6}"
fi
ROLLOUT_PLOT_OUTPUT="${ROLLOUT_PLOT_OUTPUT:-outputs/rollout/piper_action_trace.png}"
ROLLOUT_CSV_OUTPUT="${ROLLOUT_CSV_OUTPUT:-}"
ROLLOUT_PLOT_CHUNK_TRANSITIONS="${ROLLOUT_PLOT_CHUNK_TRANSITIONS:-false}"
ROLLOUT_SHOW_PLOT="${ROLLOUT_SHOW_PLOT:-false}"

if [[ -n "${ROLLOUT_BLEND:-}" ]]; then
    echo "warning: ROLLOUT_BLEND is deprecated and ignored. Use ROLLOUT_ACTIONS_PER_CHUNK / ROLLOUT_CHUNK_SIZE_THRESHOLD instead." >&2
fi

ARGS=(
    --host "${OPENPI_HOST}"
    --port "${OPENPI_PORT}"
    --task "${ROLLOUT_TASK}"
    --fps "${ROLLOUT_FPS}"
    --actions-per-chunk "${ROLLOUT_ACTIONS_PER_CHUNK}"
    --chunk-size-threshold "${ROLLOUT_CHUNK_SIZE_THRESHOLD}"
    --aggregate-fn "${ROLLOUT_AGGREGATE_FN}"
    --observation-state-epsilon "${ROLLOUT_OBSERVATION_STATE_EPSILON}"
    --num-steps "${ROLLOUT_NUM_STEPS}"
    --log-every "${ROLLOUT_LOG_EVERY}"
    --can-name "${ROLLOUT_CAN_NAME}"
    --robot-id "${ROLLOUT_ROBOT_ID}"
    --base-serial "${RS_BASE_SERIAL}"
    --wrist-serial "${RS_WRIST_SERIAL}"
    --width "${RS_WIDTH}"
    --height "${RS_HEIGHT}"
    --camera-fps "${RS_FPS}"
    --speed-ratio "${ROLLOUT_SPEED_RATIO}"
    --gripper-opening-m "${ROLLOUT_GRIPPER_OPENING_M}"
    --joint-alpha "${ROLLOUT_JOINT_ALPHA}"
    --gripper-alpha "${ROLLOUT_GRIPPER_ALPHA}"
    --startup-enable-timeout-s "${ROLLOUT_STARTUP_ENABLE_TIMEOUT_S}"
)

if [[ "${ROLLOUT_USE_EE_POSE}" == "true" ]]; then
    ARGS+=(--use-ee-pose)
fi

if [[ "${RS_USE_DEPTH}" == "true" ]]; then
    ARGS+=(--use-depth)
fi

if [[ -n "${ROLLOUT_MAX_RELATIVE_TARGET}" ]]; then
    ARGS+=(--max-relative-target "${ROLLOUT_MAX_RELATIVE_TARGET}")
fi

if [[ -n "${ROLLOUT_PLOT_OUTPUT}" ]]; then
    ARGS+=(--plot-output "${ROLLOUT_PLOT_OUTPUT}")
fi

if [[ -n "${ROLLOUT_CSV_OUTPUT}" ]]; then
    ARGS+=(--csv-output "${ROLLOUT_CSV_OUTPUT}")
fi

if [[ "${ROLLOUT_PLOT_CHUNK_TRANSITIONS}" == "true" ]]; then
    ARGS+=(--plot-chunk-transitions)
fi

if [[ "${ROLLOUT_SHOW_PLOT}" == "true" ]]; then
    ARGS+=(--show-plot)
fi

exec python3 -m rollout.inference_loop "${ARGS[@]}" "$@"
