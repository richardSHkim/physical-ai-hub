#!/usr/bin/env bash
# CONTAINER: leisaac
#
# IsaacLab에서 변환된 Piper 데이터셋 리플레이
#
# 변경할 상수:
set -a
source "$(dirname "$0")/../../envs/.env.leisaac"
set +a

REPLAY_TASK="${REPLAY_TASK:-LeIsaac-PiPER-LiftCube-v0}"
REPLAY_TASK_TYPE="${REPLAY_TASK_TYPE:-piperleader}"
REPLAY_DATASET_FILE="${REPLAY_DATASET_FILE:-outputs/leisaac/piper_banana_v2_isaaclab.hdf5}"
REPLAY_VIDEO_DIR="${REPLAY_VIDEO_DIR:-outputs/leisaac/piper_replay_videos}"
LIVESTREAM_MODE="${LIVESTREAM_MODE:-2}"

LEISAAC_ROOT="$(cd "$(dirname "$0")/../../eval/leisaac" && pwd)"

cd "${LEISAAC_ROOT}"

KIT_ARGS=()
if [ "${LIVESTREAM_MODE}" != "0" ]; then
    KIT_ARGS=("--kit_args=--/app/livestream/outDirectory=${LIVESTREAM_OUT_DIR:-/tmp/isaac-livestream}")
fi

exec python scripts/evaluation/piper_replay_lerobot_dataset.py \
    --task "${REPLAY_TASK}" \
    --task_type "${REPLAY_TASK_TYPE}" \
    --dataset_file "${REPLAY_DATASET_FILE}" \
    --save_replay_video_dir "${REPLAY_VIDEO_DIR}" \
    --device cuda:0 \
    --enable_cameras \
    --headless \
    --livestream "${LIVESTREAM_MODE}" \
    "${KIT_ARGS[@]}" \
    "$@"
