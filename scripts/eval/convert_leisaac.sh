#!/usr/bin/env bash
# CONTAINER: leisaac
#
# LeRobot v3 Piper 데이터셋을 IsaacLab HDF5 형식으로 변환
#
# 변경할 상수:
set -a
source "$(dirname "$0")/../../envs/.env.leisaac"
set +a

LEROBOT_ROOT="${LEROBOT_ROOT:-datasets/richardshkim/piper_banana_v2}"
OUTPUT_HDF5="${OUTPUT_HDF5:-outputs/leisaac/piper_banana_v2_isaaclab.hdf5}"
TASK_TYPE="${TASK_TYPE:-piperleader}"

LEISAAC_ROOT="$(cd "$(dirname "$0")/../../eval/leisaac" && pwd)"
[ ! -x "${PYTHON_BIN}" ] && PYTHON_BIN="python"
export PYTHONPATH="${LEISAAC_ROOT}/source/leisaac:${PYTHONPATH:-}"
export LEISAAC_ASSETS_ROOT

cd "${LEISAAC_ROOT}"

exec "${PYTHON_BIN}" scripts/convert/lerotbo2isaaclab_piper.py \
    --lerobot_root "${LEROBOT_ROOT}" \
    --output_hdf5 "${OUTPUT_HDF5}" \
    --task_type "${TASK_TYPE}" \
    "$@"
