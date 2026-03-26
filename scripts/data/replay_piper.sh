#!/usr/bin/env bash
# CONTAINER: piper
#
# 변경할 상수:
set -euo pipefail
set -a
source "$(dirname "$0")/../../envs/.env.piper"
set +a

REPLAY_EPISODE="${REPLAY_EPISODE:-0}"

lerobot-replay \
    --robot.type=piper_follower \
    --robot.id=piper_follower_01 \
    --dataset.repo_id=${DATASET_REPO_ID} \
    --dataset.episode=${REPLAY_EPISODE}
