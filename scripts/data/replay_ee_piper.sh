#!/usr/bin/env bash
# CONTAINER: piper
#
# EE pose 데이터셋을 로봇에 EndPoseCtrl로 replay합니다.
# FK 변환 정확도 검증용.
#
# 변경할 상수:
set -euo pipefail
set -a
source "$(dirname "$0")/../../envs/.env.piper"
set +a

REPLAY_EPISODE="${REPLAY_EPISODE:-0}"
REPLAY_DRY_RUN="${REPLAY_DRY_RUN:-}"

DRY_RUN_FLAG=""
if [ -n "${REPLAY_DRY_RUN}" ]; then
    DRY_RUN_FLAG="--dry-run"
fi

python "$(dirname "$0")/../../robots/piper/tools/replay_ee_dataset.py" \
    --dataset "${DATASET_ROOT}/${DATASET_REPO_ID}_ee" \
    --episode "${REPLAY_EPISODE}" \
    --can "${CAN_FOLLOWER:-can_follower}" \
    --fps "${FPS:-30}" \
    --speed-ratio "${SPEED_RATIO:-60}" \
    ${DRY_RUN_FLAG}
