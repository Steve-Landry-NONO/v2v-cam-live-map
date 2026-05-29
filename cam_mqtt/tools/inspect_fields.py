#!/usr/bin/env python3
"""
inspect_fields.py – Print all layers and field names for the first N packets.

Usage:
    python cam_mqtt/tools/inspect_fields.py [pcap_path] [--n 20]

Helps debug which fields pyshark/tshark exposes for a given PCAP.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config  # noqa: E402


def inspect(pcap_path: str, n: int = 20) -> None:
    try:
        import pyshark
    except ImportError:
        print("ERROR: pyshark not installed. Run: pip install pyshark && sudo apt install tshark")
        sys.exit(1)

    print(f"Inspecting: {pcap_path}  (first {n} packets)\n")
    cap = pyshark.FileCapture(pcap_path, keep_packets=False)
    cam_count = 0

    try:
        for i, pkt in enumerate(cap):
            try:
                layers = [str(layer.layer_name) for layer in pkt.layers]
                print(f"=== Packet {i + 1} | ts={pkt.sniff_timestamp} | layers={layers}")

                for layer in pkt.layers:
                    name = layer.layer_name
                    try:
                        fields = layer.field_names
                        print(f"  [{name}] fields: {fields}")
                        # Print actual values for interesting layers
                        if name in ("its", "gnw", "btpb"):
                            for f in fields:
                                try:
                                    val = getattr(layer, f)
                                    print(f"    {f} = {val!r}")
                                except Exception:
                                    pass
                            cam_count += 1
                    except Exception as exc:
                        print(f"  [{name}] (field_names error: {exc})")
            except Exception as exc:
                print(f"Packet {i + 1}: error – {exc}")

            if i + 1 >= n:
                break
    finally:
        try:
            cap.close()
        except Exception:
            pass

    print(f"\nDone. Packets with ITS/GNW/BTPB layer: {cam_count}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Inspect pyshark field names in a PCAP")
    ap.add_argument("pcap", nargs="?", default=config.PCAP_PATH, help="Path to PCAP file")
    ap.add_argument("--n", type=int, default=20, help="Number of packets to inspect")
    args = ap.parse_args()
    inspect(args.pcap, args.n)


if __name__ == "__main__":
    main()
