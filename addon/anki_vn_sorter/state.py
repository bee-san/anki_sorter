from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

UNKNOWN_PROFILE_KEY = "__unknown__"


@dataclass(frozen=True)
class ProfileState:
    last_success_ymd: str | None = None
    last_summary: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "lastSuccessYmd": self.last_success_ymd,
            "lastSummary": self.last_summary,
        }


@dataclass(frozen=True)
class SorterState:
    profiles: dict[str, ProfileState] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profiles": {
                profile_name: profile_state.to_dict()
                for profile_name, profile_state in sorted(self.profiles.items())
            }
        }

    def for_profile(self, profile_name: str | None) -> ProfileState:
        return self.profiles.get(profile_key(profile_name), ProfileState())

    def with_profile(self, profile_name: str | None, profile_state: ProfileState) -> "SorterState":
        profiles = dict(self.profiles)
        profiles[profile_key(profile_name)] = profile_state
        return SorterState(profiles=profiles)


def addon_dir() -> Path:
    return Path(__file__).resolve().parent


def ensure_user_files_dir() -> Path:
    path = addon_dir() / "user_files"
    path.mkdir(parents=True, exist_ok=True)
    return path


def state_path() -> Path:
    return ensure_user_files_dir() / "sorter_state.json"


def load_state() -> SorterState:
    path = state_path()
    if not path.exists():
        return SorterState()
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return SorterState()

    if not isinstance(payload, dict):
        return SorterState()

    profiles_payload = payload.get("profiles")
    if isinstance(profiles_payload, dict):
        profiles: dict[str, ProfileState] = {}
        for profile_name, raw_state in profiles_payload.items():
            if not isinstance(profile_name, str) or not isinstance(raw_state, dict):
                continue
            last_success = raw_state.get("lastSuccessYmd")
            summary = raw_state.get("lastSummary")
            profiles[profile_name] = ProfileState(
                last_success_ymd=last_success if isinstance(last_success, str) else None,
                last_summary=summary if isinstance(summary, dict) else None,
            )
        return SorterState(profiles=profiles)

    last_success = payload.get("lastSuccessYmd")
    summary = payload.get("lastSummary")
    legacy_state = ProfileState(
        last_success_ymd=last_success if isinstance(last_success, str) else None,
        last_summary=summary if isinstance(summary, dict) else None,
    )
    if legacy_state.last_success_ymd is None and legacy_state.last_summary is None:
        return SorterState()
    return SorterState(profiles={UNKNOWN_PROFILE_KEY: legacy_state})


def save_state(state: SorterState) -> None:
    path = state_path()
    with path.open("w", encoding="utf-8") as handle:
        json.dump(state.to_dict(), handle, ensure_ascii=True, indent=2, sort_keys=True)


def profile_key(profile_name: str | None) -> str:
    if isinstance(profile_name, str):
        cleaned = profile_name.strip()
        if cleaned:
            return cleaned
    return UNKNOWN_PROFILE_KEY
