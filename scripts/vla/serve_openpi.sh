#!/usr/bin/env bash
# CONTAINER: openpi
#
# 변경할 상수:
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

set -a
source "${PROJECT_ROOT}/envs/.env.openpi"
set +a

OPENPI_ROOT="${PROJECT_ROOT}/vla/openpi"

PIPER_CONFIG_NAME="${PIPER_CONFIG_NAME:-pi05_piper}"
DEFAULT_PIPER_POLICY_DIR="${PROJECT_ROOT}/outputs/openpi/pi05_piper/pi05_piper_20260327_075118/2999"
PIPER_POLICY_DIR="${PIPER_POLICY_DIR:-${DEFAULT_PIPER_POLICY_DIR}}"

if [[ "${PIPER_POLICY_DIR}" != /* && "${PIPER_POLICY_DIR}" != gs://* ]]; then
    PIPER_POLICY_DIR="${PROJECT_ROOT}/${PIPER_POLICY_DIR}"
fi

if [[ "${PIPER_POLICY_DIR}" != gs://* && ! -e "${PIPER_POLICY_DIR}" ]]; then
    echo "PIPER_POLICY_DIR does not exist: ${PIPER_POLICY_DIR}" >&2
    exit 1
fi

cd "${OPENPI_ROOT}"

exec uv run scripts/serve_policy.py \
    policy:checkpoint \
    --policy.config "${PIPER_CONFIG_NAME}" \
    --policy.dir "${PIPER_POLICY_DIR}" \
    "$@"
