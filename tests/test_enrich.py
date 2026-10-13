"""Offline checks for verified enrichment, translation, and caching."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

from toronto_volunteer_hub.enrich import Enricher, main


def _source(data: Path) -> Path:
    path = data / "auto" / "sample.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "source": "sample",
                "status": "ok",
                "fetched_at": "2026-10-13T00:00:00Z",
                "events": [
                    {
                        "id": "sample:1",
                        "source": "sample",
                        "title": "Volunteer 2 hours",
                        "url": "https://example.org/event",
                        "start": "2026-10-14T09:00:00-04:00",
                        "min_age": None,
                        "signup_required": None,
                        "credit": "not-stated",
                        "summary": "Help for 2 hours",
                        "title_zh": None,
                        "summary_zh": None,
                        "evidence": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _event(path: Path) -> dict[str, object]:
    source = json.loads(path.read_text(encoding="utf-8"))
    return source["events"][0]


def _model_json(value: object) -> httpx.Response:
    return httpx.Response(
        200,
        json={"candidates": [{"content": {"parts": [{"text": json.dumps(value)}]}}]},
    )


def test_verified_fields_translation_and_cache(tmp_path: Path) -> None:
    path = _source(tmp_path)
    posts = 0
    gets = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal posts, gets
        if request.method == "GET":
            gets += 1
            assert request.headers["user-agent"].startswith("toronto-volunteer-hub/0.1")
            return httpx.Response(
                200,
                text="<html><head><title>Ignore</title></head><body>Minimum age 14. "
                "Registration required. Volunteer hours letter available.</body></html>",
            )
        posts += 1
        assert request.headers["x-goog-api-key"] == "secret-value"
        assert "secret-value" not in str(request.url)
        if posts == 1:
            return _model_json(
                {
                    "min_age": 14,
                    "signup_required": True,
                    "credit": "stated",
                    "quotes": {
                        "min_age": "Minimum age 14.",
                        "signup_required": "Registration required.",
                        "credit": "Volunteer hours letter available.",
                    },
                }
            )
        if posts == 2:
            return _model_json({"translation": "志愿服务 2 小时"})
        return _model_json({"translation": "帮助 2 小时"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        first = Enricher(tmp_path, ["zh"], "secret-value", "test-model", client)
        first.run()
        assert first.fields_added == 3
        assert first.translations == 2
        assert first.api_calls == 3
        assert _event(path)["min_age"] == 14
        assert _event(path)["title_zh"] == "志愿服务 2 小时"
        evidence = _event(path)["evidence"]
        assert evidence == [
            {"field": "min_age", "quote": "Minimum age 14."},
            {"field": "signup_required", "quote": "Registration required."},
            {"field": "credit", "quote": "Volunteer hours letter available."},
        ]
        source = json.loads(path.read_text(encoding="utf-8"))
        source["events"][0]["min_age"] = None
        source["events"][0]["signup_required"] = None
        source["events"][0]["credit"] = "not-stated"
        source["events"][0]["title_zh"] = None
        source["events"][0]["summary_zh"] = None
        source["events"][0]["evidence"] = []
        path.write_text(json.dumps(source), encoding="utf-8")
        second = Enricher(tmp_path, ["zh"], "secret-value", "test-model", client)
        second.run()
        assert second.api_calls == 0
        assert second.cache_hits == 3
        assert second.fields_added == 3
        assert second.translations == 2
    assert gets == 2
    assert posts == 3


def test_rejects_unverifiable_quote_and_invented_number(tmp_path: Path) -> None:
    path = _source(tmp_path)
    posts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal posts
        if request.method == "GET":
            return httpx.Response(200, text="<body>Minimum age 14.</body>")
        posts += 1
        if posts == 1:
            return _model_json(
                {
                    "min_age": 14,
                    "signup_required": True,
                    "credit": "not-stated",
                    "quotes": {
                        "min_age": "Minimum age 14.",
                        "signup_required": "Registration required.",
                        "credit": "",
                    },
                }
            )
        return _model_json({"translation": "志愿服务 3 小时"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        worker = Enricher(tmp_path, ["zh"], "secret-value", "test-model", client)
        worker.run()
    event = _event(path)
    assert event["min_age"] == 14
    assert event["signup_required"] is None
    assert event["title_zh"] is None
    assert event["summary_zh"] is None
    assert worker.rejected == 3
    evidence = event["evidence"]
    assert evidence == [{"field": "min_age", "quote": "Minimum age 14."}]
    assert sorted(json.loads((tmp_path / "i18n" / "cache.json").read_text()))


def test_missing_key_leaves_files_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = _source(tmp_path)
    before = path.read_bytes()
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["enrich", "--data", str(tmp_path)])
    assert main() == 0
    assert capsys.readouterr().out == "skip: no key\n"
    assert path.read_bytes() == before
    assert not (tmp_path / "i18n").exists()


def test_key_never_appears_in_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _source(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text="<body>Minimum age 14.</body>")
        return httpx.Response(500, text="secret-value")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        worker = Enricher(
            tmp_path,
            ["zh"],
            "secret-value",
            "test-model",
            client,
            sleep=lambda _seconds: None,
        )
        worker.run()
    assert worker.api_calls == 9  # three attempts for each of the three tasks
    output = capsys.readouterr()
    assert "secret-value" not in output.out + output.err
