"""TRCA events calendar adapter."""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import replace
from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

from toronto_volunteer_hub.schema import Credit, Event, Evidence

URL = "https://calendar.trca.ca/?per_page=100"
USER_AGENT = "toronto-volunteer-hub/0.1 (+https://github.com/tovolunteer/tovolunteer.github.io)"
TORONTO = ZoneInfo("America/Toronto")
DATE_TIME = re.compile(r"(\d{4}-\d{2}-\d{2})\s*@\s*(\d{1,2}:\d{2}\s*[AP]M)")
AGE = re.compile(
    r"(?:at least|minimum age(?: of)?|ages?)\s*(\d{1,2})\s*"
    r"(?:years? of age|years? old)?",
    re.I,
)
CREDIT = re.compile(
    r"[^.!?\n]{0,65}(?:high school (?:volunteer|community service) hours|"
    r"secondary school volunteer hour requirements|40\s*hours?)[^.!?\n]{0,65}",
    re.I,
)
SIGNUP = re.compile(r"registration (?:is )?required|must register", re.I)


def local_iso(day: str, clock: str) -> str:
    parsed = datetime.strptime(f"{day} {clock.strip()}", "%Y-%m-%d %I:%M %p")
    return parsed.replace(tzinfo=TORONTO).isoformat()


def claims(raw: str) -> tuple[int | None, bool | None, Credit, list[Evidence]]:
    """Extract only explicit, text backed eligibility claims."""
    snippets = BeautifulSoup(raw, "html.parser").stripped_strings
    evidence: list[Evidence] = []
    min_age: int | None = None
    signup_required: bool | None = None
    credit: Credit = "not-stated"
    for snippet in snippets:
        if min_age is None and (age := AGE.search(snippet)):
            min_age = int(age.group(1))
            evidence.append(Evidence("min_age", age.group(0)))
        if signup_required is None and (signup := SIGNUP.search(snippet)):
            signup_required = True
            evidence.append(Evidence("signup_required", signup.group(0)))
        if credit == "not-stated" and (credit_match := CREDIT.search(snippet)):
            credit = "stated"
            evidence.append(Evidence("credit", credit_match.group(0).strip()))
    return min_age, signup_required, credit, evidence


def parse(html_or_raw: str) -> list[Event]:
    """Parse calendar cards without any network access."""
    soup = BeautifulSoup(html_or_raw, "html.parser")
    today = datetime.now(TORONTO).date()
    events: list[Event] = []
    for card in soup.select(".event_listing"):
        title_node = card.select_one(".wpem-event-title")
        link = card.select_one("a.wpem-event-action-url[href]")
        date_node = card.select_one(".wpem-event-date-time-text")
        if title_node is None or link is None or date_node is None:
            continue
        title = title_node.get_text(" ", strip=True)
        if not re.search(
            r"planting|stewardship|volunteer|clean[ -]?up|litter|restoration", title, re.I
        ):
            continue
        matches = DATE_TIME.findall(date_node.get_text(" ", strip=True))
        if not matches or date.fromisoformat(matches[0][0]) < today:
            continue
        href = link.get("href")
        if not isinstance(href, str):
            continue
        url = str(httpx.URL(URL).join(href))
        age, signup, credit, evidence = claims(str(card))
        location_node = card.select_one(".wpem-event-location-text")
        location = location_node.get_text(" ", strip=True) if location_node else None
        category = "tree-planting" if re.search(r"planting|trees?", title, re.I) else "environment"
        events.append(
            Event(
                id=f"trca:{hashlib.sha256(url.encode()).hexdigest()[:16]}",
                source="trca",
                title=title,
                url=url,
                start=local_iso(*matches[0]),
                end=local_iso(*matches[1]) if len(matches) > 1 else None,
                location=location,
                org="Toronto and Region Conservation Authority",
                category=category,
                min_age=age,
                signup_required=signup,
                credit=credit,
                evidence=evidence,
            )
        )
    return events


def fetch() -> list[Event]:
    """Fetch the calendar and at most 30 relevant detail pages, at 1 request/s."""
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


class TrcaSource:
    name = "trca"

    def fetch(self) -> list[Event]:
        return fetch()
