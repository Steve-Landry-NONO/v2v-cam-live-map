import base64
import json
import logging
import paho.mqtt.client as mqtt
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
count = 0

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logging.info("Connected to %s:%s", config.BROKER_HOST, config.BROKER_PORT)
        client.subscribe(config.TOPIC_RAW, qos=config.QOS)
        logging.info("Subscribed to %s", config.TOPIC_RAW)
    else:
        logging.error("Connect failed rc=%s", rc)

def on_message(client, userdata, msg):
    global count
    count += 1
    try:
        data = json.loads(msg.payload.decode("utf-8", errors="strict"))
        seq = data.get("seq")
        ln = data.get("len")
        ts = data.get("ts")
        raw_b64 = data.get("raw_b64", "")
        raw_len = len(base64.b64decode(raw_b64)) if raw_b64 else 0
        logging.info("RX #%d | seq=%s | len=%s | raw_len=%s | ts=%s", count, seq, ln, raw_len, ts)
    except Exception as e:
        logging.error("Bad message #%d: %s", count, e)

def main():
    client = mqtt.Client(client_id=config.CLIENT_ID_CONSUMER)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(config.BROKER_HOST, config.BROKER_PORT, keepalive=60)
    client.loop_forever()

if __name__ == "__main__":
    main()
