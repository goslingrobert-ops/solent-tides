#!/usr/bin/env python3
"""
solent_tide_heights.py

Pulls free high/low water predictions from the ADMIRALTY UK Tidal API
(Discovery tier) for a named station and prints them as a table.

Requires: requests  (pip install requests)

USAGE
-----
Set your Discovery subscription key as an environment variable first,
rather than pasting it into the script:

    macOS/Linux:   export ADMIRALTY_API_KEY="your-key-here"
    Windows (PS):  $env:ADMIRALTY_API_KEY = "your-key-here"

Then run, e.g.:

    python3 solent_tide_heights.py --station Cowes
    python3 solent_tide_heights.py --station Portsmouth --duration 7
    python3 solent_tide_heights.py --station Cowes --date 2026-08-10

--date filters the output down to a single day (any date within the
next 7, since that's all the free Discovery tier returns).

If you'd rather not use an environment variable, you can pass the key
directly with --key, but env var is the safer habit.

NOTE ON DATA: the Discovery tier only returns High Water / Low Water
EVENTS (time + height at each turn of the tide) â€” not a continuous
height curve, and not tidal streams/currents. Good enough for "when's
high tide", not for modelling flow across the Solent.
"""

import argparse
import os
import sys
from datetime import datetime

import requests

BASE_URL = "https://admiraltyapi.azure-api.net/uktidalapi/api/V1"


def find_station(session, name):
    """Look up a station ID by name. Returns (id, full_name) or exits with a
    helpful message if there's no exact match."""
    resp = session.get(f"{BASE_URL}/Stations", params={"name": name})
    resp.raise_for_status()
    stations = resp.json().get("features", [])

    if not stations:
        sys.exit(f"No station found matching '{name}'.")

    if len(stations) > 1:
        print(f"Multiple stations matched '{name}':")
        for s in stations:
            props = s["properties"]
            print(f"  {props['Id']}: {props['Name']}")
        exact = [s for s in stations if s["properties"]["Name"].lower() == name.lower()]
        if exact:
            stations = exact
        else:
            sys.exit("Please re-run with a more specific --station name matching one of the above.")

    props = stations[0]["properties"]
    return props["Id"], props["Name"]


def get_tidal_events(session, station_id, duration):
    resp = session.get(
        f"{BASE_URL}/Stations/{station_id}/TidalEvents",
        params={"duration": duration},
    )
    resp.raise_for_status()
    return resp.json()


def main():
    parser = argparse.ArgumentParser(description="Free ADMIRALTY tide height predictions.")
    parser.add_argument("--station", required=True, help="Station name, e.g. Cowes, Portsmouth, Southampton")
    parser.add_argument("--duration", type=int, default=7, help="Days ahead, 1-7 (default 7)")
    parser.add_argument("--date", help="Filter to a single date, YYYY-MM-DD")
    parser.add_argument("--key", help="Subscription key (overrides ADMIRALTY_API_KEY env var)")
    args = parser.parse_args()

    api_key = args.key or os.environ.get("ADMIRALTY_API_KEY")
    if not api_key:
        sys.exit(
            "No API key found. Set ADMIRALTY_API_KEY as an environment variable, "
            "or pass --key YOUR_KEY."
        )

    session = requests.Session()
    session.headers.update({"Ocp-Apim-Subscription-Key": api_key})

    station_id, station_name = find_station(session, args.station)
    events = get_tidal_events(session, station_id, args.duration)

    if args.date:
        events = [
            e for e in events
            if e["DateTime"].startswith(args.date)
        ]
        if not events:
            sys.exit(f"No events returned for {station_name} on {args.date}.")

    print(f"\nTide events for {station_name} (station {station_id})\n")
    print(f"{'Date':<12} {'Time (GMT)':<12} {'Type':<6} {'Height (m)':<10}")
    print("-" * 44)
    for e in events:
        dt = datetime.fromisoformat(e["DateTime"].replace("Z", "+00:00"))
        event_type = "HW" if e["EventType"] == "HighWater" else "LW"
        height = e.get("Height")
        height_str = f"{height:.2f}" if height is not None else "n/a"
        print(f"{dt.date()!s:<12} {dt.strftime('%H:%M'):<12} {event_type:<6} {height_str:<10}")

    print(
        "\nHeights are relative to Chart Datum. Times are GMT "
        "(add 1 hour for BST). Source: ADMIRALTY UK Tidal API (Discovery), "
        "Crown copyright."
    )


if __name__ == "__main__":
    main()
