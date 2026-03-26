#!/usr/bin/env bash
# CONTAINER: piper
#
# 변경할 상수:
set -a
source "$(dirname "$0")/../../../envs/.env.piper"
set +a

CAN_NAME="${CAN_INTERFACE:-can0}"
PERIOD="${WS_PERIOD:-0.05}"                 # 샘플링 주기 (초)
PRINT_PERIOD="${WS_PRINT_PERIOD:-0.5}"      # 콘솔 출력 주기 (초)
MARGIN="${WS_MARGIN:-0.0}"                  # 안전 마진 (미터)
OUTPUT="${WS_OUTPUT:-}"                     # 예: workspace_bounds.json
JUDGE_FLAG="${WS_JUDGE_FLAG:-false}"

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
