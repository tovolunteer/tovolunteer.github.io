"""Data contract shared by every source adapter and the site (site reads data/auto/*.json)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal, Protocol

Category = Literal["tree-planting", "environment", "food-bank", "other"]
Credit = Literal["stated", "not-stated"]  # 40h school form / hours letter mentioned in source text?


@dataclass(frozen=True)
class Evidence:
    """A verbatim snippet from the source page backing an extracted field."""

    field: str
    quote: str


@dataclass(frozen=True)
class Event:
    id: str  # stable: f"{source}:{source-specific id or url hash}"
    source: str  # adapter name, e.g. "trca"
    title: str
    url: str  # original page; users always click through
    start: str  # ISO 8601 with offset, America/Toronto
    end: str | None = None
    location: str | None = None
    org: str | None = None
    category: Category = "other"
    min_age: int | None = None  # None = not stated
    signup_required: bool | None = None  # None = not stated
    credit: Credit = "not-stated"
    summary: str | None = None  # English, from source (<= 300 chars)
    title_zh: str | None = None
    summary_zh: str | None = None
    evidence: list[Evidence] = field(default_factory=lambda: [])

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SourceResult:
    """Written to data/auto/<source>.json. status=error keeps previous events (see runner)."""

    source: str
    status: Literal["ok", "empty", "error"]
    fetched_at: str  # ISO 8601 UTC
    events: list[Event]
    error: str | None = None


class Source(Protocol):
    name: str

    def fetch(self) -> list[Event]:
        """Return upcoming events. Raise on failure; return [] only if the source truly has none."""
        ...
