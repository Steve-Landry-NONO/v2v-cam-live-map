"""
app.py – Streamlit + Folium live map for V2V CAM kinematics.

Run from project root:
    streamlit run cam_mqtt/ui/app.py

Architecture:
  - MQTT client runs in a daemon thread (started once per Streamlit session).
  - Messages are pushed into a thread-safe queue stored in st.session_state.
  - The Streamlit script drains the queue on every rerun, updates tracks/last,
    rebuilds the Folium map, then sleeps 1 s and calls st.rerun() for auto-refresh.
"""

import json
import logging
import queue
import sys
import threading
import time
from pathlib import Path

import streamlit as st

# Allow bare "import config" like the other cam_mqtt modules
sys.path.insert(0, str(Path(__file__).parent.parent))
import config  # noqa: E402

try:
    import folium
    from streamlit_folium import st_folium
except ImportError as _ie:
    st.error(
        f"Missing dependency: {_ie}\n\n"
        "Install with:\n```\npip install folium streamlit-folium\n```"
    )
    st.stop()

import paho.mqtt.client as mqtt  # noqa: E402

log = logging.getLogger(__name__)

# Default map centre (Turin – zone of the test PCAP)
_DEFAULT_CENTER = (45.07, 7.67)
_DEFAULT_ZOOM = 14
_REFRESH_S = 1.0


# ---------------------------------------------------------------------------
# MQTT background thread
# ---------------------------------------------------------------------------

def _start_mqtt(q: queue.SimpleQueue) -> None:
    """Connect to broker and start the MQTT loop in a daemon thread."""

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            client.subscribe(config.TOPIC_KIN, qos=config.QOS)
            log.info("MQTT subscribed to %s", config.TOPIC_KIN)
        else:
            log.warning("MQTT connect failed rc=%d", rc)

    def on_message(client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode())
            q.put_nowait(data)
        except Exception as exc:
            log.debug("bad message: %s", exc)

    client = mqtt.Client(client_id=f"{config.CLIENT_ID_UI}-{id(q) % 65536}")
    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(config.BROKER_HOST, config.BROKER_PORT, keepalive=60)
        t = threading.Thread(target=client.loop_forever, daemon=True)
        t.start()
    except Exception as exc:
        log.warning("MQTT connect error (broker not ready?): %s", exc)


# ---------------------------------------------------------------------------
# Session-state helpers
# ---------------------------------------------------------------------------

def _init_state() -> None:
    if "q" not in st.session_state:
        st.session_state.q = queue.SimpleQueue()
    if "mqtt_started" not in st.session_state:
        _start_mqtt(st.session_state.q)
        st.session_state.mqtt_started = True
    if "tracks" not in st.session_state:
        st.session_state.tracks: dict[str, list[tuple[float, float]]] = {}
    if "last" not in st.session_state:
        st.session_state.last: dict[str, dict] = {}


def _drain_queue(max_pts: int) -> int:
    """Pull all pending messages from the queue and update tracks/last."""
    drained = 0
    while True:
        try:
            ev = st.session_state.q.get_nowait()
        except queue.Empty:
            break
        sid = str(ev.get("stationId", "?"))
        lat = ev.get("lat")
        lon = ev.get("lon")
        if lat is None or lon is None:
            continue
        track = st.session_state.tracks.setdefault(sid, [])
        track.append((lat, lon))
        if len(track) > max_pts:
            st.session_state.tracks[sid] = track[-max_pts:]
        st.session_state.last[sid] = ev
        drained += 1
    return drained


# ---------------------------------------------------------------------------
# Folium map builder
# ---------------------------------------------------------------------------

