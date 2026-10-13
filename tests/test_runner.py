from __future__ import annotations

import json
from pathlib import Path

from toronto_volunteer_hub.runner import run
from toronto_volunteer_hub.schema import Event


class StubSource:
    def __init__(self, name: str, events: list[Event] | None = None, fail: bool = False) -> None:
        self.name = name
        self.events = events or []
        self.fail = fail

    def fetch(self) -> list[Event]:
        if self.fail:
            raise RuntimeError("temporary failure")
        return self.events


def sample() -> Event:
    return Event(
        id="trca:one",
        source="trca",
        title="Tree planting",
        url="https://example.org/one",
        start="2099-10-14T13:00:00-04:00",
    )


def test_error_keeps_events_and_sets_exit_code(tmp_path: Path) -> None:
    assert run(tmp_path, registered=[StubSource("trca", [sample()])]) == 0
    assert run(tmp_path, registered=[StubSource("trca", fail=True)]) == 2
    data = json.loads((tmp_path / "trca.json").read_text(encoding="utf-8"))
    assert data["status"] == "error"
    assert data["events"][0]["id"] == "trca:one"
    assert "temporary failure" in data["error"]


def test_empty_and_stable_output(tmp_path: Path) -> None:
    adapter = StubSource("trca", [sample(), sample()])
    assert run(tmp_path, registered=[adapter]) == 0
    path = tmp_path / "trca.json"
    first = path.read_bytes()
    assert run(tmp_path, registered=[adapter]) == 0
    assert path.read_bytes() == first
    assert len(json.loads(first)["events"]) == 1
    assert run(tmp_path, registered=[StubSource("trca")]) == 0
    assert json.loads(path.read_text(encoding="utf-8"))["status"] == "empty"
