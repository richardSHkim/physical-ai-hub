#!/usr/bin/env bash
# CONTAINER: piper
#
# SDK endpose 실측값과 FK 계산값을 실시간 비교합니다.
# 로봇을 여러 포즈로 움직이면서 오차를 확인하세요.
#
# 변경할 상수:
set -euo pipefail
set -a
source "$(dirname "$0")/../../../envs/.env.piper"
set +a

python "$(dirname "$0")/../../../robots/piper/tools/compare_fk.py" \
    --can-name "${CAN_FOLLOWER:-can_follower}"
