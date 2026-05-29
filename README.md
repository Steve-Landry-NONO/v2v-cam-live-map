# V2V CAM Live Map – Mini-projet MQTT

Pipeline complet de traitement de traces CAM V2V (ETSI EN 302 637-2) :
PCAP → parsing pyshark → broker MQTT → carte Streamlit/Folium multi-véhicules.

---

## Prérequis

| Outil | Installation |
|-------|-------------|
| Docker | <https://docs.docker.com/get-docker/> |
| Python 3.10 | `sudo apt install python3.10 python3.10-venv` |
| tshark | `sudo apt install tshark` |
| Git | `sudo apt install git` |

---

## Installation

```bash
# 1. Cloner le dépôt
git clone https://github.com/Steve-Landry-NONO/v2v-cam-live-map.git
cd v2v-cam-live-map

# 2. Créer le venv (avec paquets système pour pyshark/scapy)
python3.10 -m venv .env --system-site-packages
source .env/bin/activate

# 3. Installer les dépendances Python
pip install -r cam_mqtt/requirements.txt

# 4. Fournir le fichier PCAP (non versionné – confidentiel)
#    Placer v2v-EVA-2-0.pcap à la racine du projet.
```

> **Note** : Le fichier `.pcap` est intentionnellement absent du dépôt (`.gitignore`).
> Il doit être fourni séparément par l'enseignant ou via le canal de partage du cours.

---

## Rendu 1 – Pipeline brut (PCAP → cam/raw)

### Architecture

```
PCAP ──► producer.py ──► Mosquitto ──► consumer.py
                topic: cam/raw (JSON + base64)
```

### Démarrage (2 terminaux)

**T1 – Broker Mosquitto (Docker)**
```bash
docker run -it --rm \
  -p 1883:1883 \
  -v "$(pwd)/mqtt/config/mosquitto.conf:/mosquitto/config/mosquitto.conf" \
  eclipse-mosquitto
```

**T2 – Consumer** (dans `cam_mqtt/`)
```bash
cd cam_mqtt
python consumer.py
```

**T3 – Producer** (dans `cam_mqtt/`)
```bash
# Mode PCAP réel
cd cam_mqtt
python producer.py --limit 50

# Mode dummy (sans scapy ni PCAP)
python producer.py --dummy --limit 20
```

---

## Rendu 2 – Kinematics pipeline + carte live (cam/kinematics)

### Architecture

```
PCAP ──► producer_kinematics.py ──► Mosquitto ──► ui/app.py (Streamlit+Folium)
               topic: cam/kinematics          (carte multi-véhicules)
               {stationId, lat, lon,
                speed_kmh, heading_deg, ts}
```

### Démarrage (3 terminaux)

**T1 – Broker Mosquitto (même commande que Rendu 1)**
```bash
docker run -it --rm \
  -p 1883:1883 \
  -v "$(pwd)/mqtt/config/mosquitto.conf:/mosquitto/config/mosquitto.conf" \
  eclipse-mosquitto
```

**T2 – Interface Streamlit** (depuis la racine du projet)
```bash
source .env/bin/activate
streamlit run cam_mqtt/ui/app.py
# → http://localhost:8501
```

**T3 – Producer kinematics** (depuis `cam_mqtt/`)
```bash
source .env/bin/activate
cd cam_mqtt
python producer_kinematics.py --pcap ../v2v-EVA-2-0.pcap --rate-ms 200

# Options
#   --limit N        envoyer N événements puis quitter (0 = tout le fichier)
#   --rate-ms <ms>   délai entre envois (simulation temps réel)
#   --dry-run        afficher JSON sans publier (test sans broker)
```

### Résultat attendu

- La carte OSM se centre automatiquement sur la zone de Turin.
- Plusieurs `stationId` apparaissent avec un marqueur coloré et une trajectoire.
- Le panneau latéral permet de masquer/afficher chaque véhicule et de vider les traces.

---

## Structure des topics MQTT

| Topic | Format | Producteur |
|-------|--------|-----------|
| `cam/raw` | `{seq, ts, len, raw_b64, mode}` | `producer.py` |
| `cam/kinematics` | `{stationId, lat, lon, speed_kmh, heading_deg, ts}` | `producer_kinematics.py` |

---

## Arborescence `cam_mqtt/`

```
cam_mqtt/
├── config.py                  # Variables d'environnement et topics
├── producer.py                # Rendu 1 – publie cam/raw (bytes bruts)
├── consumer.py                # Rendu 1 – subscribe cam/raw
├── parser_cam.py              # Rendu 2 – parsing pyshark ITS/GNW → kinematics
├── producer_kinematics.py     # Rendu 2 – publie cam/kinematics
├── requirements.txt
├── ui/
│   └── app.py                 # Interface Streamlit + Folium
├── tools/
│   ├── inspect_fields.py      # Debug : affiche les champs pyshark
│   ├── smoke_consumer.py      # Compteur de messages (utilisé par smoke_test.sh)
│   └── smoke_test.sh          # Test end-to-end automatisé
└── tests/
    └── test_dummy_flow.py     # Tests pytest (imports + parser)
```

---

## Tests

```bash
# Tests unitaires (pas de broker requis)
cd cam_mqtt
pytest tests/test_dummy_flow.py -v

# Test end-to-end (broker requis + PCAP présent)
bash cam_mqtt/tools/smoke_test.sh
```

---

## Dépannage

### pyshark ne voit pas les champs ITS

Vérifier les champs disponibles dans le PCAP :
```bash
python cam_mqtt/tools/inspect_fields.py v2v-EVA-2-0.pcap --n 20
```

Si la couche `its` est absente mais `gnw` est présente, le parser bascule
automatiquement sur l'extraction GeoNetworking (champs `geonw_src_pos_*`).

### tshark non trouvé

```bash
sudo apt install tshark
# Accepter l'option "non-superuser" pendant l'install
# Ajouter l'utilisateur au groupe wireshark si nécessaire :
sudo usermod -aG wireshark $USER && newgrp wireshark
```

### La carte reste vide

1. Vérifier que le broker est démarré (T1).
2. Vérifier que `producer_kinematics.py` tourne et affiche des lignes `TX`.
3. Vérifier que `streamlit run cam_mqtt/ui/app.py` est lancé (T2).
4. La fenêtre Streamlit rafraîchit automatiquement toutes les 1 s.

### Mode dummy (sans PCAP)

```bash
# Tester le pipeline Rendu 1 sans PCAP ni pyshark
cd cam_mqtt
python producer.py --dummy --limit 10
```

---

## Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `BROKER_HOST` | `127.0.0.1` | Adresse du broker |
| `BROKER_PORT` | `1883` | Port du broker |
| `PCAP_PATH` | `../v2v-EVA-2-0.pcap` | Chemin vers le fichier PCAP |
| `TOPIC_RAW` | `cam/raw` | Topic brut |
| `TOPIC_KIN` | `cam/kinematics` | Topic kinematics |
| `QOS` | `0` | QoS MQTT |
