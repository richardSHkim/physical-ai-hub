#!/usr/bin/env bash
# CONTAINER: piper
#
# 변경할 상수:
set -a
source "$(dirname "$0")/../../../envs/.env.piper"
set +a

PROJECT_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
CAN_NAME="${1:?Usage: $0 <can_name>}"
PERIOD="${WS_PERIOD:-0.05}"                 # 샘플링 주기 (초)
PRINT_PERIOD="${WS_PRINT_PERIOD:-0.5}"      # 콘솔 출력 주기 (초)
MARGIN="${WS_MARGIN:-0.0}"                  # 안전 마진 (미터)
OUTPUT="${WS_OUTPUT:-outputs/piper/workspace.json}"
JUDGE_FLAG="${WS_JUDGE_FLAG:-false}"

if [[ -n "${OUTPUT}" && "${OUTPUT}" != /* ]]; then
    OUTPUT="${PROJECT_ROOT}/${OUTPUT}"
fi

EXTRA_ARGS=()
if [ "$JUDGE_FLAG" = "true" ]; then
    EXTRA_ARGS+=("--judge-flag")
fi
if [ -n "$OUTPUT" ]; then
    EXTRA_ARGS+=("--output" "$OUTPUT")
fi

python robots/piper/tools/measure_workspace.py \
    --can-name "$CAN_NAME" \
    --period "$PERIOD" \
    --print-period "$PRINT_PERIOD" \
    --margin "$MARGIN" \
    "${EXTRA_ARGS[@]}"
