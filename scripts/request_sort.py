#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main() -> int:
    args = parse_args()
    state_dir = Path(args.state_dir).expanduser()
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / "requester_state.json"
    today = date.today().isoformat()

    base_url = f"http://{args.host}:{args.port}"
    try:
        health = request_json(f"{base_url}/health")
    except HTTPError as error:
        payload = read_error_payload(error)
        print(
            f"Anki VN Sorter health check failed: {payload or error}",
            file=sys.stderr,
        )
        return 1
    except URLError as error:
        print(f"Anki VN Sorter is unavailable: {error}")
        return 0

    if not health.get("ready"):
        print("Anki VN Sorter is not ready yet.")
        return 0

    profile_name = profile_name_from_health(health)
    if not args.force and load_last_success(state_path, profile_name) == today:
        print(
            f'Anki VN Sorter already succeeded today ({today}) for profile "{profile_name}".'
        )
        return 0

    try:
        response = request_json(f"{base_url}/sort", method="POST", body={})
    except HTTPError as error:
        payload = read_error_payload(error)
        print(
            f"Anki VN Sorter returned an error: {payload or error}",
            file=sys.stderr,
        )
        return 1
    except URLError as error:
        print(f"Anki VN Sorter sort request could not connect: {error}")
        return 0

    summary = response.get("summary", {})
    if not isinstance(summary, dict):
        print("Anki VN Sorter returned an invalid summary payload.", file=sys.stderr)
        return 1

    save_last_success(state_path, profile_name, today)
    candidate_count = summary.get("candidateCount", 0)
    repositioned_count = summary.get("repositionedCount", 0)
    if summary.get("skippedForToday"):
        print(f'Anki VN Sorter already ran today for profile "{profile_name}".')
        return 0
    if summary.get("applied"):
        print(
            f"Anki VN Sorter repositioned {repositioned_count} cards out of {candidate_count} candidates."
        )
    else:
        print(f"Anki VN Sorter found {candidate_count} candidates and made no changes.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Request a daily Anki VN sort run.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument(
        "--state-dir",
        default="~/.local/state/anki-vn-sorter",
        help="Directory that stores the once-per-day requester state.",
    )
    parser.add_argument("--force", action="store_true", help="Ignore the once-per-day guard.")
    return parser.parse_args()


def request_json(url: str, method: str = "GET", body: dict[str, object] | None = None) -> dict[str, object]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=True).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method)
    with urlopen(request, timeout=10) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object response.")
    return payload


def read_error_payload(error: HTTPError) -> str | None:
    try:
        payload = error.read().decode("utf-8")
    except OSError:
        return None
    return payload or None


def profile_name_from_health(health: dict[str, object]) -> str:
    raw = health.get("profile")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return "__unknown__"


def load_last_success(path: Path, profile_name: str) -> str | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    profiles = payload.get("profiles")
    if not isinstance(profiles, dict):
        return None
    raw_profile = profiles.get(profile_name)
    if not isinstance(raw_profile, dict):
        return None
    raw = raw_profile.get("lastSuccessYmd")
    if isinstance(raw, str):
        return raw
    return None


def save_last_success(path: Path, profile_name: str, ymd: str) -> None:
    payload = {"profiles": {}}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            existing = None
        if isinstance(existing, dict) and isinstance(existing.get("profiles"), dict):
            payload["profiles"] = dict(existing["profiles"])
    payload["profiles"][profile_name] = {"lastSuccessYmd": ymd}
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True),
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
