#!/usr/bin/env bash
# CONTAINER: piper
#
# 변경할 상수:
set -a
source "$(dirname "$0")/../../../envs/.env.piper"
set +a

CAN_PORTS="${CAN_PORTS:-}"
CAN_IGNORE_CHECK="${CAN_IGNORE_CHECK:-false}"
# CAN_PORTS 형식 (space-separated):
#   "bus_id,can_name,bitrate bus_id,can_name,bitrate ..."
#   예: "3-13.1:1.0,can_l_follower,1000000 3-13.2:1.0,can_l_leader,1000000"

if [ -z "$CAN_PORTS" ]; then
    echo "[ERROR]: CAN_PORTS is not set. Configure it in envs/.env.piper"
    echo "  Format: \"bus_id,can_name,bitrate bus_id,can_name,bitrate ...\""
    echo "  Example: \"3-13.1:1.0,can_l_follower,1000000 3-13.2:1.0,can_l_leader,1000000\""
    exit 1
fi

CONF_FILE=$(mktemp /tmp/can_ports.XXXXXX.conf)
trap 'rm -f "$CONF_FILE"' EXIT

for entry in $CAN_PORTS; do
    IFS=',' read -r bus_id can_name bitrate <<< "$entry"
    echo "$bus_id $can_name $bitrate" >> "$CONF_FILE"
done

EXTRA_ARGS=()
if [ "$CAN_IGNORE_CHECK" = "true" ]; then
    EXTRA_ARGS+=("--ignore")
fi

bash robots/piper/tools/activate_can.sh "$CONF_FILE" "${EXTRA_ARGS[@]}"
