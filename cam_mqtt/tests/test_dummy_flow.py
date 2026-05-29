"""
test_dummy_flow.py – Minimum pytest suite for the CAM kinematics pipeline.

Tests that work without a broker (no MQTT needed):
  - Module imports
  - Config topics
  - CAM parser (skipped if PCAP absent)

Run from project root:
    pytest cam_mqtt/tests/test_dummy_flow.py -v
"""

import sys
from pathlib import Path

import pytest

# Add cam_mqtt to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

PCAP_PATH = str(Path(__file__).parent.parent.parent / "v2v-EVA-2-0.pcap")
_PCAP_PRESENT = Path(PCAP_PATH).exists()


# ---------------------------------------------------------------------------
# Import / config tests (always run)
# ---------------------------------------------------------------------------

def test_config_imports():
    import config  # noqa: F401


def test_config_topics():
    import config
    assert config.TOPIC_RAW == "cam/raw"
    assert config.TOPIC_KIN == "cam/kinematics"


def test_parser_cam_imports():
    from parser_cam import extract_cam_kinematics  # noqa: F401


def test_producer_kinematics_imports():
    import producer_kinematics  # noqa: F401


# ---------------------------------------------------------------------------
# Parser tests (require PCAP)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _PCAP_PRESENT, reason="PCAP not versioned – provide v2v-EVA-2-0.pcap")
def test_extract_at_least_one_event():
    from parser_cam import extract_cam_kinematics

    ev = next(iter(extract_cam_kinematics(PCAP_PATH)), None)
    assert ev is not None, "No events extracted – check tshark/pyshark and PCAP content"

    for key in ("stationId", "lat", "lon", "speed_kmh", "heading_deg", "ts"):
        assert key in ev, f"Missing key: {key}"

    assert -90.0 <= ev["lat"] <= 90.0, f"lat out of range: {ev['lat']}"
    assert -180.0 <= ev["lon"] <= 180.0, f"lon out of range: {ev['lon']}"
    assert ev["speed_kmh"] >= 0.0


@pytest.mark.skipif(not _PCAP_PRESENT, reason="PCAP not versioned – provide v2v-EVA-2-0.pcap")
def test_multiple_events_and_stations():
    from parser_cam import extract_cam_kinematics

    events = []
    stations = set()
    for ev in extract_cam_kinematics(PCAP_PATH):
        events.append(ev)
        stations.add(ev["stationId"])
        if len(events) >= 100:
            break

    assert len(events) >= 1, "Expected ≥1 events in first 100 packets"
    assert len(stations) >= 1, "Expected ≥1 distinct stationId"
    print(f"\nExtracted {len(events)} events from {len(stations)} station(s): {sorted(stations)}")


@pytest.mark.skipif(not _PCAP_PRESENT, reason="PCAP not versioned – provide v2v-EVA-2-0.pcap")
def test_coordinates_in_italy():
    """Sanity-check: PCAP is recorded in the Turin area (lat≈45, lon≈7)."""
    from parser_cam import extract_cam_kinematics

    lats, lons = [], []
    for ev in extract_cam_kinematics(PCAP_PATH):
        lats.append(ev["lat"])
        lons.append(ev["lon"])
        if len(lats) >= 20:
            break

    if lats:
        avg_lat = sum(lats) / len(lats)
        avg_lon = sum(lons) / len(lons)
        print(f"\nAvg position: lat={avg_lat:.4f} lon={avg_lon:.4f}")
        # Turin area rough bounds
        assert 40.0 <= avg_lat <= 50.0, f"Unexpected avg lat: {avg_lat}"
        assert 5.0 <= avg_lon <= 15.0, f"Unexpected avg lon: {avg_lon}"
