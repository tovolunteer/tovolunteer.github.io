from __future__ import annotations

from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

from toronto_volunteer_hub.sources import trca

FIXTURES = Path(__file__).parent / "fixtures" / "trca"


def test_listing_filters_and_missing_claims() -> None:
    raw = (FIXTURES / "listing.html").read_text(encoding="utf-8").replace("2026", "2099")
    events = trca.parse(raw)
    assert [event.title for event in events] == [
        "Conservation Youth Corps | eBird Challenge & Litter Clean Up",
        "Downsview Park Community Planting",
    ]
    assert events[0].start == "2099-10-14T16:00:00-04:00"
    assert events[0].min_age is None
    assert events[0].signup_required is None
    assert events[0].credit == "not-stated"
    assert events[0].evidence == []
    assert (
        trca.parse(raw.replace("2099-10-14", "2020-10-14"))[0].title
        == "Downsview Park Community Planting"
    )


def test_detail_claims_are_verbatim() -> None:
    raw = (FIXTURES / "detail.html").read_text(encoding="utf-8")
    age, signup, credit, evidence = trca.claims(raw)
    assert (age, signup, credit) == (14, None, "stated")
    visible = BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
    assert all(item.quote in visible for item in evidence)
    assert all(item.quote in raw for item in evidence)


def test_toronto_winter_offset() -> None:
    offset = datetime.fromisoformat(trca.local_iso("2026-12-01", "04:00 PM")).utcoffset()
    assert offset is not None
    assert offset.total_seconds() == -18000
