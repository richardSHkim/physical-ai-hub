#!/usr/bin/env bash
# CONTAINER: leisaac
#
# Piper 손목 카메라 오프셋 인터랙티브 튜닝
#
# 변경할 상수:
source "$(dirname "${BASH_SOURCE[0]}")/_leisaac_common.sh"
set -euo pipefail

TUNE_TASK="${TUNE_TASK:-LeIsaac-PiPER-LiftCube-v0}"
TUNE_TASK_TYPE="${TUNE_TASK_TYPE:-piperleader}"

"${PYTHON_BIN}" scripts/evaluation/piper_wrist_camera_tuner.py \
    --task "${TUNE_TASK}" \
    --task_type "${TUNE_TASK_TYPE}" \
    --device cuda:0 \
    --enable_cameras \
    --headless \
    --livestream "${LIVESTREAM_MODE}" \
    "${KIT_ARGS[@]}" \
    "$@"
