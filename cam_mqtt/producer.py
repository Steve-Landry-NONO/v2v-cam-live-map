import argparse
import os
import time
import base64
import json
import logging
from datetime import datetime

import paho.mqtt.client as mqtt
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

def packet_to_message(pkt_bytes: bytes, seq: int) -> dict:
    return {
        "seq": seq,
        "ts": datetime.utcnow().isoformat() + "Z",
        "len": len(pkt_bytes),
        "raw_b64": base64.b64encode(pkt_bytes).decode("ascii"),
        "mode": "dummy"  # remplacé si vrai pcap
    }

def send_dummy(client, n: int):
    for i in range(1, n+1):
        fake = os.urandom(120)  # 120 bytes random
        msg = packet_to_message(fake, i)
        msg["mode"] = "dummy"
        client.publish(config.TOPIC_RAW, json.dumps(msg), qos=config.QOS)
        logging.info("TX(dummy) #%d | len=%d", i, len(fake))
        time.sleep(0.05)

def send_from_pcap(client, n: int):
    from scapy.all import PcapReader  # import ici pour éviter dépendance si --dummy

    if not os.path.exists(config.PCAP_PATH):
        raise FileNotFoundError(f"PCAP not found: {config.PCAP_PATH}")

    with PcapReader(config.PCAP_PATH) as pcap:
        sent = 0
        for i, pkt in enumerate(pcap, start=1):
            pkt_bytes = bytes(pkt)
            msg = packet_to_message(pkt_bytes, seq=i)
            msg["mode"] = "pcap"
            client.publish(config.TOPIC_RAW, json.dumps(msg), qos=config.QOS)
            sent += 1
            logging.info("TX(pcap) #%d | len=%d", i, len(pkt_bytes))
            if sent >= n:
                break

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=config.SEND_LIMIT)
    ap.add_argument("--dummy", action="store_true", help="Send N fake messages (no scapy/pcap needed)")
    args = ap.parse_args()

    client = mqtt.Client(client_id=config.CLIENT_ID_PRODUCER)
    client.connect(config.BROKER_HOST, config.BROKER_PORT, keepalive=60)
    client.loop_start()

    if args.dummy:
        send_dummy(client, args.limit)
    else:
        send_from_pcap(client, args.limit)

    logging.info("DONE: sent=%d messages to topic=%s", args.limit, config.TOPIC_RAW)
    client.loop_stop()
    client.disconnect()

if __name__ == "__main__":
    main()

