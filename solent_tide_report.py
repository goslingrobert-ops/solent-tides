#!/usr/bin/env python3
"""
solent_tide_report.py

Pulls free high/low water predictions from the ADMIRALTY UK Tidal API
(Discovery tier) for a list of Solent stations and writes them to a CSV.

Designed to be run by a GitHub Actions workflow on a schedule, but works
fine run locally too.

Requires: requests

Environment variables:
    ADMIRALTY_API_KEY  - your Discovery subscription key (required)
    STATIONS           - comma-separated station names
                          (default: Portsmouth,Southampton,Cowes)
    OUTPUT_FILE         - path to write CSV to (default: tide_data.csv)

NOTE ON DATA: the Discovery tier only returns High Water / Low Water
EVENTS (time + height at each turn of the tide), not a continuous
height curve, and not tidal streams/currents.
"""

import csv
import os
import sys
from datetime import datetime, timezone

import requests

BASE_URL = "https://admiraltyapi.azure-api.net/uktidalapi/api/V1"


def find_station(session, name):
    resp = session.get(f"{BASE_URL}/Stations", params={"name": name})
    resp.raise_for_status()
    stations = resp.json().get("features", [])

    if not stations:
        print(f"WARNING: no station found matching '{name}', skipping.", file=sys.stderr)
        return None, None

    exact = [s for s in stations if s["properties"]["Name"].lower() == name.lower()]
    chosen = exact[0] if exact else stations[0]
    props = chosen["properties"]
    return props["Id"], props["Name"]


def get_tidal_events(session, station_id, duration=7):
    resp = session.get(
        f"{BASE_URL}/Stations/{station_id}/TidalEvents",
        params={"duration": duration},
    )
    resp.raise_for_status()
    return resp.json()


def main():
    api_key = os.environ.get("ADMIRALTY_API_KEY")
    if not api_key:
        sys.exit("ADMIRALTY_API_KEY environment variable not set.")

    station_names = [
        s.strip() for s in os.environ.get("STATIONS", "Portsmouth,Southampton,Cowes").split(",")
        if s.strip()
    ]
    output_file = os.environ.get("OUTPUT_FILE", "tide_data.csv")

    session = requests.Session()
    session.headers.update({"Ocp-Apim-Subscription-Key": api_key})

    rows = []
    for name in station_names:
        station_id, station_name = find_station(session, name)
        if station_id is None:
            continue
        events = get_tidal_events(session, station_id)
        for e in events:
            dt = datetime.fromisoformat(e["DateTime"].replace("Z", "+00:00"))
            event_type = "HW" if e["EventType"] == "HighWater" else "LW"
            height = e.get("Height")
            rows.append({
                "station": station_name,
                "date": dt.date().isoformat(),
                "time_gmt": dt.strftime("%H:%M"),
                "event": event_type,
                "height_m": f"{height:.2f}" if height is not None else "",
            })

    if not rows:
        sys.exit("No data retrieved for any station, nothing written.")

    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["station", "date", "time_gmt", "event", "height_m"])
        writer.writeheader()
        writer.writerows(rows)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"Wrote {len(rows)} rows to {output_file} at {generated_at}")


if __name__ == "__main__":
    main()
