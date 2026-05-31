from __future__ import annotations

from dataclasses import dataclass

from .config import (
    AUTO_SORT_MODE_AFTER_SYNC,
    AUTO_SORT_MODE_PROFILE_OPEN,
    AddonConfig,
    SYNC_SAFETY_MODE_DESKTOP_ONLY_ALLOW_AUTO,
    SYNC_SAFETY_MODE_MOBILE_GUARDED,
)

SORT_TRIGGER_AFTER_SYNC = "after_sync"
SORT_TRIGGER_PROFILE_OPEN = "profile_open"
SORT_TRIGGER_MANUAL = "manual"
SORT_TRIGGER_API = "api"
AUTOMATION_TRIGGERS = {
    SORT_TRIGGER_AFTER_SYNC: AUTO_SORT_MODE_AFTER_SYNC,
    SORT_TRIGGER_PROFILE_OPEN: AUTO_SORT_MODE_PROFILE_OPEN,
}
ACKNOWLEDGED_TRIGGERS = {SORT_TRIGGER_MANUAL, SORT_TRIGGER_API}


@dataclass(frozen=True)
class SortSafetyDecision:
    allowed: bool
    reason: str


def decide_sort_safety(
    config: AddonConfig,
    trigger: str,
    *,
    acknowledged: bool = False,
) -> SortSafetyDecision:
    if trigger in ACKNOWLEDGED_TRIGGERS:
        if acknowledged:
            return SortSafetyDecision(True, "acknowledged manual/API sort request")
        return SortSafetyDecision(False, "manual/API sort request requires acknowledgement")

    required_auto_sort_mode = AUTOMATION_TRIGGERS.get(trigger)
    if required_auto_sort_mode is None:
        return SortSafetyDecision(False, f"unknown sort trigger: {trigger}")

    if config.auto_sort_mode != required_auto_sort_mode:
        return SortSafetyDecision(
            False,
            f"autoSortMode is {config.auto_sort_mode}; {required_auto_sort_mode} is not enabled",
        )

    if config.sync_safety_mode == SYNC_SAFETY_MODE_DESKTOP_ONLY_ALLOW_AUTO:
        return SortSafetyDecision(True, "desktop_only_allow_auto permits automatic sorting")

    if config.sync_safety_mode == SYNC_SAFETY_MODE_MOBILE_GUARDED:
        return SortSafetyDecision(
            False,
            "mobile_guarded blocks automatic sorting after sync/profile open",
        )

    return SortSafetyDecision(False, f"unsupported syncSafetyMode: {config.sync_safety_mode}")