def _build_map(hidden: set[str], center, zoom: int) -> folium.Map:
    m = folium.Map(location=center, zoom_start=zoom, tiles="OpenStreetMap")

    # Colour palette – cycles for each stationId
    palette = [
        "blue", "red", "green", "purple", "orange",
        "darkred", "darkblue", "darkgreen", "cadetblue", "pink",
    ]

    for idx, (sid, track) in enumerate(sorted(st.session_state.tracks.items())):
        if sid in hidden or not track:
            continue
        color = palette[idx % len(palette)]
        last_ev = st.session_state.last.get(sid, {})
        speed = last_ev.get("speed_kmh", 0.0)
        heading = last_ev.get("heading_deg", 0.0)
        ts = last_ev.get("ts", "")

        # Trajectory polyline
        if len(track) >= 2:
            folium.PolyLine(
                locations=track,
                weight=2,
                color=color,
                opacity=0.7,
            ).add_to(m)

        # Current-position marker
        popup_html = (
            f"<b>Vehicle {sid}</b><br/>"
            f"Speed: {speed:.1f} km/h<br/>"
            f"Heading: {heading:.0f}°<br/>"
            f"ts: {ts}"
        )
        folium.Marker(
            location=track[-1],
            popup=folium.Popup(popup_html, max_width=220),
            tooltip=f"{sid} | {speed:.0f} km/h",
            icon=folium.Icon(color=color, icon="circle", prefix="fa"),
        ).add_to(m)

    return m


# ---------------------------------------------------------------------------
# Main Streamlit app
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(
        page_title="V2V CAM Live Map",
        layout="wide",
        page_icon="🚗",
    )
    st.title("🚗 V2V CAM Live Map")

    _init_state()

    # ---- Sidebar ----
    with st.sidebar:
        st.header("⚙️ Settings")
        max_pts = st.slider("Max points / vehicle", 10, 500, 200, key="max_pts_slider")
        if st.button("🗑️ Clear all tracks"):
            st.session_state.tracks.clear()
            st.session_state.last.clear()
        st.divider()
        st.subheader("🔌 Connection")
        st.code(f"{config.BROKER_HOST}:{config.BROKER_PORT}\ntopic: {config.TOPIC_KIN}")
        st.divider()
        st.subheader("🚗 Vehicles")

    # Drain queue before rendering
    drained = _drain_queue(max_pts)

    # Vehicle toggle checkboxes
    vehicles = sorted(st.session_state.last.keys())
    hidden: set[str] = set()
    for sid in vehicles:
        key = f"show_{sid}"
        if key not in st.session_state:
            st.session_state[key] = True
        show = st.sidebar.checkbox(f"ID: {sid}", key=key)
        if not show:
            hidden.add(sid)

    # Compute map centre from visible vehicles
    visible_lasts = [
        st.session_state.last[sid]
        for sid in st.session_state.last
        if sid not in hidden
    ]
    if visible_lasts:
        center_lat = sum(v["lat"] for v in visible_lasts) / len(visible_lasts)
        center_lon = sum(v["lon"] for v in visible_lasts) / len(visible_lasts)
        center = (center_lat, center_lon)
        zoom = 15
    else:
        center, zoom = _DEFAULT_CENTER, _DEFAULT_ZOOM

    # Stats row
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total vehicles", len(st.session_state.last))
    col2.metric("Visible", len(vehicles) - len(hidden))
    col3.metric("New msgs this cycle", drained)
    total_pts = sum(len(t) for t in st.session_state.tracks.values())
    col4.metric("Total track points", total_pts)

    # Build and render map
    m = _build_map(hidden, center, zoom)
    try:
        st_folium(m, use_container_width=True, height=600, returned_objects=[])
    except TypeError:
        # Older streamlit-folium versions don't have use_container_width
        st_folium(m, width=900, height=600)

    # Status line
    if not vehicles:
        st.info(
            "Waiting for data on `cam/kinematics`…\n\n"
            "Start the producer:  `python cam_mqtt/producer_kinematics.py --pcap v2v-EVA-2-0.pcap`"
        )

    # Auto-refresh every REFRESH_S seconds
    time.sleep(_REFRESH_S)
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()


if __name__ == "__main__":
    main()
