from __future__ import annotations

from typing import Any

from aqt import mw
from aqt.operations import QueryOp
from aqt.qt import QAction, QMenu
from aqt.utils import showWarning, tooltip

from .config import ConfigValidationError, load_config
from .server import _profile_name
from .sorter import run_sort_on_collection

TOOLS_MENU_TITLE = "Anki VN Sorter"
RUN_ACTION_LABEL = "Sort Kiku VN Cards Now"
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
