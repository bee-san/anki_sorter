from __future__ import annotations

from concurrent.futures import Future
from typing import Any

from aqt import gui_hooks, mw
from aqt.qt import QTimer
from aqt.utils import showWarning

from .config import (
    AUTO_SORT_MODE_AFTER_SYNC,
    AUTO_SORT_MODE_PROFILE_OPEN,
    ConfigValidationError,
    load_config,
)
from .server import _profile_name, _append_hook_callback, _callback_key, _hook_callbacks, _remove_hook_callback
from .sorter import run_sort_on_collection


class AutoSortManager:
    def __init__(self) -> None:
        self._profile_closing = False
        self._sort_running = False

    def register_hooks(self) -> None:
        _replace_hook_callback(gui_hooks.profile_did_open, self._on_profile_did_open)
        if hasattr(gui_hooks, "profile_will_close"):
            _replace_hook_callback(gui_hooks.profile_will_close, self._on_profile_will_close)
        if hasattr(gui_hooks, "sync_did_finish"):
            _replace_hook_callback(gui_hooks.sync_did_finish, self._on_sync_did_finish)

    def _on_profile_did_open(self, *args: Any) -> None:
        self._profile_closing = False
        self._maybe_schedule_auto_sort(AUTO_SORT_MODE_PROFILE_OPEN)

    def _on_profile_will_close(self, *args: Any) -> None:
        self._profile_closing = True

    def _on_sync_did_finish(self, *args: Any) -> None:
        self._maybe_schedule_auto_sort(AUTO_SORT_MODE_AFTER_SYNC)

    def _maybe_schedule_auto_sort(self, required_mode: str) -> None:
        if self._profile_closing or not getattr(mw, "col", None):
            return
        try:
            config = load_config()
        except ConfigValidationError as error:
            showWarning(
                "Anki VN Sorter configuration is invalid.\n\n" + "\n".join(error.messages),
                parent=mw,
            )
            return
        if config.auto_sort_mode != required_mode:
            return
        QTimer.singleShot(0, lambda: self._run_auto_sort(config))

    def _run_auto_sort(self, config: Any) -> None:
        if self._profile_closing or self._sort_running:
            return
        col = getattr(mw, "col", None)
        if col is None:
            return

        self._sort_running = True
        profile_name = _profile_name()

        def background_task() -> dict[str, Any]:
            return run_sort_on_collection(
                col,
                config,
                profile_name,
                force=False,
            )

        def on_done(background_future: Future[dict[str, Any]]) -> None:
            self._sort_running = False
            try:
                background_future.result()
            except Exception as error:
                if not self._profile_closing:
                    showWarning(f"Anki VN Sorter automatic run failed.\n\n{error}", parent=mw)

        mw.taskman.run_in_background(
            background_task,
            on_done=on_done,
            uses_collection=True,
        )


def _replace_hook_callback(hook: Any, callback: Any) -> None:
    callback_key = _callback_key(callback)
    for existing in _hook_callbacks(hook):
        if _callback_key(existing) == callback_key:
            _remove_hook_callback(hook, existing)
    _append_hook_callback(hook, callback)


auto_sort_manager = AutoSortManager()
