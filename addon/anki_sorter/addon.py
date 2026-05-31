from .automation import auto_sort_manager
from .server import server_manager
from .ui import register_tools_menu


def register_addon() -> None:
    register_tools_menu()
    auto_sort_manager.register_hooks()
    server_manager.register_hooks()
