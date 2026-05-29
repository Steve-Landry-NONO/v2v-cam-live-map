"""
parser_cam.py – Extract CAM kinematic events from a PCAP file via pyshark/tshark.

Priority:
  1. ITS layer  (packet.its.*)
  2. GeoNetworking header  (packet.gnw.geonw_src_pos_*)

Unit normalisation:
  - lat / lon : raw value is 1e-7 degrees (ITS standard) → divide by 1e7
  - speed     : 0.01 m/s per unit → * 0.01 * 3.6 = km/h
  - heading   : 0.1 degree per unit → / 10
"""

import logging
import time
from typing import Iterator

log = logging.getLogger(__name__)

# ITS "unavailable" sentinels (ISO 21217 / ETSI EN 302 637-2)
_UNAVAIL_LAT = 900000001
_UNAVAIL_LON = 1800000001
_UNAVAIL_SPEED = 16383
_UNAVAIL_HEADING = 3601


def _to_int(v) -> int:
    """Parse a pyshark field value (may be decimal or '0x…' hex string)."""
    s = str(v).strip()
    try:
        return int(s, 0)
    except ValueError:
        return int(float(s))


def _to_signed32(v) -> int:
    """Two's-complement conversion for 32-bit values."""
    n = _to_int(v)
    if n >= (1 << 31):
        n -= (1 << 32)
    return n


def _norm_speed(raw) -> float:
    v = _to_int(raw)
    if v >= _UNAVAIL_SPEED:
        return 0.0
    return round(v * 0.01 * 3.6, 2)


def _norm_heading(raw) -> float:
    v = _to_int(raw)
    if v >= _UNAVAIL_HEADING:
        return 0.0
    return round(v / 10.0, 1)


def _valid_coords(lat: float, lon: float) -> bool:
    return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0


def _try_its(pkt, ts: float) -> dict | None:
    """Extract kinematics from ITS dissector layer."""
    if not hasattr(pkt, "its"):
        return None
    try:
        its = pkt.its
        lat_raw = _to_int(its.latitude)
        lon_raw = _to_int(its.longitude)
        if lat_raw == _UNAVAIL_LAT or lon_raw == _UNAVAIL_LON:
            return None
        lat = _to_signed32(lat_raw) / 1e7
        lon = _to_signed32(lon_raw) / 1e7
        if not _valid_coords(lat, lon):
            log.debug("ITS: invalid coords lat=%.7f lon=%.7f – skipped", lat, lon)
            return None
        return {
            "stationId": str(_to_int(its.stationid)),
            "lat": round(lat, 7),
            "lon": round(lon, 7),
            "speed_kmh": _norm_speed(its.speedvalue),
            "heading_deg": _norm_heading(its.headingvalue),
            "ts": ts,
        }
    except AttributeError as exc:
        log.debug("ITS layer incomplete: %s", exc)
        return None


def _try_gnw(pkt, ts: float) -> dict | None:
    """Extract kinematics from GeoNetworking header (fallback)."""
    if not hasattr(pkt, "gnw"):
        return None
    try:
        gnw = pkt.gnw
        lat = _to_signed32(gnw.geonw_src_pos_lat) / 1e7
        lon = _to_signed32(gnw.geonw_src_pos_long) / 1e7
        if not _valid_coords(lat, lon):
            log.debug("GNW: invalid coords lat=%.7f lon=%.7f – skipped", lat, lon)
            return None
        station_id = str(getattr(gnw, "geonw_src_pos_addr_mid", "unknown"))
        return {
            "stationId": station_id,
            "lat": round(lat, 7),
            "lon": round(lon, 7),
            "speed_kmh": _norm_speed(gnw.geonw_src_pos_speed),
            "heading_deg": _norm_heading(gnw.geonw_src_pos_hdg),
            "ts": ts,
        }
    except AttributeError as exc:
        log.debug("GNW layer incomplete: %s", exc)
        return None


def extract_cam_kinematics(pcap_path: str) -> Iterator[dict]:
    """
    Yield CAM kinematic event dicts from *pcap_path*.

    Each event: {stationId, lat, lon, speed_kmh, heading_deg, ts}
    """
    try:
        import pyshark
    except ImportError:
        raise ImportError(
            "pyshark is not installed.\n"
            "  pip install pyshark\n"
            "  sudo apt install tshark"
        )

    cap = pyshark.FileCapture(pcap_path, keep_packets=False)
    try:
        for pkt in cap:
            try:
                ts = float(pkt.sniff_timestamp)
            except Exception:
                ts = time.time()

            ev = _try_its(pkt, ts) or _try_gnw(pkt, ts)
            if ev:
                yield ev
            else:
                log.debug("pkt ts=%.3f: no CAM kinematics", ts)
    finally:
        try:
            cap.close()
        except Exception:
            pass
