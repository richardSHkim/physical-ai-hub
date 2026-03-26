#!/usr/bin/env bash
# CONTAINER: leisaac
#
# Piper 제로 포즈 시각화 (정책 없이)
#
# 변경할 상수:
source "$(dirname "${BASH_SOURCE[0]}")/_leisaac_common.sh"
set -euo pipefail

ZERO_TASK="${ZERO_TASK:-LeIsaac-PiPER-LiftCube-v0}"
ZERO_TASK_TYPE="${ZERO_TASK_TYPE:-piperleader}"

"${PYTHON_BIN}" scripts/evaluation/piper_zero_pose.py \
    --task "${ZERO_TASK}" \
    --task_type "${ZERO_TASK_TYPE}" \
    --device cuda:0 \
    --enable_cameras \
    --headless \
    --livestream "${LIVESTREAM_MODE}" \
    "${KIT_ARGS[@]}" \
    "$@"
