#!/usr/bin/env bash
# CONTAINER: leisaac
#
# Piper 제로 포즈 시각화 (정책 없이)
#
# 변경할 상수:
set -a
source "$(dirname "$0")/../../envs/.env.leisaac"
set +a

ZERO_TASK="${ZERO_TASK:-LeIsaac-PiPER-LiftCube-v0}"
ZERO_TASK_TYPE="${ZERO_TASK_TYPE:-piperleader}"
LIVESTREAM_MODE="${LIVESTREAM_MODE:-2}"

LEISAAC_ROOT="$(cd "$(dirname "$0")/../../eval/leisaac" && pwd)"

cd "${LEISAAC_ROOT}"

KIT_ARGS=()
if [ "${LIVESTREAM_MODE}" != "0" ]; then
    KIT_ARGS=("--kit_args=--/app/livestream/outDirectory=${LIVESTREAM_OUT_DIR:-/tmp/isaac-livestream}")
fi

exec python scripts/evaluation/piper_zero_pose.py \
    --task "${ZERO_TASK}" \
    --task_type "${ZERO_TASK_TYPE}" \
    --device cuda:0 \
    --enable_cameras \
    --headless \
    --livestream "${LIVESTREAM_MODE}" \
    "${KIT_ARGS[@]}" \
    "$@"
