#!/usr/bin/env bash
# CONTAINER: piper
# RUN: make rollout-openpi
#
# 변경할 상수:
set -euo pipefail
set -a
source "$(dirname "$0")/../../envs/.env.piper"
source "$(dirname "$0")/../../envs/.env.openpi"
set +a

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PIPER_ROOT="${PROJECT_ROOT}/robots/piper"

SERVER_URL="${SERVER_URL:-http://localhost:${OPENPI_PORT:-8000}}"
ROLLOUT_PROMPT="${ROLLOUT_PROMPT:-${DATASET_SINGLE_TASK:-Put banana into basket.}}"
ROLLOUT_CONTROL_HZ="${ROLLOUT_CONTROL_HZ:-${CONTROL_HZ:-10}}"
ROLLOUT_MAX_STEPS="${ROLLOUT_MAX_STEPS:-}"
ROLLOUT_ACTIONS_PER_INFERENCE="${ROLLOUT_ACTIONS_PER_INFERENCE:-1}"
ROLLOUT_DRY_RUN="${ROLLOUT_DRY_RUN:-false}"

cd "${PROJECT_ROOT}"

ARGS=(
    python rollout/openpi_inference_loop.py
    --server-url "${SERVER_URL}"
    --prompt "${ROLLOUT_PROMPT}"
    --control-hz "${ROLLOUT_CONTROL_HZ}"
    --actions-per-inference "${ROLLOUT_ACTIONS_PER_INFERENCE}"
    --can-name "can_follower"
    --base-serial "${RS_BASE_SERIAL}"
    --wrist-serial "${RS_WRIST_SERIAL}"
    --width "${RS_WIDTH}"
    --height "${RS_HEIGHT}"
    --fps "${RS_FPS}"
    --max-relative-target "0.08"
)

if [[ "${RS_USE_DEPTH}" == "true" ]]; then
    ARGS+=(--use-depth)
fi

if [[ -n "${ROLLOUT_MAX_STEPS}" ]]; then
    ARGS+=(--max-steps "${ROLLOUT_MAX_STEPS}")
fi

if [[ "${ROLLOUT_DRY_RUN}" == "true" ]]; then
    ARGS+=(--dry-run)
fi

exec uv run --project "${PIPER_ROOT}" "${ARGS[@]}" "$@"
