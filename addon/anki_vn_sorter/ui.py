from __future__ import annotations

from typing import Any

from aqt import mw
from aqt.operations import QueryOp
from aqt.qt import QAction, QInputDialog, QMenu
from aqt.utils import showWarning, tooltip

from .config import ConfigValidationError, addon_module_name, load_config, load_raw_config
from .jiten import FrequencyLookup, refresh_frequency_lookup
from .jiten_lists import dropdown_options, get_frequency_list_definition
from .server import _profile_name
from .sorter import run_sort_on_collection

TOOLS_MENU_TITLE = "Anki VN Sorter"
RUN_ACTION_LABEL = "Sort Kiku VN Cards Now"
CHOOSE_FREQUENCY_LIST_ACTION_LABEL = "Choose Jiten Frequency List..."
REFRESH_JITEN_ACTION_LABEL = "Refresh Current Jiten Frequency List Now"
TOOLS_MENU_ATTR = "_anki_vn_sorter_menu"


def register_tools_menu() -> None:
    if not getattr(mw, "form", None):
        return

    tools_menu = mw.form.menuTools
    existing = getattr(mw, TOOLS_MENU_ATTR, None)
    if existing is not None:
        try:
            tools_menu.removeAction(existing.menuAction())
        except RuntimeError:
            pass

    menu = QMenu(TOOLS_MENU_TITLE, mw)
    run_action = QAction(RUN_ACTION_LABEL, menu)
    run_action.triggered.connect(run_sort_now)
    menu.addAction(run_action)
    choose_frequency_list_action = QAction(CHOOSE_FREQUENCY_LIST_ACTION_LABEL, menu)
    choose_frequency_list_action.triggered.connect(choose_jiten_frequency_list)
    menu.addAction(choose_frequency_list_action)
    refresh_action = QAction(REFRESH_JITEN_ACTION_LABEL, menu)
    refresh_action.triggered.connect(refresh_jiten_now)
    menu.addAction(refresh_action)
    tools_menu.addMenu(menu)
    setattr(mw, TOOLS_MENU_ATTR, menu)


def run_sort_now() -> None:
    try:
        config = load_config()
    except ConfigValidationError as error:
        showWarning(
            "Anki VN Sorter configuration is invalid.\n\n" + "\n".join(error.messages),
            parent=mw,
        )
        return

    QueryOp(
        parent=mw,
        op=lambda col: run_sort_on_collection(
            col,
            config,
            _profile_name(),
            force=True,
        ),
        success=_on_sort_success,
    ).with_progress("Prioritizing new Kiku cards...").failure(
        _on_sort_failure
    ).run_in_background()


def refresh_jiten_now() -> None:
    try:
        config = load_config()
    except ConfigValidationError as error:
        showWarning(
            "Anki VN Sorter configuration is invalid.\n\n" + "\n".join(error.messages),
            parent=mw,
        )
        return

    QueryOp(
        parent=mw,
        op=lambda col: refresh_frequency_lookup(config),
        success=_on_refresh_success,
    ).with_progress(
        f"Refreshing the Jiten {get_frequency_list_definition(config.jiten_frequency_list_id).label} frequency list..."
    ).failure(
        _on_refresh_failure
    ).run_in_background()


def choose_jiten_frequency_list() -> None:
    try:
        config = load_config()
    except ConfigValidationError as error:
        showWarning(
            "Anki VN Sorter configuration is invalid.\n\n" + "\n".join(error.messages),
            parent=mw,
        )
        return

    options = list(dropdown_options())
    labels = [label for _, label in options]
    ids_by_label = {label: list_id for list_id, label in options}
    current_label = get_frequency_list_definition(
        config.jiten_frequency_list_id
    ).dropdown_label
    current_index = labels.index(current_label) if current_label in labels else 0
    selected_label, accepted = QInputDialog.getItem(
        mw,
        "Jiten Frequency List",
        "Choose which Jiten frequency list should drive new-card prioritization.\n\nGlobal and Kanji are listed first. Media-specific lists are marked as such.",
        labels,
        current_index,
        False,
    )
    if not accepted or not selected_label:
        return

    selected_list_id = ids_by_label.get(selected_label)
    if not selected_list_id:
        return

    raw_config = load_raw_config()
    raw_config["jitenFrequencyListId"] = selected_list_id
    raw_config["jitenVnCsvUrl"] = ""
    mw.addonManager.writeConfig(addon_module_name(), raw_config)

    try:
        updated_config = load_config()
    except ConfigValidationError as error:
        showWarning(
            "Anki VN Sorter configuration is invalid after saving.\n\n"
            + "\n".join(error.messages),
            parent=mw,
        )
        return

    QueryOp(
        parent=mw,
        op=lambda col: refresh_frequency_lookup(updated_config),
        success=lambda lookup: _on_frequency_list_selected(updated_config, lookup),
    ).with_progress(
        f"Switching to Jiten {get_frequency_list_definition(selected_list_id).label}..."
    ).failure(_on_refresh_failure).run_in_background()


def _on_sort_success(summary: dict[str, Any]) -> None:
    if summary.get("skippedForToday"):
        tooltip("Anki VN Sorter already ran for this profile today.", parent=mw)
        return
    if summary.get("applied"):
        tooltip(
            f"Anki VN Sorter repositioned {summary.get('repositionedCount', 0)} new cards.",
            parent=mw,
        )
        return

    tooltip("Anki VN Sorter found nothing to change.", parent=mw)


def _on_sort_failure(error: Exception) -> None:
    showWarning(f"Anki VN Sorter failed.\n\n{error}", parent=mw)


def _on_refresh_success(lookup: FrequencyLookup) -> None:
    if lookup.source_kind == "remote":
        tooltip(
            f"Refreshed Jiten frequency list ({len(lookup.ranks):,} entries).",
            parent=mw,
        )
        return

    message = "Could not refresh the Jiten frequency list from the live source."
    if lookup.source_kind == "cache":
        message += "\n\nUsing the local cache instead."
    elif lookup.source_kind == "bundled":
        message += "\n\nUsing the bundled snapshot instead."
    else:
        message += "\n\nFalling back to Kiku FreqSort only."

    details = "\n".join(lookup.warnings)
    if details:
        message += "\n\n" + details
    showWarning(message, parent=mw)


def _on_refresh_failure(error: Exception) -> None:
    showWarning(f"Jiten refresh failed.\n\n{error}", parent=mw)


def _on_frequency_list_selected(config: Any, lookup: FrequencyLookup) -> None:
    selected_label = get_frequency_list_definition(config.jiten_frequency_list_id).label
    if lookup.source_kind == "remote":
        tooltip(
            f"Using Jiten {selected_label} ({len(lookup.ranks):,} entries).",
            parent=mw,
        )
        return

    message = f"Switched to Jiten {selected_label}."
    if lookup.source_kind == "cache":
        message += "\n\nThe live download failed, so the cached copy will be used."
    elif lookup.source_kind == "bundled":
        message += "\n\nThe live download failed, so the bundled snapshot will be used."
    elif lookup.source_kind == "none":
        message += "\n\nNo usable Jiten data was available; the sorter will fall back to Kiku FreqSort."

    details = "\n".join(lookup.warnings)
    if details:
        message += "\n\n" + details
    showWarning(message, parent=mw)
