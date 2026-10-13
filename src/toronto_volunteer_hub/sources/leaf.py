"""LEAF events listing adapter."""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import replace
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from bs4.element import Tag

from toronto_volunteer_hub.schema import Event
from toronto_volunteer_hub.sources.trca import TORONTO, USER_AGENT, claims

URL = "https://www.yourleaf.org/events"
WHEN = re.compile(
    r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s*"
    r"([A-Za-z]+ \d{1,2}, \d{4})\s*-\s*"
    r"(\d{1,2}:\d{2}\s*[ap]m)\s+to\s+(\d{1,2}:\d{2}\s*[ap]m)",
    re.I,
)


def _card(heading: Tag) -> Tag:
    parent = heading.find_parent(class_="views-row") or heading.find_parent("article")
    if isinstance(parent, Tag):
        return parent
    ancestor = heading.parent
    if isinstance(ancestor, Tag) and isinstance(ancestor.parent, Tag):
        return ancestor.parent
    return heading


def _when(text: str) -> tuple[str, str] | None:
    match = WHEN.search(text)
    if match is None:
        return None
    day = datetime.strptime(match.group(1), "%B %d, %Y").date()
    start = datetime.strptime(match.group(2).replace(" ", "").upper(), "%I:%M%p")
    end = datetime.strptime(match.group(3).replace(" ", "").upper(), "%I:%M%p")
    return (
        datetime.combine(day, start.time(), TORONTO).isoformat(),
        datetime.combine(day, end.time(), TORONTO).isoformat(),
    )


def parse(html_or_raw: str) -> list[Event]:
    """Parse LEAF listing entries without network access."""
    soup = BeautifulSoup(html_or_raw, "html.parser")
    today = datetime.now(TORONTO).date()
    events: list[Event] = []
    for heading in soup.select("h2"):
        link = heading.find("a", href=True)
        if not isinstance(link, Tag):
            continue
        title = heading.get_text(" ", strip=True)
        if not re.search(r"planting|stewardship|volunteer|clean[ -]?up|restoration", title, re.I):
            continue
        card = _card(heading)
        text = card.get_text(" ", strip=True)
        times = _when(text)
        if times is None or datetime.fromisoformat(times[0]).date() < today:
            continue
        href = link.get("href")
        if not isinstance(href, str):
            continue
        url = str(httpx.URL(URL).join(href))
        age, signup, credit, evidence = claims(str(card))
        location_match = re.search(
            r"Location:\s*(.*?)\s*(?:Event Type:|Read more about|$)", text, re.I
        )
        location = location_match.group(1).strip() if location_match else None
        if location and len(location) > 120:
            location = None
        events.append(
            Event(
                id=f"leaf:{hashlib.sha256(url.encode()).hexdigest()[:16]}",
                source="leaf",
                title=title,
                url=url,
                start=times[0],
                end=times[1],
                location=location,
                org="LEAF",
                category="tree-planting" if "planting" in title.lower() else "environment",
                min_age=age,
                signup_required=signup,
                credit=credit,
                evidence=evidence,
            )
        )
    return events


def fetch() -> list[Event]:
    """Fetch LEAF listing and at most 30 detail pages, at 1 request/s."""
    with httpx.Client(
        headers={"User-Agent": USER_AGENT}, timeout=20, follow_redirects=True
    ) as client:
        response = client.get(URL)
        response.raise_for_status()
        events = parse(response.text)
        enriched: list[Event] = []
        for event in events[:30]:
            time.sleep(1)
            detail = client.get(event.url)
            detail.raise_for_status()
            age, signup, credit, evidence = claims(detail.text)
            enriched.append(
                replace(
                    event,
                    min_age=age if age is not None else event.min_age,
                    signup_required=signup if signup is not None else event.signup_required,
                    credit=credit if credit == "stated" else event.credit,
                    evidence=event.evidence + evidence,
                )
            )
        return enriched + events[30:]


class LeafSource:
    name = "leaf"

    def fetch(self) -> list[Event]:
        return fetch()
