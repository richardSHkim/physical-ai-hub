#!/usr/bin/env bash
# CONTAINER: leisaac
#
# Piper 제로 포즈 시각화 (정책 없이)
#
# 변경할 상수:
set -a
source "$(dirname "$0")/../../envs/.env.leisaac"
set +a

ZERO_TASK="${ZERO_TASK:-${LEISAAC_TASK}}"
ZERO_TASK_TYPE="${ZERO_TASK_TYPE:-piperleader}"
LEISAAC_DEVICE="${LEISAAC_DEVICE:-cuda:0}"
LEISAAC_ENABLE_CAMERAS="${LEISAAC_ENABLE_CAMERAS:-1}"
LEISAAC_HEADLESS="${LEISAAC_HEADLESS:-${ISAAC_HEADLESS:-1}}"

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

exec "${PYTHON_BIN}" scripts/evaluation/piper_zero_pose.py \
    --task "${ZERO_TASK}" \
    --task_type "${ZERO_TASK_TYPE}" \
    "${APP_ARGS[@]}" \
    "${KIT_ARGS[@]}" \
    "$@"
