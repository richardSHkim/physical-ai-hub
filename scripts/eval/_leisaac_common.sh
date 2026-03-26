#!/usr/bin/env bash
# 모든 LeIsaac 스크립트에서 source하는 공통 설정
#
# 사용법:
#   source "$(dirname "${BASH_SOURCE[0]}")/_leisaac_common.sh"

set -a
source "$(dirname "${BASH_SOURCE[0]}")/../../envs/.env.leisaac"
set +a

LEISAAC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../eval/leisaac" && pwd)"

if [ ! -x "${PYTHON_BIN}" ]; then
    PYTHON_BIN="python"
fi

export PYTHONPATH="${LEISAAC_ROOT}/source/leisaac:${PYTHONPATH:-}"
export LEISAAC_ASSETS_ROOT

cd "${LEISAAC_ROOT}" || exit 1

KIT_ARGS=()
if [ "${LIVESTREAM_MODE}" != "0" ]; then
    KIT_ARGS=("--kit_args=--/app/livestream/outDirectory=${LIVESTREAM_OUT_DIR}")
fi
