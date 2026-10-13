"""Offline tests for the manual data checker."""

from datetime import date
from pathlib import Path

import httpx

from toronto_volunteer_hub.check_manual import check_data


def test_statuses_staleness_and_deduplication(tmp_path: Path) -> None:
    manual = tmp_path / "manual"
    manual.mkdir()
    (manual / "programs.yaml").write_text(
        """- id: old
  url: https://example.org/gone
  signup_url: https://example.org/gone
  last_verified: '2026-08-01'
  sources: [https://example.org/blocked]
""",
        encoding="utf-8",
    )
    (manual / "foodbanks.yaml").write_text(
        """- id: new
  url: https://example.org/ok
  last_verified: '2026-10-13'
  sources: [https://example.org/gone]
""",
        encoding="utf-8",
    )
    requested: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        statuses = {"gone": 404, "blocked": 403, "ok": 200}
        return httpx.Response(statuses[request.url.path.lstrip("/")])

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        report, issues = check_data(
            tmp_path,
            60,
            date(2026, 10, 13),
            client,
            sleep=lambda _: None,
            monotonic=lambda: 0.0,
        )

    assert issues
    assert requested.count("https://example.org/gone") == 1
    assert len(requested) == 3
    assert "old | https://example.org/gone" in report.split("## 需人工看")[0]
    assert "old | https://example.org/blocked" in report.split("## 待重新核实")[0]
    assert "old | 2026-08-01" in report
    assert "new | https://example.org/gone" in report


def test_all_normal(tmp_path: Path) -> None:
    manual = tmp_path / "manual"
    manual.mkdir()
    entry = "- id: ok\n  url: https://example.org/ok\n  last_verified: '2026-10-13'\n"
    (manual / "programs.yaml").write_text(entry, encoding="utf-8")
    (manual / "foodbanks.yaml").write_text("[]\n", encoding="utf-8")
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200))) as client:
        report, issues = check_data(tmp_path, 60, date(2026, 10, 13), client)
    assert not issues
    assert report.count("无") == 3
