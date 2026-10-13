"""Build a cached map of event and manual-entry coordinates with Nominatim."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from typing import TypeGuard

import httpx
import yaml

URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "toronto-volunteer-hub/0.1 (+https://github.com/tovolunteer/tovolunteer.github.io)"
MIN_INTERVAL = 1.1
MAX_ADDRESSES = 150
RETRY_AFTER = timedelta(days=7)

type Place = dict[str, str | float | None]


def is_string_dict(value: object) -> TypeGuard[dict[str, object]]:
    return isinstance(value, dict)


def is_object_list(value: object) -> TypeGuard[list[object]]:
    return isinstance(value, list)


def clean_address(value: object) -> str | None:
    """Keep only a usable, consistently spaced address."""
    if not isinstance(value, str):
        return None
    cleaned = re.sub(r"\s+,", ",", " ".join(value.split())).strip(" ,")
    if not cleaned or cleaned.lower() == "null":
        return None
    return cleaned


def without_unit(query: str) -> str | None:
    """Remove a leading unit number for a second lookup."""
    shortened = re.sub(
        r"^(?:unit|suite|ste|apt|apartment|#)\s*[\w-]+\s*,?\s*",
        "",
        query,
        count=1,
        flags=re.IGNORECASE,
    )
    return shortened if shortened and shortened != query else None


def collect_addresses(data_dir: Path) -> dict[str, str]:
    addresses: dict[str, str] = {}
    for path in sorted((data_dir / "auto").glob("*.json")):
        document: object = json.loads(path.read_text(encoding="utf-8"))
        if not is_string_dict(document):
            continue
        events: object = document.get("events")
        if not is_object_list(events):
            continue
        for raw_event in events:
            if not is_string_dict(raw_event):
                continue
            identifier: object = raw_event.get("id")
            address = clean_address(raw_event.get("location"))
            if isinstance(identifier, str) and address:
                addresses[identifier] = address

    for name in ("programs.yaml", "foodbanks.yaml"):
        path = data_dir / "manual" / name
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not is_object_list(document):
            continue
        for raw_entry in document:
            if not is_string_dict(raw_entry):
                continue
            identifier = raw_entry.get("id")
            address = clean_address(raw_entry.get("address"))
            if isinstance(identifier, str) and address:
                addresses[identifier] = address
    return addresses


def read_cache(path: Path) -> dict[str, Place]:
    if not path.exists():
        return {}
    document: object = json.loads(path.read_text(encoding="utf-8"))
    if not is_string_dict(document):
        raise ValueError(f"Expected an object in {path}")
    cache: dict[str, Place] = {}
    for identifier, raw_place in document.items():
        if not is_string_dict(raw_place):
            continue
        query: object = raw_place.get("query")
        lat: object = raw_place.get("lat")
        lng: object = raw_place.get("lng")
        checked: object = raw_place.get("checked")
        if not isinstance(query, str):
            continue
        if not (lat is None or isinstance(lat, (int, float))):
            continue
        if not (lng is None or isinstance(lng, (int, float))):
            continue
        place: Place = {"query": query, "lat": lat, "lng": lng}
        if isinstance(checked, str):
            place["checked"] = checked
        cache[identifier] = place
    return cache


def cache_is_fresh(place: Place, query: str, today: date) -> bool:
    if place["query"] != query:
        return False
    if place["lat"] is not None and place["lng"] is not None:
        return True
    checked = place.get("checked")
    if not isinstance(checked, str):
        return False
    try:
        checked_date = date.fromisoformat(checked)
    except ValueError:
        return False
    return today < checked_date + RETRY_AFTER


def lookup(client: httpx.Client, query: str) -> tuple[float, float] | None:
    response = client.get(
        URL,
        params={"q": query, "format": "jsonv2", "limit": "1", "countrycodes": "ca"},
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    results: object = response.json()
    if not is_object_list(results):
        raise ValueError("Nominatim returned a non-list response")
    if not results:
        return None
    first: object = results[0]
    if not is_string_dict(first):
        raise ValueError("Nominatim returned a non-object result")
    raw_lat: object = first.get("lat")
    raw_lng: object = first.get("lon")
    if not isinstance(raw_lat, (str, int, float)) or not isinstance(raw_lng, (str, int, float)):
        raise ValueError("Nominatim returned invalid coordinates")
    lat, lng = float(raw_lat), float(raw_lng)
    if 43.3 <= lat <= 44.5 and -80.2 <= lng <= -78.5:
        return lat, lng
    return None


def geocode(
    data_dir: Path,
    client: httpx.Client,
    *,
    today: date | None = None,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[int, int]:
    """Update the cache; return (addresses attempted, service errors)."""
    current_date = today or date.today()
    addresses = collect_addresses(data_dir)
    cache_path = data_dir / "geo" / "places.json"
    old_cache = read_cache(cache_path)
    cache: dict[str, Place] = {}
    attempted = 0
    errors = 0
    last_request: float | None = None

    def request(query: str) -> tuple[float, float] | None:
        nonlocal last_request
        if last_request is not None:
            elapsed = monotonic() - last_request
            if elapsed < MIN_INTERVAL:
                sleep(MIN_INTERVAL - elapsed)
        last_request = monotonic()
        return lookup(client, query)

    for identifier, query in sorted(addresses.items()):
        prior = old_cache.get(identifier)
        if prior is not None and cache_is_fresh(prior, query, current_date):
            cache[identifier] = prior
            continue
        if attempted >= MAX_ADDRESSES:
            if prior is not None and prior["query"] == query:
                cache[identifier] = prior
            continue
        attempted += 1
        try:
            coordinates = request(query)
            if coordinates is None:
                fallback = without_unit(query)
                if fallback is not None:
                    coordinates = request(fallback)
        except (httpx.HTTPError, ValueError) as exc:
            errors += 1
            print(f"Geocoding {identifier} failed: {exc}", file=sys.stderr)
            if prior is not None and prior["query"] == query:
                cache[identifier] = prior
            continue

        if coordinates is None:
            cache[identifier] = {
                "query": query,
                "lat": None,
                "lng": None,
                "checked": current_date.isoformat(),
            }
        else:
            lat, lng = coordinates
            cache[identifier] = {"query": query, "lat": lat, "lng": lng}

    rendered = json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if not cache_path.exists() or cache_path.read_text(encoding="utf-8") != rendered:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(rendered, encoding="utf-8")
    return attempted, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data"))
    args = parser.parse_args()
    with httpx.Client(timeout=20.0) as client:
        attempted, errors = geocode(args.data, client)
    print(f"Geocoding complete: {attempted} addresses attempted, {errors} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
