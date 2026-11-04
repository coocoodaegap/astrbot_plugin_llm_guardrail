"""Provide the minimal ``astrbot.api`` surface plugin modules import in tests.

Plugin code imports ``logger`` from ``astrbot.api`` exactly as it does inside
AstrBot and no longer falls back to the standard library logger.  The test suite
runs outside the AstrBot runtime, so install the smallest possible module
surface before any plugin module is imported.
"""

import logging
import sys
import types


def install() -> None:
    astrbot = sys.modules.get("astrbot")
    if astrbot is None:
        astrbot = types.ModuleType("astrbot")
        astrbot.__path__ = []  # type: ignore[attr-defined]
        sys.modules["astrbot"] = astrbot

    api = sys.modules.get("astrbot.api")
    if api is None:
        api = types.ModuleType("astrbot.api")
        sys.modules["astrbot.api"] = api
        setattr(astrbot, "api", api)

    if not hasattr(api, "logger"):
        setattr(api, "logger", logging.getLogger("astrbot"))
