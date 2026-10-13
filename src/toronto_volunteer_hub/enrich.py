"""Verify source-backed fields and cache Gemini translations for scraped events."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import time
from collections.abc import Callable
from html.parser import HTMLParser
from pathlib import Path
from typing import TypeGuard

import httpx

USER_AGENT = "toronto-volunteer-hub/0.1 (+https://github.com/tovolunteer/tovolunteer.github.io)"
DEFAULT_MODEL = "gemini-3.5-flash-lite"
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
FIELDS = ("min_age", "signup_required", "credit")


def _is_mapping(value: object) -> TypeGuard[dict[str, object]]:
    return isinstance(value, dict)


def _mapping(value: object) -> dict[str, object] | None:
    return value if _is_mapping(value) else None


def _is_list(value: object) -> TypeGuard[list[object]]:
    return isinstance(value, list)


def _list(value: object) -> list[object] | None:
    return value if _is_list(value) else None


def _normalize(value: str) -> str:
    return " ".join(value.split())


class _BodyParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "head", "noscript"}:
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "head", "noscript"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def _body(html: str) -> str:
    parser = _BodyParser()
    parser.feed(html)
    return _normalize(" ".join(parser.parts))


def _key(task: str, language: str, source: str) -> str:
    return hashlib.sha256(f"{task}\0{language}\0{source}".encode()).hexdigest()


def _atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = stream.name
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)


class Enricher:
    def __init__(
        self,
        data: Path,
        languages: list[str],
        key: str,
        model: str,
        client: httpx.Client,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.data = data
        self.languages = languages
        self.key = key
        self.model = model
        self.client = client
        self.sleep = sleep
        self.monotonic = monotonic
        self.cache_path = data / "i18n" / "cache.json"
        self.cache: dict[str, object] = {}
        self.cache_dirty = False
        self.fields_added = 0
        self.translations = 0
        self.cache_hits = 0
        self.api_calls = 0
        self.rejected = 0
        self.pages = 0
        self.last_page_request: float | None = None
        try:
            cached = _mapping(json.loads(self.cache_path.read_text(encoding="utf-8")))
            if cached is not None:
                self.cache = cached
        except (OSError, ValueError):
            pass

    def _page(self, url: str) -> str | None:
        if self.pages >= 40:
            return None
        if self.last_page_request is not None:
            remaining = 1.0 - (self.monotonic() - self.last_page_request)
            if remaining > 0:
                self.sleep(remaining)
        self.last_page_request = self.monotonic()
        self.pages += 1
        try:
            response = self.client.get(url, headers={"User-Agent": USER_AGENT}, timeout=20.0)
            response.raise_for_status()
            return _body(response.text)
        except (httpx.HTTPError, ValueError):
            return None

    def _generate(self, prompt: str) -> tuple[object | None, bool]:
        url = API_URL.format(model=self.model)
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        for retry in range(3):
            if self.api_calls >= 120:
                return None, False
            self.api_calls += 1
            try:
                response = self.client.post(
                    url,
                    headers={"x-goog-api-key": self.key},
                    json=payload,
                    timeout=30.0,
                )
                if response.status_code == 429 or response.status_code >= 500:
                    if retry < 2:
                        self.sleep(float(2**retry))
                        continue
                    return None, False
                response.raise_for_status()
                try:
                    outer = _mapping(response.json())
                except ValueError:
                    return None, True
                candidates = _list(outer.get("candidates")) if outer is not None else None
                candidate = _mapping(candidates[0]) if candidates else None
                content = _mapping(candidate.get("content")) if candidate is not None else None
                parts = _list(content.get("parts")) if content is not None else None
                part = _mapping(parts[0]) if parts else None
                text = part.get("text") if part is not None else None
                if not isinstance(text, str):
                    return None, True
                try:
                    return json.loads(text), True
                except ValueError:
                    return None, True
            except httpx.HTTPError:
                return None, False
        return None, False

    def _remember(self, cache_key: str, value: object) -> None:
        self.cache[cache_key] = value
        self.cache_dirty = True

    def _fields(self, event: dict[str, object]) -> bool:
        needs = (
            event.get("min_age") is None
            or event.get("signup_required") is None
            or event.get("credit") == "not-stated"
        )
        url = event.get("url")
        if not needs or not isinstance(url, str):
            return False
        body = self._page(url)
        if not body:
            return False
        body_hash = hashlib.sha256(body.encode()).hexdigest()
        cache_key = _key("fields", "", f"{url}\0{body_hash}")
        if cache_key in self.cache:
            self.cache_hits += 1
            validated = _mapping(self.cache[cache_key])
        else:
            prompt = (
                "Extract only facts stated in the source text. Return exactly a JSON object "
                'with keys "min_age" (integer or null), "signup_required" (boolean or null), '
                '"credit" ("stated" or "not-stated"), and "quotes" (object with keys '
                '"min_age", "signup_required", "credit" containing verbatim supporting '
                "quotes or empty strings). Credit means volunteer hours or a school form. "
                f"Source URL: {url}\nSource text: {body}"
            )
            raw, received = self._generate(prompt)
            if not received:
                return False
            validated = self._validate_fields(raw, body)
            self._remember(cache_key, validated)
        if validated is None:
            return False
        quotes = _mapping(validated.get("quotes"))
        if quotes is None:
            return False
        changed = False
        evidence = _list(event.get("evidence")) or []
        for field in FIELDS:
            value = validated.get(field)
            if value is None or (field == "credit" and value != "stated"):
                continue
            if field == "credit":
                if event.get(field) != "not-stated":
                    continue
            elif event.get(field) is not None:
                continue
            quote = quotes.get(field)
            if not isinstance(quote, str):
                continue
            event[field] = value
            evidence.append({"field": field, "quote": quote})
            self.fields_added += 1
            changed = True
        if changed:
            event["evidence"] = evidence
        return changed

    def _validate_fields(self, raw: object, body: str) -> dict[str, object] | None:
        data = _mapping(raw)
        if data is None or set(data) != {*FIELDS, "quotes"}:
            self.rejected += 1
            return None
        quotes = _mapping(data["quotes"])
        if quotes is None or set(quotes) != set(FIELDS):
            self.rejected += 1
            return None
        age = data["min_age"]
        signup = data["signup_required"]
        credit = data["credit"]
        if (
            (age is not None and (type(age) is not int or age < 0))
            or (signup is not None and type(signup) is not bool)
            or not isinstance(credit, str)
            or credit not in {"stated", "not-stated"}
        ):
            self.rejected += 1
            return None
        result: dict[str, object] = {
            "min_age": None,
            "signup_required": None,
            "credit": "not-stated",
            "quotes": {field: "" for field in FIELDS},
        }
        accepted_quotes: dict[str, str] = {}
        for field, value in (("min_age", age), ("signup_required", signup), ("credit", credit)):
            if value is None or (field == "credit" and value == "not-stated"):
                continue
            quote = quotes[field]
            if not isinstance(quote, str) or not _normalize(quote) or _normalize(quote) not in body:
                self.rejected += 1
                continue
            if (
                field == "min_age"
                and isinstance(value, int)
                and str(value) not in re.findall(r"\d+", quote)
            ):
                self.rejected += 1
                continue
            result[field] = value
            accepted_quotes[field] = quote
        result["quotes"] = accepted_quotes
        return result

    def _translation(self, event: dict[str, object], field: str, language: str) -> bool:
        original = event.get(field)
        if not isinstance(original, str) or not original:
            return False
        target = f"{field}_{language}"
        if language == "zh" and event.get(target) is not None:
            return False
        cache_key = _key("translation", language, original)
        if cache_key in self.cache:
            self.cache_hits += 1
            value = self.cache[cache_key]
        else:
            prompt = (
                f"Translate this {field} into language {language}. Preserve all factual "
                'numbers. Return exactly JSON with one key "translation" containing a string. '
                f"Original: {original}"
            )
            raw, received = self._generate(prompt)
            if not received:
                return False
            data = _mapping(raw)
            value = (
                data.get("translation")
                if data is not None and set(data) == {"translation"}
                else None
            )
            if (
                not isinstance(value, str)
                or not value
                or len(value) > len(original) * 3
                or not set(re.findall(r"\d+", value)).issubset(set(re.findall(r"\d+", original)))
            ):
                value = None
                self.rejected += 1
            self._remember(cache_key, value)
        if not isinstance(value, str):
            return False
        if language == "zh":
            event[target] = value
        self.translations += 1
        return language == "zh"

    def run(self) -> None:
        for path in sorted((self.data / "auto").glob("*.json")):
            try:
                document = _mapping(json.loads(path.read_text(encoding="utf-8")))
                if document is None:
                    continue
                events = _list(document.get("events"))
                if events is None:
                    continue
                changed = False
                for index, item in enumerate(events):
                    event = _mapping(item)
                    if event is None:
                        continue
                    changed |= self._fields(event)
                    for language in self.languages:
                        changed |= self._translation(event, "title", language)
                        changed |= self._translation(event, "summary", language)
                    events[index] = event
                if changed:
                    document["events"] = events
                    _atomic_json(path, document)
            except Exception:
                # A failed source file never replaces its original contents.
                continue
        if self.cache_dirty:
            _atomic_json(self.cache_path, self.cache)
        print(
            f"enrich: fields_added={self.fields_added} translations={self.translations} "
            f"cache_hits={self.cache_hits} api_calls={self.api_calls} rejected={self.rejected}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--langs", default="zh")
    args = parser.parse_args()
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        print("skip: no key")
        return 0
    languages = list(dict.fromkeys(part.strip() for part in args.langs.split(",") if part.strip()))
    if not languages or any(
        re.fullmatch(r"[A-Za-z][A-Za-z0-9-]*", item) is None for item in languages
    ):
        parser.error("--langs must contain comma-separated language codes")
    with httpx.Client() as client:
        Enricher(
            args.data, languages, key, os.environ.get("GEMINI_MODEL", DEFAULT_MODEL), client
        ).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
