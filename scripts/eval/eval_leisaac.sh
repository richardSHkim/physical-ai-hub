#!/usr/bin/env bash
# CONTAINER: leisaac
#
# LeIsaac 시뮬레이션에서 정책 평가 실행
#
# 변경할 상수:
source "$(dirname "${BASH_SOURCE[0]}")/_leisaac_common.sh"
set -euo pipefail

EVAL_TASK="${EVAL_TASK:-LeIsaac-PiPER-LiftCube-v0}"
EVAL_POLICY_TYPE="${EVAL_POLICY_TYPE:-openpi}"
EVAL_POLICY_HOST="${EVAL_POLICY_HOST:-localhost}"
EVAL_POLICY_PORT="${EVAL_POLICY_PORT:-8000}"
EVAL_LANGUAGE_INSTRUCTION="${EVAL_LANGUAGE_INSTRUCTION:-Lift the red cube up.}"
EVAL_VIDEO_DIR="${EVAL_VIDEO_DIR:-outputs/leisaac/policy_inference_videos}"

"${PYTHON_BIN}" scripts/evaluation/policy_inference.py \
    --task "${EVAL_TASK}" \
    --policy_type "${EVAL_POLICY_TYPE}" \
    --policy_host "${EVAL_POLICY_HOST}" \
    --policy_port "${EVAL_POLICY_PORT}" \
    --policy_language_instruction "${EVAL_LANGUAGE_INSTRUCTION}" \
    --save_eval_video_dir "${EVAL_VIDEO_DIR}" \
    --device cuda:0 \
    --enable_cameras \
    --headless \
    --livestream "${LIVESTREAM_MODE}" \
    "${KIT_ARGS[@]}" \
    "$@"
