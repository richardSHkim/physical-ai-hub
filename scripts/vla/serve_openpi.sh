#!/usr/bin/env bash
# CONTAINER: openpi
#
# 변경할 상수:
set -a
source "$(dirname "$0")/../../envs/.env.openpi"
set +a

OPENPI_ROOT="$(cd "$(dirname "$0")/../../vla/openpi" && pwd)"

PIPER_CONFIG_NAME="${PIPER_CONFIG_NAME:-pi05_piper}"
PIPER_POLICY_DIR="${PIPER_POLICY_DIR:?Set PIPER_POLICY_DIR to a checkpoint directory.}"

cd "${OPENPI_ROOT}"

exec uv run scripts/serve_policy.py \
    policy:checkpoint \
    --policy.config "${PIPER_CONFIG_NAME}" \
    --policy.dir "${PIPER_POLICY_DIR}" \
    "$@"
