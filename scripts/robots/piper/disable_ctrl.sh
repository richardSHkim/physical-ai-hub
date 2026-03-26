#!/usr/bin/env bash
# CONTAINER: piper
#
# 변경할 상수:
CAN_NAME="${1:?Usage: $0 <can_name>}"

python robots/piper/tools/disable_ctrl.py "$CAN_NAME"
