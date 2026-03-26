#!/usr/bin/env bash
# CONTAINER: piper
#
# 변경할 상수:
set -a
source "$(dirname "$0")/../../../envs/.env.piper"
set +a

WIDTH="${RS_WIDTH:-640}"
HEIGHT="${RS_HEIGHT:-480}"
FPS="${RS_FPS:-30}"
USE_DEPTH="${RS_USE_DEPTH:-false}"
SERIALS="${RS_SERIALS:-}"       # 예: "base=207222072736 wrist=207522074203"

EXTRA_ARGS=()
if [ "$USE_DEPTH" = "true" ]; then
    EXTRA_ARGS+=("--use-depth")
fi
for s in $SERIALS; do
    EXTRA_ARGS+=("--serial" "$s")
done

python robots/piper/tools/check_realsense_intrinsics.py \
    --width "$WIDTH" --height "$HEIGHT" --fps "$FPS" \
    "${EXTRA_ARGS[@]}"
