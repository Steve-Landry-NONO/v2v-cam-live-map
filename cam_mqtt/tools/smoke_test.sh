#!/usr/bin/env bash
# smoke_test.sh – End-to-end test: producer_kinematics → broker → consumer counter
#
# Usage (from project root or any directory):
#   bash cam_mqtt/tools/smoke_test.sh
#
# Prerequisites:
#   - Mosquitto broker running on 127.0.0.1:1883
#   - v2v-EVA-2-0.pcap at project root (or set PCAP_PATH env var)
#   - pip install paho-mqtt pyshark  &&  sudo apt install tshark

set -euo pipefail

LIMIT="${LIMIT:-10}"
BROKER_HOST="${BROKER_HOST:-127.0.0.1}"
BROKER_PORT="${BROKER_PORT:-1883}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CAM_DIR="$SCRIPT_DIR/.."
PCAP_PATH="${PCAP_PATH:-$CAM_DIR/../v2v-EVA-2-0.pcap}"
COUNT_FILE="/tmp/smoke_cam_$$"

echo "========================================"
echo " Smoke Test – CAM Kinematics Pipeline"
echo "========================================"
printf "  Broker : %s:%s\n" "$BROKER_HOST" "$BROKER_PORT"
printf "  PCAP   : %s\n" "$PCAP_PATH"
printf "  Limit  : %s events\n" "$LIMIT"
echo ""

# ---- 1. Check PCAP exists ---------------------------------------------------
if [ ! -f "$PCAP_PATH" ]; then
    echo "ERROR: PCAP not found at $PCAP_PATH"
    echo "  Set PCAP_PATH env var or place v2v-EVA-2-0.pcap at project root."
    exit 1
fi

# ---- 2. Check broker --------------------------------------------------------
printf "[1/4] Broker connectivity... "
python3 -c "
import paho.mqtt.client as mqtt, sys
c = mqtt.Client()
try:
    c.connect('$BROKER_HOST', $BROKER_PORT, 3)
    c.disconnect()
    print('OK')
    sys.exit(0)
except Exception as e:
    print(f'FAIL: {e}')
    sys.exit(1)
"

# ---- 3. Start background consumer counter -----------------------------------
echo "[2/4] Starting background consumer (timeout=25s)..."
python3 "$SCRIPT_DIR/smoke_consumer.py" "$COUNT_FILE" 25 "$BROKER_HOST" "$BROKER_PORT" &
CONS_PID=$!
sleep 1

# ---- 4. Run producer --------------------------------------------------------
echo "[3/4] Running producer_kinematics --limit $LIMIT ..."
cd "$CAM_DIR"
python3 producer_kinematics.py \
    --pcap "$PCAP_PATH" \
    --limit "$LIMIT" \
    --rate-ms 100

echo "[4/4] Waiting for consumer to flush (5s)..."
sleep 5
kill "$CONS_PID" 2>/dev/null || true
wait "$CONS_PID" 2>/dev/null || true

# ---- 5. Check result --------------------------------------------------------
COUNT=$(cat "$COUNT_FILE" 2>/dev/null || echo 0)
rm -f "$COUNT_FILE"

echo ""
echo "  Consumer received : $COUNT"
echo "  Expected          : >= $LIMIT"
echo ""

if [ "$COUNT" -ge "$LIMIT" ]; then
    echo "✓ PASS"
    exit 0
else
    echo "✗ FAIL (got $COUNT, expected >= $LIMIT)"
    exit 1
fi
