"""Check links and verification dates in manually maintained data."""

import argparse
import socket
import time
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any, TypeGuard

import httpx
import yaml

USER_AGENT = "toronto-volunteer-hub/0.1 (+https://github.com/tovolunteer/tovolunteer.github.io)"
URL_FIELDS = ("url", "signup_url", "volunteer_url", "find_food_url")


def _is_object_list(value: object) -> TypeGuard[list[object]]:
    return isinstance(value, list)


def _is_entry(value: object) -> TypeGuard[dict[str, Any]]:
    return isinstance(value, dict)


def _entries(data_dir: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for name in ("programs.yaml", "foodbanks.yaml"):
        with (data_dir / "manual" / name).open(encoding="utf-8") as source:
            loaded: Any = yaml.safe_load(source)
        if _is_object_list(loaded):
            entries.extend(item for item in loaded if _is_entry(item))
    return entries


def _urls(entry: dict[str, Any]) -> set[str]:
    values = [entry.get(field) for field in URL_FIELDS]
    sources = entry.get("sources")
    if _is_object_list(sources):
        values.extend(sources)
    return {value for value in values if isinstance(value, str) and value}


def _is_dns_error(error: BaseException) -> bool:
    current: BaseException | None = error
    while current is not None:
        if isinstance(current, socket.gaierror):
            return True
        current = current.__cause__
    return False


def check_data(
    data_dir: Path,
    stale_days: int,
    today: date,
    client: httpx.Client,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> tuple[str, bool]:
    """Return the report and whether any issue was found."""
    broken: list[str] = []
    review: list[str] = []
    stale: list[str] = []
    checked: dict[str, str] = {}
    last_request: float | None = None

    for entry in _entries(data_dir):
        identifier = str(entry["id"])
        verified = date.fromisoformat(str(entry["last_verified"]))
        if (today - verified).days > stale_days:
            stale.append(f"{identifier} | {verified.isoformat()}")

        for url in sorted(_urls(entry)):
            if url not in checked:
                if last_request is not None:
                    elapsed = monotonic() - last_request
                    if elapsed < 1:
                        sleep(1 - elapsed)
                last_request = monotonic()
                try:
                    response = client.get(url)
                    if response.status_code in (404, 410):
                        checked[url] = "broken"
                    elif (
                        response.status_code in (403, 429)
                        or response.status_code >= 500
                        or response.status_code >= 400
                    ):
                        checked[url] = "review"
                    else:
                        checked[url] = "ok"
                except httpx.ConnectError as exc:
                    if _is_dns_error(exc):
                        checked[url] = "broken"
                    else:
                        checked[url] = "review"
                except httpx.RequestError:
                    checked[url] = "review"

            if checked[url] == "broken":
                broken.append(f"{identifier} | {url}")
            elif checked[url] == "review":
                review.append(f"{identifier} | {url}")

    sections = (
        ("失效", broken),
        ("需人工看", review),
        ("待重新核实", stale),
    )
    report = (
        "\n\n".join(
            f"## {heading}\n\n" + ("\n".join(rows) if rows else "无") for heading, rows in sections
        )
        + "\n"
    )
    return report, any(rows for _, rows in sections)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--stale-days", type=int, default=60)
    parser.add_argument("--out", type=Path, default=Path("report.md"))
    args = parser.parse_args()
    if args.stale_days < 0:
        parser.error("--stale-days must be nonnegative")
    with httpx.Client(
        follow_redirects=True, timeout=20, headers={"User-Agent": USER_AGENT}
    ) as client:
        report, issues = check_data(args.data, args.stale_days, date.today(), client)
    args.out.write_text(report, encoding="utf-8")
    return int(issues)


if __name__ == "__main__":
    raise SystemExit(main())
