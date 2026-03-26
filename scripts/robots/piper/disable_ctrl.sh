#!/usr/bin/env bash
# CONTAINER: piper
#
# 변경할 상수:
set -a
source "$(dirname "$0")/../../../envs/.env.piper"
set +a

CAN_NAME="${CAN_INTERFACE:-can0}"

python robots/piper/tools/disable_ctrl.py "$CAN_NAME"
