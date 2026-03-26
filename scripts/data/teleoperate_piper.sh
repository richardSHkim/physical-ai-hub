#!/usr/bin/env bash
# CONTAINER: piper
#
# 변경할 상수:
set -euo pipefail
set -a
source "$(dirname "$0")/../../envs/.env.piper"
set +a

lerobot-teleoperate \
    --robot.type=piper_follower \
    --robot.can_name=can_follower \
    --robot.id=piper_follower_01 \
    --robot.cameras="{ base: {type: intelrealsense, serial_number_or_name: ${RS_BASE_SERIAL}, width: ${RS_WIDTH}, height: ${RS_HEIGHT}, fps: ${RS_FPS}, use_depth: ${RS_USE_DEPTH}}, wrist: {type: intelrealsense, serial_number_or_name: ${RS_WRIST_SERIAL}, width: ${RS_WIDTH}, height: ${RS_HEIGHT}, fps: ${RS_FPS}, use_depth: ${RS_USE_DEPTH}}}" \
    --teleop.type=piper_leader \
    --teleop.can_name=can_leader \
    --teleop.id=piper_leader_01 \
    --teleop.hand_guiding=true \
    --teleop.hand_guiding_mode=drag_teach \
    --teleop.teaching_friction=2 \
    --fps=${CONTROL_HZ} \
    --display_data=true
