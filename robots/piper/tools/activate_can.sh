#!/bin/bash
# Unified CAN interface activation script.
# Usage: bash tools/activate_can.sh [config_file] [--ignore]
#   config_file: Path to CAN port config (default: config/can_ports_single.conf)
#   --ignore:    Skip CAN quantity check

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_CONF="${SCRIPT_DIR}/../../config/can_ports_single.conf"

# Parse arguments
CONF_FILE=""
IGNORE_CHECK=false
for arg in "$@"; do
    if [ "$arg" == "--ignore" ]; then
        IGNORE_CHECK=true
    elif [ -z "$CONF_FILE" ] && [ "$arg" != "--ignore" ]; then
        CONF_FILE="$arg"
    fi
done
CONF_FILE="${CONF_FILE:-$DEFAULT_CONF}"

if [ ! -f "$CONF_FILE" ]; then
    echo "[ERROR]: Config file '$CONF_FILE' not found."
    exit 1
fi

# Read config file into USB_PORTS associative array
declare -A USB_PORTS
while IFS= read -r line || [ -n "$line" ]; do
    line="$(echo "$line" | sed 's/#.*//' | xargs)"
    [ -z "$line" ] && continue
    read -r bus_id can_name bitrate <<< "$line"
    USB_PORTS["$bus_id"]="$can_name:$bitrate"
done < "$CONF_FILE"

