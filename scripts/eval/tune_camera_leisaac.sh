#!/usr/bin/env bash
# CONTAINER: leisaac
#
# Piper 손목 카메라 오프셋 인터랙티브 튜닝
#
# 변경할 상수:
set -a
source "$(dirname "$0")/../../envs/.env.leisaac"
set +a

TUNE_TASK="${TUNE_TASK:-LeIsaac-PiPER-LiftCube-v0}"
TUNE_TASK_TYPE="${TUNE_TASK_TYPE:-piperleader}"

LEISAAC_ROOT="$(cd "$(dirname "$0")/../../eval/leisaac" && pwd)"
[ ! -x "${PYTHON_BIN}" ] && PYTHON_BIN="python"
export PYTHONPATH="${LEISAAC_ROOT}/source/leisaac:${PYTHONPATH:-}"
export LEISAAC_ASSETS_ROOT

cd "${LEISAAC_ROOT}"

KIT_ARGS=()
[ "${LIVESTREAM_MODE}" != "0" ] && KIT_ARGS=("--kit_args=--/app/livestream/outDirectory=${LIVESTREAM_OUT_DIR}")

exec "${PYTHON_BIN}" scripts/evaluation/piper_wrist_camera_tuner.py \
    --task "${TUNE_TASK}" \
    --task_type "${TUNE_TASK_TYPE}" \
    --device cuda:0 \
    --enable_cameras \
    --headless \
    --livestream "${LIVESTREAM_MODE}" \
    "${KIT_ARGS[@]}" \
    "$@"
