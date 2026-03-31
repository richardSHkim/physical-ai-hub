#!/usr/bin/env bash
# CONTAINER: piper
#
# Joint 기반 Piper 데이터셋을 EE pose 기반으로 변환합니다.
#
# 변경할 상수:
set -euo pipefail
set -a
source "$(dirname "$0")/../../envs/.env.piper"
set +a

SRC="${DATASET_ROOT}/${DATASET_REPO_ID}"           # joint 원본
DST="${DATASET_ROOT}/${DATASET_REPO_ID}_ee"         # EE pose 변환 결과

python "$(dirname "$0")/../../data/tools/convert_joint_to_ee.py" \
    --src "${SRC}" \
    --dst "${DST}"
