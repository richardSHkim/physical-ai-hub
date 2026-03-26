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

EXTRA_ARGS=()
if [ "$USE_DEPTH" = "true" ]; then
    EXTRA_ARGS+=("--use-depth")
fi
if [ -n "${RS_BASE_SERIAL:-}" ]; then
    EXTRA_ARGS+=("--serial" "base=${RS_BASE_SERIAL}")
fi
if [ -n "${RS_WRIST_SERIAL:-}" ]; then
    EXTRA_ARGS+=("--serial" "wrist=${RS_WRIST_SERIAL}")
fi

python robots/piper/tools/check_realsense_intrinsics.py \
    --width "$WIDTH" --height "$HEIGHT" --fps "$FPS" \
    "${EXTRA_ARGS[@]}"
