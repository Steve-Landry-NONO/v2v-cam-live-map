# cam-mqtt (mini-projet V2V)

Mini-projet 1 (en cours) :
- Broker MQTT (Mosquitto) via Docker
- Producer lit un fichier PCAP et publie N paquets sur un topic MQTT (JSON + base64)
- Consumer s'abonne et affiche les messages reçus (compteurs, tailles)

## Démarrage rapide

### 1) Créer / activer le venv (Python 3.10 + paquets système)
```bash
/usr/bin/python3.10 -m venv .env --system-site-packages
source .env/bin/activate
python -V
python -c "import paho.mqtt.client as mqtt; print('OK paho')"


