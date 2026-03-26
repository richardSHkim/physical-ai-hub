#!/usr/bin/env bash
# CONTAINER: piper
#
# 변경할 상수:
set -euo pipefail
set -a
source "$(dirname "$0")/../../envs/.env.piper"
set +a

lerobot-record \
    --robot.type=bi_piper_follower \
    --robot.id=bi_piper_follower_01 \
    --robot.left_arm_config.can_name=can_l_follower \
    --robot.left_arm_config.speed_ratio=60 \
    --robot.left_arm_config.cameras="{ base: {type: intelrealsense, serial_number_or_name: ${RS_BASE_SERIAL}, width: ${RS_WIDTH}, height: ${RS_HEIGHT}, fps: ${RS_FPS}, use_depth: ${RS_USE_DEPTH}}, wrist: {type: intelrealsense, serial_number_or_name: ${RS_WRIST_SERIAL}, width: ${RS_WIDTH}, height: ${RS_HEIGHT}, fps: ${RS_FPS}, use_depth: ${RS_USE_DEPTH}}}" \
    --robot.right_arm_config.can_name=can_r_follower \
    --robot.right_arm_config.speed_ratio=60 \
    --teleop.type=bi_piper_leader \
    --teleop.id=bi_piper_leader_01 \
    --teleop.left_arm_config.can_name=can_l_leader \
    --teleop.left_arm_config.hand_guiding=true \
    --teleop.left_arm_config.hand_guiding_mode=drag_teach \
    --teleop.left_arm_config.teaching_friction=2 \
    --teleop.right_arm_config.can_name=can_r_leader \
    --teleop.right_arm_config.hand_guiding=true \
    --teleop.right_arm_config.hand_guiding_mode=drag_teach \
    --teleop.right_arm_config.teaching_friction=2 \
    --dataset.repo_id=${DATASET_REPO_ID} \
    --dataset.private=${DATASET_PRIVATE} \
    --dataset.single_task="${DATASET_SINGLE_TASK}" \
    --dataset.num_episodes=${DATASET_NUM_EPISODES} \
    --display_data=true
