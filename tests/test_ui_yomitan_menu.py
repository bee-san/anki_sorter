from __future__ import annotations

import importlib
import sys
import types
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))


class DummySignal:
    def __init__(self) -> None:
        self.callback = None

    def connect(self, callback: Any) -> None:
        self.callback = callback


class DummyAction:
    def __init__(self, text: str, parent: Any = None) -> None:
        self.text = text
        self.parent = parent
        self.triggered = DummySignal()


class DummyMenu:
    def __init__(self, title: str = "", parent: Any = None) -> None:
        self.title = title
        self.parent = parent
        self.actions: list[DummyAction] = []
        self.menus: list[DummyMenu] = []

    def addAction(self, action: DummyAction) -> None:
        self.actions.append(action)

    def addMenu(self, menu: "DummyMenu") -> None:
        self.menus.append(menu)

    def removeAction(self, action: Any) -> None:
        return None

    def menuAction(self) -> DummyAction:
        return DummyAction(self.title, self)


class DummyAddonManager:
    def __init__(self) -> None:
        self.raw_config: dict[str, Any] = {}
        self.writes: list[tuple[str, dict[str, Any]]] = []

    def getConfig(self, module_name: str) -> dict[str, Any]:
        return dict(self.raw_config)

    def writeConfig(self, module_name: str, raw_config: dict[str, Any]) -> None:
        self.raw_config = dict(raw_config)
        self.writes.append((module_name, dict(raw_config)))


class DummyMainWindow:
    def __init__(self) -> None:
        self.form = types.SimpleNamespace(menuTools=DummyMenu("Tools"))
        self.addonManager = DummyAddonManager()


class DummyQueryOp:
    instances: list["DummyQueryOp"] = []

    def __init__(self, parent: Any, op: Any, success: Any) -> None:
        self.parent = parent
        self.op = op
        self.success = success
        self.progress_message = ""
        self.failure_callback = None
        DummyQueryOp.instances.append(self)

    def with_progress(self, message: str) -> "DummyQueryOp":
        self.progress_message = message
        return self

    def failure(self, callback: Any) -> "DummyQueryOp":
        self.failure_callback = callback
        return self

    def run_in_background(self) -> None:
        result = self.op(None)
        self.success(result)


class DummyInputDialog:
    next_text: tuple[str, bool] = ("", False)
    next_item: tuple[str, bool] = ("", False)

    @staticmethod
    def getText(*args: Any, **kwargs: Any) -> tuple[str, bool]:
        return DummyInputDialog.next_text

    @staticmethod
    def getItem(*args: Any) -> tuple[str, bool]:
        return DummyInputDialog.next_item


class DummyMessageBox:
    Yes = 1
    No = 2
    next_answer = No
    questions: list[tuple[Any, str, str, int, int]] = []

    @staticmethod
    def question(parent: Any, title: str, text: str, buttons: int, default_button: int) -> int:
        DummyMessageBox.questions.append((parent, title, text, buttons, default_button))
        return DummyMessageBox.next_answer


class UiYomitanMenuTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mw = DummyMainWindow()
        DummyQueryOp.instances = []
        DummyInputDialog.next_text = ("", False)
        DummyInputDialog.next_item = ("", False)
        DummyMessageBox.next_answer = DummyMessageBox.No
        DummyMessageBox.questions = []
        package = types.ModuleType("anki_sorter")
        package.__path__ = [str(ROOT / "addon" / "anki_sorter")]  # type: ignore[attr-defined]
        sys.modules["anki_sorter"] = package

        aqt = types.ModuleType("aqt")
        setattr(aqt, "mw", self.mw)
        setattr(aqt, "gui_hooks", types.SimpleNamespace(profile_did_open=[]))
        sys.modules["aqt"] = aqt

        operations = types.ModuleType("aqt.operations")
        setattr(operations, "QueryOp", DummyQueryOp)
        sys.modules["aqt.operations"] = operations

        qt = types.ModuleType("aqt.qt")
        setattr(qt, "QAction", DummyAction)
        setattr(qt, "QInputDialog", DummyInputDialog)
        setattr(qt, "QMenu", DummyMenu)
        setattr(qt, "QMessageBox", DummyMessageBox)
        sys.modules["aqt.qt"] = qt

        utils = types.ModuleType("aqt.utils")
        setattr(utils, "showWarning", lambda *args, **kwargs: None)
        setattr(utils, "tooltip", lambda *args, **kwargs: None)
        sys.modules["aqt.utils"] = utils
        sys.modules.pop("anki_sorter.ui", None)
        self.ui = importlib.import_module("anki_sorter.ui")
        setattr(
            self.ui,
            "refresh_frequency_lookup",
            lambda config: self.ui.FrequencyLookup(
                ranks={"語": 1.0},
                source_url="https://example.test/source",
                warnings=tuple(),
                source_kind="yomitan"
                if config.yomitan_frequency_index_url.strip()
                else "remote",
            ),
        )

    def test_tools_menu_exposes_yomitan_source_actions(self) -> None:
        self.ui.register_tools_menu()

        menu = self.mw.form.menuTools.menus[-1]
        labels = [action.text for action in menu.actions]

        self.assertIn("Sort Cards Now", labels)
        self.assertNotIn("Sort Kiku Cards Now", labels)
        self.assertIn("Set Yomitan Frequency Dictionary URL...", labels)
        self.assertIn("Clear Yomitan Frequency Dictionary URL", labels)
        self.assertIn("Refresh Current Frequency Source Now", labels)
        self.assertNotIn("Refresh Current Jiten Frequency List Now", labels)

    def test_set_yomitan_frequency_url_saves_url_and_refreshes_source(self) -> None:
        self.mw.addonManager.raw_config = {
            "jitenFrequencyListId": "global",
            "yomitanFrequencyIndexUrl": "",
        }
        DummyInputDialog.next_text = (" https://example.test/index.json ", True)

        self.ui.set_yomitan_frequency_url()

        self.assertEqual(
            self.mw.addonManager.raw_config["yomitanFrequencyIndexUrl"],
            "https://example.test/index.json",
        )
        self.assertEqual(len(DummyQueryOp.instances), 1)
        self.assertIn("Yomitan frequency dictionary", DummyQueryOp.instances[0].progress_message)

    def test_clear_yomitan_frequency_url_restores_jiten_refresh_path(self) -> None:
        self.mw.addonManager.raw_config = {
            "jitenFrequencyListId": "global",
            "yomitanFrequencyIndexUrl": "https://example.test/index.json",
        }

        self.ui.clear_yomitan_frequency_url()

        self.assertEqual(self.mw.addonManager.raw_config["yomitanFrequencyIndexUrl"], "")
        self.assertEqual(len(DummyQueryOp.instances), 1)
        self.assertIn("Jiten", DummyQueryOp.instances[0].progress_message)

    def test_choosing_jiten_frequency_list_clears_yomitan_url(self) -> None:
        self.mw.addonManager.raw_config = {
            "jitenFrequencyListId": "global",
            "yomitanFrequencyIndexUrl": "https://example.test/index.json",
        }
        options = list(self.ui.dropdown_options())
        selected_id, selected_label = options[-1]
        DummyInputDialog.next_item = (selected_label, True)

        self.ui.choose_jiten_frequency_list()

        self.assertEqual(self.mw.addonManager.raw_config["jitenFrequencyListId"], selected_id)
        self.assertEqual(self.mw.addonManager.raw_config["yomitanFrequencyIndexUrl"], "")

    def test_manual_sort_cancelled_when_sync_confirmation_declined(self) -> None:
        self.mw.addonManager.raw_config = {}
        DummyMessageBox.next_answer = DummyMessageBox.No

        self.ui.run_sort_now()

        self.assertEqual(len(DummyQueryOp.instances), 0)
        self.assertEqual(len(DummyMessageBox.questions), 1)
        confirmation_copy = DummyMessageBox.questions[0][2]
        self.assertIn("AnkiDroid", confirmation_copy)
        self.assertIn("offline reviews", confirmation_copy)
        self.assertIn("sync conflicts", confirmation_copy)
        self.assertIn("sync this desktop after all devices", confirmation_copy)

    def test_manual_sort_runs_after_sync_confirmation_acceptance(self) -> None:
        captured: dict[str, Any] = {}
        self.mw.addonManager.raw_config = {}
        DummyMessageBox.next_answer = DummyMessageBox.Yes

        def fake_run_sort_on_collection(*args: Any, **kwargs: Any) -> dict[str, object]:
            captured.update(kwargs)
            return {"applied": False, "candidateCount": 0, "repositionedCount": 0}

        self.ui.run_sort_on_collection = fake_run_sort_on_collection

        self.ui.run_sort_now()

        self.assertEqual(len(DummyQueryOp.instances), 1)
        self.assertTrue(captured["acknowledged"])
        self.assertTrue(captured["force"])
        self.assertEqual(captured["trigger"], self.ui.SORT_TRIGGER_MANUAL)


if __name__ == "__main__":
    unittest.main()
