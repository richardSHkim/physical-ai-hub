#!/usr/bin/env bash
# CONTAINER: piper
#
CAN_NAME="${1:?Usage: $0 <can_name>}"

python robots/piper/tools/go_zero.py "$CAN_NAME"
