#!/usr/bin/env python3
"""
smoke_consumer.py – Count messages on cam/kinematics then write count to a file.
Used internally by smoke_test.sh.

Usage:
    python smoke_consumer.py <count_file> [timeout_seconds] [broker_host] [broker_port]
"""

import json
import signal
import sys
import time

import paho.mqtt.client as mqtt

count_file = sys.argv[1]
timeout = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
broker_host = sys.argv[3] if len(sys.argv) > 3 else "127.0.0.1"
broker_port = int(sys.argv[4]) if len(sys.argv) > 4 else 1883

count = [0]


def _flush():
    with open(count_file, "w") as f:
        f.write(str(count[0]))


def on_message(client, userdata, msg):
    count[0] += 1
    _flush()  # write after every message so kill won't lose the count
    try:
        d = json.loads(msg.payload)
        print(
            f"  RX {count[0]:3d}: id={str(d.get('stationId', '?')):<14} "
            f"lat={d.get('lat', 0):.5f}  lon={d.get('lon', 0):.5f}  "
            f"speed={d.get('speed_kmh', 0):.1f} km/h",
            flush=True,
        )
    except Exception:
        print(f"  RX {count[0]:3d}: (parse error)", flush=True)


def _sigterm_handler(sig, frame):
    _flush()
    sys.exit(0)


signal.signal(signal.SIGTERM, _sigterm_handler)
signal.signal(signal.SIGINT, _sigterm_handler)

c = mqtt.Client()
c.on_message = on_message
c.connect(broker_host, broker_port)
c.subscribe("cam/kinematics")
c.loop_start()
time.sleep(timeout)
c.loop_stop()
c.disconnect()
_flush()