if [ ${#USB_PORTS[@]} -eq 0 ]; then
    echo "[ERROR]: No CAN port entries found in '$CONF_FILE'."
    exit 1
fi

# Step 1: Print USB_PORTS mapping and check for duplicate target names
echo "🔧 Checking USB_PORTS configuration (from $CONF_FILE):"
declare -A TARGET_NAMES_COUNT
LINE_NUM=0
HAS_DUPLICATE=false

for k in "${!USB_PORTS[@]}"; do
    LINE_NUM=$((LINE_NUM + 1))
    IFS=':' read -r name bitrate <<< "${USB_PORTS[$k]}"

    if [[ -n "${TARGET_NAMES_COUNT[$name]}" ]]; then
        echo "→ [$LINE_NUM] \"$k\"=\"${USB_PORTS[$k]}\"  ❌ Duplicate target CAN name: '$name'"
        HAS_DUPLICATE=true
    else
        echo "  [$LINE_NUM] \"$k\"=\"${USB_PORTS[$k]}\""
        TARGET_NAMES_COUNT["$name"]=1
    fi
done

if $HAS_DUPLICATE; then
    echo "❌ [ERROR]: Found duplicate target CAN interface name(s) above. Please resolve before proceeding."
    exit 1
fi

PREDEFINED_COUNT=${#USB_PORTS[@]}
CURRENT_CAN_COUNT=$(ip link show type can | grep -c "link/can")

if [ "$IGNORE_CHECK" = false ] && [ "$CURRENT_CAN_COUNT" -ne "$PREDEFINED_COUNT" ]; then
    echo "[WARN]: The detected number of CAN modules ($CURRENT_CAN_COUNT) does not match the expected number ($PREDEFINED_COUNT)."
    read -p "Do you want to continue? (y/N): " user_input
    case "$user_input" in
        [yY]|[yY][eE][sS])
            echo "Continue execution..."
            ;;
        *)
            echo "Exited."
            exit 1
            ;;
    esac
else
    echo "CAN quantity check ignored or matched, continuing..."
fi

# Load the gs_usb module
sudo modprobe gs_usb
if [ $? -ne 0 ]; then
    echo "[ERROR]: Unable to load gs_usb module."
    exit 1
fi

SUCCESS_COUNT=0
FAILED_COUNT=0

declare -A USB_PORT_STATUS
for k in "${!USB_PORTS[@]}"; do
    USB_PORT_STATUS["$k"]="pending"
done

SYS_INTERFACE=$(ip -br link show type can | awk '{print $1}')

echo -e "\n🔍 [INFO]: The following CAN interfaces were detected in the system:"
for iface in $SYS_INTERFACE; do
    echo "  - $iface"
done

echo -e "\n⚠️  [HINT]: Please make sure none of the above interface names conflict with the predefined names in your USB_PORTS config."

for iface in $SYS_INTERFACE; do
    echo "--------------------------- $iface ------------------------------"
    BUS_INFO=$(sudo ethtool -i "$iface" | grep "bus-info" | awk '{print $2}')

    if [ -z "$BUS_INFO" ]; then
        echo "[ERROR]: Unable to get bus-info information for interface '$iface'."
        continue
    fi

    echo "[INFO]: System interface '$iface' is plugged into USB port '$BUS_INFO'"
    if [ -n "${USB_PORTS[$BUS_INFO]}" ]; then
        IFS=':' read -r TARGET_NAME TARGET_BITRATE <<< "${USB_PORTS[$BUS_INFO]}"

        IS_LINK_UP=$(ip link show "$iface" | grep -q "UP" && echo "yes" || echo "no")
        CURRENT_BITRATE=$(ip -details link show "$iface" | grep -oP 'bitrate \K\d+')

        if [ "$IS_LINK_UP" = "yes" ] && [ "$CURRENT_BITRATE" -eq "$TARGET_BITRATE" ]; then
            echo "[INFO]: Interface '$iface' is activated and bitrate is $TARGET_BITRATE"

            if [ "$iface" != "$TARGET_NAME" ]; then
                echo "[INFO]: Rename interface '$iface' to '$TARGET_NAME'"
                sudo ip link set "$iface" down
                sudo ip link set "$iface" name "$TARGET_NAME"
                sudo ip link set "$TARGET_NAME" up
                echo "[INFO]: The interface was renamed to '$TARGET_NAME' and reactivated."
            else
                echo "[INFO]: The USB port '$BUS_INFO' interface name is already '$TARGET_NAME'"
            fi
        else
            if ip link show "$TARGET_NAME" &>/dev/null; then
                echo "[WARN]: Cannot rename '$iface' to '$TARGET_NAME' because interface '$TARGET_NAME' already exists."
                echo "[HINT]: Please check if another interface already occupies this name, or fix your USB_PORTS configuration."
                echo "-----------------------------------------------------------------"
                continue
            fi

            if [ "$IS_LINK_UP" = "yes" ]; then
                echo "[INFO]: Interface '$iface' is activated, but the bitrate $CURRENT_BITRATE does not match the set $TARGET_BITRATE."
            else
                echo "[INFO]: Interface '$iface' is not activated or the bitrate is not set."
            fi

            sudo ip link set "$iface" down
            sudo ip link set "$iface" type can bitrate $TARGET_BITRATE
            sudo ip link set "$iface" up
            echo "[INFO]: Interface '$iface' has been reset to bitrate $TARGET_BITRATE and activated."

            if [ "$iface" != "$TARGET_NAME" ]; then
                echo "[INFO]: Rename interface $iface to '$TARGET_NAME'"
                sudo ip link set "$iface" down
                sudo ip link set "$iface" name "$TARGET_NAME"
                sudo ip link set "$TARGET_NAME" up
                echo "[INFO]: The interface was renamed to '$TARGET_NAME' and reactivated."
            fi
        fi
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        USB_PORT_STATUS["$BUS_INFO"]="success"
    else
        echo "[ERROR]: The USB port '$BUS_INFO' of interface '$iface' was not found in the predefined USB_PORTS list."
        echo "[INFO]: Current predefined USB_PORTS configuration:"
        for k in "${!USB_PORTS[@]}"; do
            echo "        '$k'"
        done
        echo "[HINT]: Please check if the USB device is inserted into the correct port, or update the USB_PORTS config if needed."
    fi
    echo "-----------------------------------------------------------------"
done

for k in "${!USB_PORT_STATUS[@]}"; do
    if [ "${USB_PORT_STATUS[$k]}" != "success" ]; then
        echo "❌ Expected CAN interface on USB port '$k' was not found or not activated."
        FAILED_COUNT=$((FAILED_COUNT + 1))
    fi
done

if [ "$SUCCESS_COUNT" -gt 0 ]; then
    echo "[RESULT]: ✅ $SUCCESS_COUNT expected CAN interfaces processed successfully."
else
    echo "[RESULT]: ❌ No USB interface matches the preset CAN configuration, please check whether the USB port is connected correctly."
fi

if [ "$FAILED_COUNT" -gt 0 ]; then
    echo "[RESULT]: 🚫 $FAILED_COUNT expected CAN interfaces failed to activate or were not found."
fi
