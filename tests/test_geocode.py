"""Offline checks for geocoding and its persistent cache."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import yaml

from toronto_volunteer_hub.geocode import USER_AGENT, geocode, is_string_dict


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def seed(
    root: Path,
    events: list[dict[str, object]],
    programs: list[dict[str, object]] | None = None,
    foodbanks: list[dict[str, object]] | None = None,
) -> None:
    (root / "auto").mkdir()
    (root / "manual").mkdir()
    (root / "auto" / "events.json").write_text(json.dumps({"events": events}), encoding="utf-8")
    (root / "manual" / "programs.yaml").write_text(yaml.safe_dump(programs or []), encoding="utf-8")
    (root / "manual" / "foodbanks.yaml").write_text(
        yaml.safe_dump(foodbanks or []), encoding="utf-8"
    )


def places(root: Path) -> dict[str, object]:
    result: object = json.loads((root / "geo" / "places.json").read_text(encoding="utf-8"))
    assert is_string_dict(result)
    return result


def test_collect_clean_cache_and_rate_limit(tmp_path: Path) -> None:
    seed(
        tmp_path,
        [
            {"id": "event-b", "location": "  Unit 3,  5 Main St , Toronto  "},
            {"id": "event-a", "location": "10 Queen St , Toronto"},
            {"id": "no-location", "location": None},
        ],
        [{"id": "area-only", "area": "Toronto"}],
        [{"id": "food", "address": "20 King St, Toronto"}, {"id": "null", "address": "null"}],
    )
    clock = Clock()
    seen: list[tuple[str, float]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        query = request.url.params["q"]
        seen.append((query, clock.now))
        assert request.headers["User-Agent"] == USER_AGENT
        assert request.url.params["format"] == "jsonv2"
        assert request.url.params["limit"] == "1"
        assert request.url.params["countrycodes"] == "ca"
        if query.startswith("Unit"):
            return httpx.Response(200, json=[])
        return httpx.Response(200, json=[{"lat": "43.7", "lon": "-79.4"}])

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert geocode(
            tmp_path,
            client,
            today=date(2026, 10, 13),
            monotonic=clock.monotonic,
            sleep=clock.sleep,
        ) == (3, 0)
        first_content = (tmp_path / "geo" / "places.json").read_text(encoding="utf-8")
        first_mtime = (tmp_path / "geo" / "places.json").stat().st_mtime_ns
        assert geocode(
            tmp_path,
            client,
            today=date(2026, 10, 14),
            monotonic=clock.monotonic,
            sleep=clock.sleep,
        ) == (0, 0)

    assert [query for query, _ in seen] == [
        "10 Queen St, Toronto",
        "Unit 3, 5 Main St, Toronto",
        "5 Main St, Toronto",
        "20 King St, Toronto",
    ]
    assert all(right - left >= 1.1 for (_, left), (_, right) in zip(seen, seen[1:], strict=False))
    assert places(tmp_path) == {
        identifier: {"lat": 43.7, "lng": -79.4, "query": query}
        for identifier, query in (
            ("event-a", "10 Queen St, Toronto"),
            ("event-b", "Unit 3, 5 Main St, Toronto"),
            ("food", "20 King St, Toronto"),
        )
    }
    assert (tmp_path / "geo" / "places.json").read_text(encoding="utf-8") == first_content
    assert (tmp_path / "geo" / "places.json").stat().st_mtime_ns == first_mtime


def test_misses_retry_after_seven_days_and_prune_removed_ids(tmp_path: Path) -> None:
    seed(tmp_path, [{"id": "miss", "location": "1 Main St"}])
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.params["q"])
        return httpx.Response(200, json=[{"lat": "45.0", "lon": "-79.4"}])

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert geocode(tmp_path, client, today=date(2026, 10, 1)) == (1, 0)
        assert places(tmp_path) == {
            "miss": {"query": "1 Main St", "lat": None, "lng": None, "checked": "2026-10-01"}
        }
        assert geocode(tmp_path, client, today=date(2026, 10, 7)) == (0, 0)
        assert geocode(tmp_path, client, today=date(2026, 10, 8)) == (1, 0)
        (tmp_path / "auto" / "events.json").write_text('{"events": []}', encoding="utf-8")
        assert geocode(tmp_path, client, today=date(2026, 10, 9)) == (0, 0)
    assert calls == ["1 Main St", "1 Main St"]
    assert places(tmp_path) == {}


def test_network_error_is_not_cached_and_changed_query_is_refetched(tmp_path: Path) -> None:
    seed(tmp_path, [{"id": "event", "location": "1 Old St"}])
    queries: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        query = request.url.params["q"]
        queries.append(query)
        if query == "1 New St":
            raise httpx.ConnectError("offline")
        return httpx.Response(200, json=[{"lat": "43.7", "lon": "-79.4"}])

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert geocode(tmp_path, client) == (1, 0)
        (tmp_path / "auto" / "events.json").write_text(
            '{"events": [{"id": "event", "location": "1 New St"}]}', encoding="utf-8"
        )
        assert geocode(tmp_path, client) == (1, 1)
        assert places(tmp_path) == {}
        assert geocode(tmp_path, client) == (1, 1)
    assert queries == ["1 Old St", "1 New St", "1 New St"]


def test_limits_new_addresses_per_run(tmp_path: Path) -> None:
    seed(
        tmp_path,
        [{"id": f"event-{index:03}", "location": f"{index} Main St"} for index in range(151)],
    )
    clock = Clock()
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=[])

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert geocode(
            tmp_path,
            client,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
        ) == (150, 0)
    assert calls == 150
    assert len(places(tmp_path)) == 150
