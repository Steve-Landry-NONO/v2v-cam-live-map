# config.py
import os
from pathlib import Path

BROKER_HOST = os.getenv("BROKER_HOST", "127.0.0.1")
BROKER_PORT = int(os.getenv("BROKER_PORT", "1883"))
TOPIC_RAW = os.getenv("TOPIC_RAW", "cam/raw")
QOS = int(os.getenv("QOS", "0"))

CLIENT_ID_PRODUCER = os.getenv("CLIENT_ID_PRODUCER", "cam-producer")
CLIENT_ID_CONSUMER = os.getenv("CLIENT_ID_CONSUMER", "cam-consumer")

# Par défaut : pcap à la racine du projet (../v2v-EVA-2-0.pcap depuis cam_mqtt/)
DEFAULT_PCAP = str((Path(__file__).resolve().parent.parent / "v2v-EVA-2-0.pcap"))
PCAP_PATH = os.getenv("PCAP_PATH", DEFAULT_PCAP)

SEND_LIMIT = int(os.getenv("SEND_LIMIT", "10"))

