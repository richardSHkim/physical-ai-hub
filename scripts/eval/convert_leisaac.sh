#!/usr/bin/env bash
# CONTAINER: leisaac
#
# LeRobot v3 Piper 데이터셋을 IsaacLab HDF5 형식으로 변환
#
# 변경할 상수:
source "$(dirname "${BASH_SOURCE[0]}")/_leisaac_common.sh"
set -euo pipefail

LEROBOT_ROOT="${LEROBOT_ROOT:-datasets/richardshkim/piper_banana_v2}"
OUTPUT_HDF5="${OUTPUT_HDF5:-outputs/leisaac/piper_banana_v2_isaaclab.hdf5}"
TASK_TYPE="${TASK_TYPE:-piperleader}"

"${PYTHON_BIN}" scripts/convert/lerotbo2isaaclab_piper.py \
    --lerobot_root "${LEROBOT_ROOT}" \
    --output_hdf5 "${OUTPUT_HDF5}" \
    --task_type "${TASK_TYPE}" \
    "$@"
