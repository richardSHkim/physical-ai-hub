#!/usr/bin/env bash
# CONTAINER: leisaac
#
# LeIsaac 시뮬레이션에서 정책 평가 실행
#
# 변경할 상수:
set -a
source "$(dirname "$0")/../../envs/.env.leisaac"
set +a

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LEISAAC_OUTPUT_ROOT="${LEISAAC_OUTPUT_ROOT:-outputs/leisaac}"
EVAL_TASK="${EVAL_TASK:-${LEISAAC_TASK}}"
EVAL_POLICY_TYPE="${EVAL_POLICY_TYPE:-openpi}"
EVAL_POLICY_HOST="${EVAL_POLICY_HOST:-localhost}"
EVAL_POLICY_PORT="${EVAL_POLICY_PORT:-8000}"
EVAL_LANGUAGE_INSTRUCTION="${EVAL_LANGUAGE_INSTRUCTION:-Lift the red cube up.}"
EVAL_VIDEO_DIR="${EVAL_VIDEO_DIR:-${LEISAAC_OUTPUT_ROOT}/policy_inference_videos}"
LEISAAC_DEVICE="${LEISAAC_DEVICE:-cuda:0}"
LEISAAC_ENABLE_CAMERAS="${LEISAAC_ENABLE_CAMERAS:-1}"
LEISAAC_HEADLESS="${LEISAAC_HEADLESS:-${ISAAC_HEADLESS:-1}}"

if [[ "${EVAL_VIDEO_DIR}" != /* ]]; then
    EVAL_VIDEO_DIR="${PROJECT_ROOT}/${EVAL_VIDEO_DIR}"
fi

LEISAAC_ROOT="$(cd "$(dirname "$0")/../../simulation/leisaac" && pwd)"
[ ! -x "${PYTHON_BIN}" ] && PYTHON_BIN="python"
export PYTHONPATH="${LEISAAC_ROOT}/source/leisaac:${PYTHONPATH:-}"
export LEISAAC_ASSETS_ROOT

cd "${LEISAAC_ROOT}"

KIT_ARGS=()
[ "${LIVESTREAM_MODE}" != "0" ] && KIT_ARGS=("--kit_args=--/app/livestream/outDirectory=${LIVESTREAM_OUT_DIR}")
APP_ARGS=(--device "${LEISAAC_DEVICE}" --livestream "${LIVESTREAM_MODE}")

case "${LEISAAC_ENABLE_CAMERAS,,}" in
    1|true|yes|on) APP_ARGS+=(--enable_cameras) ;;
esac

case "${LEISAAC_HEADLESS,,}" in
    1|true|yes|on) APP_ARGS+=(--headless) ;;
esac

exec "${PYTHON_BIN}" scripts/evaluation/policy_inference.py \
    --task "${EVAL_TASK}" \
    --policy_type "${EVAL_POLICY_TYPE}" \
    --policy_host "${EVAL_POLICY_HOST}" \
    --policy_port "${EVAL_POLICY_PORT}" \
    --policy_language_instruction "${EVAL_LANGUAGE_INSTRUCTION}" \
    --save_eval_video_dir "${EVAL_VIDEO_DIR}" \
    "${APP_ARGS[@]}" \
    "${KIT_ARGS[@]}" \
    "$@"
