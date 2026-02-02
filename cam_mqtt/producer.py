import base64
import json
import logging
import os
from datetime import datetime

import paho.mqtt.client as mqtt
from scapy.all import PcapReader  # type: ignore

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

def packet_to_message(pkt_bytes: bytes, seq: int) -> dict:
    return {
        "seq": seq,
        "ts": datetime.utcnow().isoformat() + "Z",
        "len": len(pkt_bytes),
        "raw_b64": base64.b64encode(pkt_bytes).decode("ascii"),
    }

def main():
    if not os.path.exists(config.PCAP_PATH):
        raise FileNotFoundError(
            f"PCAP not found: {config.PCAP_PATH}. Update PCAP_PATH in config.py."
        )

    client = mqtt.Client(client_id=config.CLIENT_ID_PRODUCER)
    client.connect(config.BROKER_HOST, config.BROKER_PORT, keepalive=60)
    client.loop_start()

    sent = 0
    logging.info("Reading PCAP: %s", config.PCAP_PATH)

    with PcapReader(config.PCAP_PATH) as pcap:
        for i, pkt in enumerate(pcap, start=1):
            pkt_bytes = bytes(pkt)
            msg = packet_to_message(pkt_bytes, seq=i)
            payload = json.dumps(msg, separators=(",", ":"))

            info = client.publish(config.TOPIC_RAW, payload=payload, qos=config.QOS)
            info.wait_for_publish()

            sent += 1
            logging.info("TX #%d | len=%d", i, len(pkt_bytes))
            if sent >= config.SEND_LIMIT:
                break

    logging.info("DONE: sent=%d messages to topic=%s", sent, config.TOPIC_RAW)
    client.loop_stop()
    client.disconnect()

if __name__ == "__main__":
    main()
