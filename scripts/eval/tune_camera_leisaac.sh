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
LIVESTREAM_MODE="${LIVESTREAM_MODE:-2}"

LEISAAC_ROOT="$(cd "$(dirname "$0")/../../eval/leisaac" && pwd)"

cd "${LEISAAC_ROOT}"

KIT_ARGS=()
if [ "${LIVESTREAM_MODE}" != "0" ]; then
    KIT_ARGS=("--kit_args=--/app/livestream/outDirectory=${LIVESTREAM_OUT_DIR:-/tmp/isaac-livestream}")
fi

exec python scripts/evaluation/piper_wrist_camera_tuner.py \
    --task "${TUNE_TASK}" \
    --task_type "${TUNE_TASK_TYPE}" \
    --device cuda:0 \
    --enable_cameras \
    --headless \
    --livestream "${LIVESTREAM_MODE}" \
    "${KIT_ARGS[@]}" \
    "$@"
