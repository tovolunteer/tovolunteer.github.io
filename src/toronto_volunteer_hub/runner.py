"""Run the registered source adapters and write stable source snapshots."""

from __future__ import annotations

import argparse
import importlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, TypeGuard

from toronto_volunteer_hub.schema import Event, Source, SourceResult
from toronto_volunteer_hub.sources.leaf import LeafSource
from toronto_volunteer_hub.sources.trca import TrcaSource


class SourceFactory(Protocol):
    def __call__(self) -> Source: ...


def _object_dict(value: object) -> TypeGuard[dict[str, object]]:
    return isinstance(value, dict)


def _object_list(value: object) -> TypeGuard[list[object]]:
    return isinstance(value, list)


def sources() -> list[Source]:
    """Return adapters in their scheduled order; city is an optional sibling task."""
    registered: list[Source] = [TrcaSource(), LeafSource()]
    try:
        city_module = importlib.import_module("toronto_volunteer_hub.sources.city")
    except ModuleNotFoundError as exc:
        if exc.name != "toronto_volunteer_hub.sources.city":
            raise
    else:
        city_factory: SourceFactory = city_module.CitySource
        registered.append(city_factory())
    return registered


def _old_events(path: Path) -> list[object]:
    if not path.exists():
        return []
    try:
        data: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if _object_dict(data):
        events = data.get("events")
        if _object_list(events):
            return events
    return []


def _unique(events: list[Event]) -> list[Event]:
    return list({event.id: event for event in events}.values())


def run(out: Path, only: str | None = None, registered: list[Source] | None = None) -> int:
    """Fetch and persist each source. Return 2 if any adapter failed."""
    adapters = sources() if registered is None else registered
    if only is not None:
        adapters = [adapter for adapter in adapters if adapter.name == only]
        if not adapters:
            raise ValueError(f"Unknown source: {only}")
    out.mkdir(parents=True, exist_ok=True)
    failed = False
    for adapter in adapters:
        path = out / f"{adapter.name}.json"
        fetched_at = datetime.now(UTC).isoformat()
        try:
            events = _unique(adapter.fetch())
            count = len(events)
            status = "ok" if events else "empty"
            result = SourceResult(
                source=adapter.name,
                status=status,
                fetched_at=fetched_at,
                events=events,
            )
            payload: dict[str, object] = asdict(result)
        except Exception as exc:
            failed = True
            old_events = _old_events(path)
            count = len(old_events)
            status = "error"
            payload = {
                "source": adapter.name,
                "status": status,
                "fetched_at": fetched_at,
                "events": old_events,
                "error": f"{type(exc).__name__}: {exc}",
            }
        serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if path.exists():
            try:
                previous = path.read_text(encoding="utf-8")
                previous_data: object = json.loads(previous)
            except (OSError, ValueError):
                previous = ""
                previous_data = None
            if _object_dict(previous_data):
                prior_at = previous_data.get("fetched_at")
                candidate = dict(payload)
                candidate["fetched_at"] = prior_at
                if (
                    json.dumps(candidate, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
                    == previous
                ):
                    print(f"{adapter.name}: {status} ({count})")
                    continue
        path.write_text(serialized, encoding="utf-8")
        print(f"{adapter.name}: {status} ({count})")
    return 2 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch Toronto volunteer events")
    parser.add_argument("--only", help="Run just one registered source")
    parser.add_argument("--out", type=Path, default=Path("data/auto"))
    args = parser.parse_args(argv)
    try:
        return run(args.out, args.only)
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
