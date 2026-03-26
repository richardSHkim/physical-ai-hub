#!/usr/bin/env bash
# CONTAINER: openpi
# RUN: make server-openpi
#
# 변경할 상수:
PORT="${OPENPI_PORT:-8000}"   # ← 여기만 수정
