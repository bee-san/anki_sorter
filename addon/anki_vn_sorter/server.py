from __future__ import annotations

import json
from concurrent.futures import Future
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock, Thread
from typing import Any, Callable, TypeVar
from urllib.parse import urlparse

from aqt import gui_hooks, mw
from aqt.utils import showWarning

from .config import AddonConfig, ConfigValidationError, load_config
from .sorter import build_health_snapshot, run_sort_on_collection
from .state import load_state

T = TypeVar("T")


class SorterRequestHandler(BaseHTTPRequestHandler):
    server: "SorterHTTPServer"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._serve_json(self.server.manager.get_health)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/sort":
            self._serve_json(self.server.manager.run_sort)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def log_message(self, format: str, *args: object) -> None:
        return

    def _serve_json(self, payload_factory: Callable[[], dict[str, Any]]) -> None:
        try:
            payload = payload_factory()
        except Exception as error:
            message = json.dumps(
                {"ready": False, "error": str(error)},
                ensure_ascii=True,
            ).encode("utf-8")
            self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(message)))
            self.end_headers()
            self.wfile.write(message)
            return

        encoded = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)


class SorterHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, manager: "LocalSorterServerManager", port: int) -> None:
        self.manager = manager
        super().__init__(("127.0.0.1", port), SorterRequestHandler)


class LocalSorterServerManager:
    def __init__(self) -> None:
        self._lock = Lock()
        self._config: AddonConfig | None = None
        self._server: SorterHTTPServer | None = None
        self._thread: Thread | None = None

    def register_hooks(self) -> None:
        _replace_hook_callback(gui_hooks.profile_did_open, self.start_from_current_config)
        if hasattr(gui_hooks, "profile_will_close"):
            _replace_hook_callback(gui_hooks.profile_will_close, self.stop)

    def start_from_current_config(self, *args: Any) -> None:
        if not getattr(mw, "col", None):
            return
        try:
            config = load_config()
        except ConfigValidationError as error:
            self.stop()
            showWarning(
                "Anki VN Sorter configuration is invalid.\n\n" + "\n".join(error.messages)
            )
            return
        self.apply_config(config)

    def apply_config(self, config: AddonConfig) -> bool:
        with self._lock:
            existing_port = self._server.server_address[1] if self._server else None
            thread_is_alive = self._thread is not None and self._thread.is_alive()
            if (
                self._server
                and thread_is_alive
                and existing_port == config.http_port
                and self._config == config
            ):
                return True

        self.stop()
        try:
            server = SorterHTTPServer(self, config.http_port)
        except OSError as error:
            showWarning(
                f"Anki VN Sorter could not start its local server on port {config.http_port}.\n\n{error}"
            )
            return False

        thread = Thread(
            target=server.serve_forever,
            name="AnkiVnSorterServer",
            daemon=True,
        )
        thread.start()

        with self._lock:
            self._server = server
            self._thread = thread
            self._config = config
        return True

    def stop(self, *args: Any) -> None:
        with self._lock:
            server = self._server
            thread = self._thread
            self._server = None
            self._thread = None
            self._config = None

        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)

    def get_health(self) -> dict[str, Any]:
        config = self._require_config()
        profile_name = _profile_name()
        snapshot = self._run_collection_task_sync(
            lambda col: build_health_snapshot(col, config)
        )
        state = load_state()
        profile_state = state.for_profile(profile_name)
        return {
            "ready": True,
            "profile": profile_name,
            "config": config.to_dict(),
            "state": state.to_dict(),
            "lastSuccessYmd": profile_state.last_success_ymd,
            **snapshot,
        }

    def run_sort(self) -> dict[str, Any]:
        config = self._require_config()
        profile_name = _profile_name()
        summary = self._run_collection_task_sync(
            lambda col: run_sort_on_collection(
                col,
                config,
                profile_name,
                force=False,
            )
        )
        return {
            "ready": True,
            "profile": profile_name,
            "summary": summary,
        }

    def _require_config(self) -> AddonConfig:
        with self._lock:
            config = self._config
        if config is None:
            raise RuntimeError("The Anki VN Sorter server is not configured.")
        return config

    def _run_collection_task_sync(self, task: Callable[[Any], T]) -> T:
        result: Future[T] = Future()

        def schedule() -> None:
            col = mw.col
            if col is None:
                result.set_exception(RuntimeError("No collection is currently open."))
                return

            def background_task() -> T:
                return task(col)

            def on_done(background_future: Future[T]) -> None:
                try:
                    result.set_result(background_future.result())
                except Exception as error:
                    result.set_exception(error)

            mw.taskman.run_in_background(
                background_task,
                on_done=on_done,
                uses_collection=True,
            )

        mw.taskman.run_on_main(schedule)
        return result.result()


def _profile_name() -> str | None:
    profile_manager = getattr(mw, "pm", None)
    if profile_manager is None:
        return None
    name = getattr(profile_manager, "name", None)
    if callable(name):
        return name()
    if isinstance(name, str):
        return name
    return None


def _replace_hook_callback(hook: Any, callback: Any) -> None:
    callback_key = _callback_key(callback)
    for existing in _hook_callbacks(hook):
        if _callback_key(existing) == callback_key:
            _remove_hook_callback(hook, existing)
    _append_hook_callback(hook, callback)


def _callback_key(callback: Any) -> tuple[Any, Any]:
    return (getattr(callback, "__self__", None), getattr(callback, "__func__", callback))


def _hook_callbacks(hook: Any) -> list[Any]:
    if isinstance(hook, list):
        return list(hook)
    callbacks = getattr(hook, "_hooks", None)
    if isinstance(callbacks, list):
        return list(callbacks)
    return []


def _remove_hook_callback(hook: Any, callback: Any) -> None:
    if hasattr(hook, "remove"):
        try:
            hook.remove(callback)
        except ValueError:
            pass
        return
    if isinstance(hook, list):
        while callback in hook:
            hook.remove(callback)


def _append_hook_callback(hook: Any, callback: Any) -> None:
    if hasattr(hook, "append"):
        hook.append(callback)


server_manager = LocalSorterServerManager()
