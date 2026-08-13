from __future__ import annotations

import json
from gi.repository import Gio, GLib
from .constants import HELPER_BUS, HELPER_IFACE, HELPER_PATH


class SystemHelperProxy:
    def __init__(self): self._proxy = None

    def connect(self):
        if self._proxy is None:
            self._proxy = Gio.DBusProxy.new_for_bus_sync(Gio.BusType.SYSTEM, Gio.DBusProxyFlags.NONE, None, HELPER_BUS, HELPER_PATH, HELPER_IFACE, None)
        return self._proxy

    def call(self, method: str, payload: dict | None = None):
        result = self.connect().call_sync(method, GLib.Variant("(s)", (json.dumps(payload or {}),)), Gio.DBusCallFlags.NONE, 120_000, None)
        raw = result.unpack()[0]
        response = json.loads(raw)
        if not response.get("ok"): raise RuntimeError(response.get("error", "System operation failed"))
        return response

    def status(self):
        try: return self.call("QueryStatus")
        except Exception as exc: return {"ok": False, "error": str(exc), "available": False}

    def login_appearance(self):
        try:return self.call("QueryStatus", {"appearance_only": True}).get("appearance")
        except Exception:return None
