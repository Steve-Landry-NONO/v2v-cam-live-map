#!/usr/bin/env python3
"""
producer_kinematics.py – Parse PCAP and publish CAM kinematics on cam/kinematics.

Usage (from cam_mqtt/ directory):
    python producer_kinematics.py --pcap ../v2v-EVA-2-0.pcap --limit 50 --rate-ms 200
    python producer_kinematics.py --dry-run --limit 10
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import paho.mqtt.client as mqtt
import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Publish CAM kinematics to MQTT topic cam/kinematics"
    )
    ap.add_argument("--pcap", default=config.PCAP_PATH, help="Path to PCAP file")
    ap.add_argument("--limit", type=int, default=0, help="Max events (0 = no limit)")
    ap.add_argument(
        "--rate-ms",
        type=int,
        default=200,
        dest="rate_ms",
        help="Sleep between publishes in ms (default 200)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print JSON events without publishing to MQTT",
    )
    return ap.parse_args()


def main() -> None:
    args = _parse_args()

    try:
        from parser_cam import extract_cam_kinematics
    except ImportError as exc:
        log.error("Cannot import parser_cam: %s", exc)
        sys.exit(1)

    # Connect to broker (unless dry-run)
    client = None
    if not args.dry_run:
        client = mqtt.Client(client_id=config.CLIENT_ID_KIN_PRODUCER)
        try:
            client.connect(config.BROKER_HOST, config.BROKER_PORT, keepalive=60)
        except Exception as exc:
            log.error(
                "Cannot connect to broker %s:%d  →  %s",
                config.BROKER_HOST,
                config.BROKER_PORT,
                exc,
            )
            sys.exit(1)
        client.loop_start()
        log.info("Connected to broker %s:%d", config.BROKER_HOST, config.BROKER_PORT)

    log.info("Reading PCAP: %s", args.pcap)

    tx = 0
    try:
        for ev in extract_cam_kinematics(args.pcap):
            payload = json.dumps(ev, separators=(",", ":"))

            if args.dry_run:
                print(f"[DRY-RUN] {payload}", flush=True)
            else:
                client.publish(config.TOPIC_KIN, payload, qos=config.QOS)
                log.info(
                    "TX #%d | id=%-12s | lat=%9.5f | lon=%9.5f | "
                    "speed=%5.1f km/h | hdg=%5.1f°",
                    tx + 1,
                    ev["stationId"],
                    ev["lat"],
                    ev["lon"],
                    ev["speed_kmh"],
                    ev["heading_deg"],
                )

            tx += 1
            if args.limit and tx >= args.limit:
                break
            if args.rate_ms > 0:
                time.sleep(args.rate_ms / 1000.0)

    except ImportError as exc:
        log.error("%s", exc)
        sys.exit(1)
    except FileNotFoundError:
        log.error("PCAP not found: %s", args.pcap)
        sys.exit(1)
    except KeyboardInterrupt:
        log.info("Interrupted by user")

    log.info(
        "DONE | sent=%d | topic=%s",
        tx,
        config.TOPIC_KIN if not args.dry_run else "(dry-run)",
    )

    if client is not None:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
