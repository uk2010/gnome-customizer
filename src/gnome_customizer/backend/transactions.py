from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Callable

from .settings import SettingsBackend
from .state import StateStore

COMPANION_UUID = "gnome-customizer@io.github.gnomecustomizer"


@dataclass(frozen=True)
class Change:
    domain: str
    schema: str
    key: str
    value: Any
    label: str


class TransactionError(RuntimeError):
    def __init__(self, message: str, applied: int = 0):
        super().__init__(message)
        self.applied = applied


class ChangeManager:
    def __init__(self, settings: SettingsBackend, state: StateStore):
        self.settings, self.state = settings, state
        self.pending: dict[tuple[str, str], Change] = {}
        self.listeners: list[Callable[[], None]] = []

    def stage(self, change: Change) -> None:
        if not self.settings.supports(change.schema, change.key):
            raise TransactionError(f"{change.label} is not supported on this system")
        if change.schema == "io.github.gnomecustomizer.shell":
            enabled = list(self.settings.get("org.gnome.shell", "enabled-extensions"))
            if COMPANION_UUID not in enabled:
                enabled.append(COMPANION_UUID)
            self.pending[("org.gnome.shell", "enabled-extensions")] = Change(
                "shell", "org.gnome.shell", "enabled-extensions", enabled, "Shell Companion"
            )
            if self.settings.supports("org.gnome.shell", "disable-user-extensions"):
                self.pending[("org.gnome.shell", "disable-user-extensions")] = Change(
                    "shell", "org.gnome.shell", "disable-user-extensions", False, "Shell Extensions"
                )
            if self.settings.supports("org.gnome.shell", "disabled-extensions"):
                disabled = [item for item in self.settings.get("org.gnome.shell", "disabled-extensions") if item != COMPANION_UUID]
                self.pending[("org.gnome.shell", "disabled-extensions")] = Change(
                    "shell", "org.gnome.shell", "disabled-extensions", disabled, "Shell Companion"
                )
        self.pending[(change.schema, change.key)] = change
        self._notify()

    def discard(self) -> None:
        self.pending.clear(); self._notify()

    def apply(self) -> int:
        state_before = deepcopy(self.state.data)
        applied: list[tuple[Change, Any]] = []
        try:
            for change in self.pending.values():
                old = self.settings.get(change.schema, change.key)
                self.state.remember_original(change.domain, f"{change.schema}:{change.key}", old)
                value=change.value
                if change.schema=="org.gnome.shell" and change.key in {"enabled-extensions","disabled-extensions"}:
                    current=list(old);wanted=COMPANION_UUID in value
                    if wanted and COMPANION_UUID not in current:current.append(COMPANION_UUID)
                    if not wanted and COMPANION_UUID in current:current.remove(COMPANION_UUID)
                    value=current
                self.settings.set(change.schema, change.key, value)
                applied.append((change, old))
        except Exception as exc:
            for change, old in reversed(applied):
                try: self.settings.set(change.schema, change.key, old)
                except Exception: pass
            self.state.data = state_before
            raise TransactionError(str(exc), len(applied)) from exc
        count = len(applied)
        for change, _ in applied:
            managed = self.state.data.setdefault("managed", {}).setdefault(change.domain, [])
            token = f"{change.schema}:{change.key}"
            if token not in managed: managed.append(token)
        self.state.data["last_apply"] = datetime.now(timezone.utc).isoformat()
        self.state.save(); self.pending.clear(); self._notify()
        return count

    def restore(self, domain: str = "desktop") -> int:
        originals = self.state.original(domain); restored = 0;applied=[]
        try:
            for token, value in originals.items():
                schema, key = token.split(":", 1)
                if self.settings.supports(schema, key):
                    current=self.settings.get(schema,key);target=value
                    if schema=="org.gnome.shell" and key in {"enabled-extensions","disabled-extensions"}:
                        target=list(current);originally_present=COMPANION_UUID in value
                        if originally_present and COMPANION_UUID not in target:target.append(COMPANION_UUID)
                        if not originally_present and COMPANION_UUID in target:target.remove(COMPANION_UUID)
                    self.settings.set(schema, key, target);applied.append((schema,key,current));restored += 1
        except Exception as exc:
            for schema,key,current in reversed(applied):
                try:self.settings.set(schema,key,current)
                except Exception:pass
            raise TransactionError(f"Restore failed: {exc}",len(applied)) from exc
        self.state.clear_original(domain)
        return restored

    def reset_managed(self, domains=("desktop", "shell")) -> int:
        tokens=[]
        for domain in domains:
            for token in [*self.state.data.get("managed",{}).get(domain,[]), *self.state.original(domain)]:
                if token not in tokens:tokens.append(token)
        applied=[]
        try:
            for token in tokens:
                schema,key=token.split(":",1)
                if not self.settings.supports(schema,key):continue
                current=self.settings.get(schema,key);applied.append((schema,key,current))
                if schema=="org.gnome.shell" and key in {"enabled-extensions","disabled-extensions"}:
                    self.settings.set(schema,key,[item for item in current if item!=COMPANION_UUID])
                else:self.settings.reset(schema,key)
        except Exception as exc:
            for schema,key,current in reversed(applied):
                try:self.settings.set(schema,key,current)
                except Exception:pass
            raise TransactionError(f"Reset failed: {exc}",len(applied)) from exc
        for domain in domains:
            self.state.data.get("original",{}).pop(domain,None)
            self.state.data.get("managed",{}).pop(domain,None)
        self.state.save();return len(applied)

    def _notify(self):
        for listener in tuple(self.listeners): listener()
