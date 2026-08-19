from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Callable

from .settings import SettingsBackend, yaru_theme_for_accent
from .state import StateStore

COMPANION_UUID = "gnome-customizer@io.github.gnomecustomizer"
COMPANION_SCHEMA = "io.github.gnomecustomizer.shell"
BMS_UUID = "blur-my-shell@aunetx"
BMS_SCHEMA_PREFIX = "org.gnome.shell.extensions.blur-my-shell"
DOCK_SCHEMA = "org.gnome.shell.extensions.dash-to-dock"


@dataclass(frozen=True)
class Change:
    domain: str
    schema: str
    key: str
    value: Any
    label: str
    best_effort: bool = False


class TransactionError(RuntimeError):
    def __init__(self, message: str, applied: int = 0):
        super().__init__(message)
        self.applied = applied


class ChangeManager:
    def __init__(self, settings: SettingsBackend, state: StateStore):
        self.settings, self.state = settings, state
        # The Dock page fills this with the installed extension that owns the
        # shared Dash-to-Dock schema.  Ubuntu Dock and upstream Dash to Dock
        # use the same schema, but have different extension UUIDs.
        self.dock_extension_uuid: str | None = None
        self.pending: dict[tuple[str, str], Change] = {}
        self.skipped: list[tuple[Change, str]] = []
        self.factory_targets: dict[str, list[str]] = {"shell":[
            "org.gnome.shell:enabled-extensions","org.gnome.shell:disabled-extensions","org.gnome.shell:disable-user-extensions",
        ]}
        self.listeners: list[Callable[[], None]] = []

    def register_factory(self, domain: str, schema: str, key: str) -> None:
        token=f"{schema}:{key}";targets=self.factory_targets.setdefault(domain,[])
        if token not in targets:targets.append(token)

    def stage(self, change: Change) -> None:
        if not self.settings.supports(change.schema, change.key):
            raise TransactionError(f"{change.label} is not supported on this system")
        if change.schema == COMPANION_SCHEMA:
            self._ensure_extension(COMPANION_UUID, "Shell Companion")
        elif change.schema == BMS_SCHEMA_PREFIX or change.schema.startswith(BMS_SCHEMA_PREFIX + "."):
            self._ensure_extension(BMS_UUID, "Blur My Shell")
        elif change.schema == DOCK_SCHEMA and self.dock_extension_uuid:
            self._ensure_extension(self.dock_extension_uuid, "Dock Extension")
        self.pending[(change.schema, change.key)] = change
        if change.schema == "org.gnome.desktop.interface" and change.key in {"accent-color", "color-scheme"}:
            accent = change.value if change.key == "accent-color" else self._effective_interface_value("accent-color")
            scheme = change.value if change.key == "color-scheme" else self._effective_interface_value("color-scheme")
            theme = yaru_theme_for_accent(accent, scheme == "prefer-dark")
            # Ubuntu's Yaru variants are optional. Fedora's stock GNOME uses
            # Adwaita and already applies the native accent-color setting.
            gtk_theme = self._effective_interface_value("gtk-theme")
            if isinstance(gtk_theme, str) and gtk_theme.startswith("Yaru"):
                self._stage_interface_companion("gtk-theme", theme, "GNOME GTK Theme")
            icon_theme = self._effective_interface_value("icon-theme")
            if isinstance(icon_theme, str) and icon_theme.startswith("Yaru"):
                self._stage_interface_companion("icon-theme", theme, "GNOME Folder Icons")
        self._notify()

    def _ensure_extension(self, uuid: str, label: str) -> None:
        """Stage enabling an extension without disturbing other extensions."""
        enabled = list(self.settings.get("org.gnome.shell", "enabled-extensions"))
        if uuid not in enabled:
            enabled.append(uuid)
        self.pending[("org.gnome.shell", "enabled-extensions")] = Change(
            "shell", "org.gnome.shell", "enabled-extensions", enabled, label
        )
        if self.settings.supports("org.gnome.shell", "disable-user-extensions"):
            self.pending[("org.gnome.shell", "disable-user-extensions")] = Change(
                "shell", "org.gnome.shell", "disable-user-extensions", False, "Shell Extensions"
            )
        if self.settings.supports("org.gnome.shell", "disabled-extensions"):
            disabled = [
                item for item in self.settings.get("org.gnome.shell", "disabled-extensions")
                if item != uuid
            ]
            self.pending[("org.gnome.shell", "disabled-extensions")] = Change(
                "shell", "org.gnome.shell", "disabled-extensions", disabled, label
            )

    def _managed_extension_uuids(self) -> tuple[str, ...]:
        uuids=[COMPANION_UUID, BMS_UUID]
        if self.dock_extension_uuid and self.dock_extension_uuid not in uuids:
            uuids.append(self.dock_extension_uuid)
        return tuple(uuids)

    def _effective_interface_value(self, key: str) -> Any:
        pending = self.pending.get(("org.gnome.desktop.interface", key))
        return pending.value if pending else self.settings.get("org.gnome.desktop.interface", key)

    def _stage_interface_companion(self, key: str, value: str, label: str) -> None:
        schema = "org.gnome.desktop.interface"
        if self.settings.supports(schema, key):
            self.pending[(schema, key)] = Change("desktop", schema, key, value, label)

    def discard(self) -> None:
        self.pending.clear(); self._notify()

    def apply(self) -> int:
        state_before = deepcopy(self.state.data)
        applied: list[tuple[Change, Any]] = []
        self.skipped.clear()
        try:
            for change in self.pending.values():
                try:
                    old = self.settings.get(change.schema, change.key)
                    value=change.value
                    if change.schema=="org.gnome.shell" and change.key in {"enabled-extensions","disabled-extensions"}:
                        current=list(old)
                        for uuid in self._managed_extension_uuids():
                            wanted=uuid in value
                            if wanted and uuid not in current:current.append(uuid)
                            if not wanted and uuid in current:current.remove(uuid)
                        value=current
                    self.settings.set(change.schema, change.key, value)
                except Exception as exc:
                    if not change.best_effort:
                        raise
                    self.skipped.append((change, str(exc)))
                    continue
                self.state.remember_original(change.domain, f"{change.schema}:{change.key}", old)
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
                        target=list(current)
                        for uuid in self._managed_extension_uuids():
                            originally_present=uuid in value
                            if originally_present and uuid not in target:target.append(uuid)
                            if not originally_present and uuid in target:target.remove(uuid)
                    self.settings.set(schema, key, target);applied.append((schema,key,current));restored += 1
        except Exception as exc:
            for schema,key,current in reversed(applied):
                try:self.settings.set(schema,key,current)
                except Exception:pass
            raise TransactionError(f"Restore failed: {exc}",len(applied)) from exc
        self.state.clear_original(domain)
        return restored

    def _reset(self, domains, factory=False) -> int:
        tokens=[]
        for domain in domains:
            exposed=self.factory_targets.get(domain,[]) if factory else []
            for token in [*self.state.data.get("managed",{}).get(domain,[]), *self.state.original(domain), *exposed]:
                if token not in tokens:tokens.append(token)
        applied=[]
        try:
            for token in tokens:
                schema,key=token.split(":",1)
                if not self.settings.supports(schema,key):continue
                current=self.settings.get(schema,key);applied.append((schema,key,current))
                if schema=="org.gnome.shell" and key in {"enabled-extensions","disabled-extensions"}:
                    self.settings.set(schema,key,[item for item in current if item not in self._managed_extension_uuids()])
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

    def reset_managed(self, domains=("desktop", "shell")) -> int:
        return self._reset(domains)

    def reset_factory(self, domains=("desktop", "shell")) -> int:
        return self._reset(domains,True)

    def _notify(self):
        for listener in tuple(self.listeners): listener()
