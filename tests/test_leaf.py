from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

from toronto_volunteer_hub.sources import leaf

FIXTURES = Path(__file__).parent / "fixtures" / "leaf"


def test_listing_and_eligibility() -> None:
    raw = (FIXTURES / "listing.html").read_text(encoding="utf-8").replace("2026", "2099")
    events = leaf.parse(raw)
    assert len(events) == 2
    event = events[0]
    assert event.title == "Community Tree Planting in Bluff Trail (Nobleton)"
    assert event.start == "2099-10-17T13:00:00-04:00"
    assert event.signup_required is True
    assert event.min_age is None
    assert event.credit == "not-stated"
    visible = BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
    assert all(item.quote in visible for item in event.evidence)
    assert leaf.parse(raw.replace("2099", "2020")) == []


def test_detail_credit_does_not_invent_age_minimum() -> None:
    raw = (FIXTURES / "detail.html").read_text(encoding="utf-8")
    age, signup, credit, evidence = leaf.claims(raw)
    assert (age, signup, credit) == (None, True, "stated")
    visible = BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
    assert all(item.quote in visible for item in evidence)
    assert all(item.quote in raw for item in evidence)
