from __future__ import annotations

from typing import Any
import subprocess
import re
from pathlib import Path

from gi.repository import Gio, GLib

POWER_PROFILES_SCHEMA = "org.freedesktop.UPower.PowerProfiles"
POWER_PROFILES_PATH = "/org/freedesktop/UPower/PowerProfiles"
POWER_PROFILE_KEY = "active-profile"
POWER_PROFILE_CHOICES = ("power-saver", "balanced", "performance")


class SettingsError(RuntimeError):
    pass


YARU_ACCENT_SUFFIX = {
    # This is Ubuntu's GNOME 50 / patched Libadwaita mapping.  The names are
    # Yaru's installed theme variants, not guesses derived from the enum.
    "blue": "blue",
    "teal": "prussiangreen",
    "green": "olive",
    "yellow": "yellow",
    "orange": None,
    "red": "red",
    "pink": "magenta",
    "purple": "purple",
    "slate": "sage",
    "brown": "wartybrown",
}


def yaru_theme_for_accent(accent: str, dark: bool) -> str:
    """Return the Yaru GTK/icon theme selected by Ubuntu's GNOME 50 panel."""
    if accent not in YARU_ACCENT_SUFFIX:
        raise ValueError(f"Unsupported GNOME accent: {accent}")
    suffix = YARU_ACCENT_SUFFIX[accent]
    return "Yaru" + (f"-{suffix}" if suffix else "") + ("-dark" if dark else "")


class SettingsBackend:
    """Schema-aware GSettings access; unsupported keys never become controls."""

    def __init__(self):
        self.source = Gio.SettingsSchemaSource.get_default()
        self._settings: dict[str, Gio.Settings] = {}
        self._power_profiles_proxy = None
        self._power_profiles_proxy_loaded = False

    def _power_proxy(self):
        if not self._power_profiles_proxy_loaded:
            self._power_profiles_proxy_loaded = True
            try:
                self._power_profiles_proxy = Gio.DBusProxy.new_for_bus_sync(
                    Gio.BusType.SYSTEM, Gio.DBusProxyFlags.NONE, None,
                    POWER_PROFILES_SCHEMA, POWER_PROFILES_PATH,
                    POWER_PROFILES_SCHEMA, None,
                )
            except GLib.Error:
                self._power_profiles_proxy = None
        return self._power_profiles_proxy

    def _power_property(self, name: str) -> Any:
        proxy = self._power_proxy()
        if proxy is None: raise SettingsError("Power Profiles service is unavailable")
        try:
            result = proxy.call_sync(
                "org.freedesktop.DBus.Properties.Get",
                GLib.Variant("(ss)", (POWER_PROFILES_SCHEMA, name)),
                Gio.DBusCallFlags.NONE, -1, None,
            )
        except GLib.Error as exc:
            raise SettingsError(f"Could not read the system power profile: {exc.message}") from exc
        return result.unpack()[0]

    def power_profile_info(self) -> list[dict[str, Any]]:
        if not self.supports(POWER_PROFILES_SCHEMA, POWER_PROFILE_KEY): return []
        profiles = self._power_property("Profiles")
        return profiles if isinstance(profiles, list) else []

    def power_profile_summary(self) -> str:
        if not self.supports(POWER_PROFILES_SCHEMA, POWER_PROFILE_KEY):
            return "Power Profiles service is unavailable"
        profiles = self.power_profile_info()
        performance = next((item for item in profiles if item.get("Profile") == "performance"), None)
        if performance is None:
            return "Performance remains listed, but this hardware or driver does not currently expose it"
        degraded = self._power_property("PerformanceDegraded")
        if degraded:
            return f"Performance is available but currently degraded: {str(degraded).replace('-', ' ')}"
        driver = performance.get("CpuDriver") or performance.get("PlatformDriver") or performance.get("Driver")
        return f"Performance is available{f' through {driver}' if driver else ''}"

    def schema(self, schema_id: str):
        return self.source.lookup(schema_id, True) if self.source else None

    @staticmethod
    def _extension_roots():
        return (
            Path.home() / ".local/share/gnome-shell/extensions",
            Path("/usr/local/share/gnome-shell/extensions"),
            Path("/usr/share/gnome-shell/extensions"),
        )

    @classmethod
    def extension_available(cls, uuid: str) -> bool:
        """Return true only when the extension has a usable installed payload."""
        required = ["metadata.json", "extension.js"]
        if uuid == "blur-my-shell@aunetx":
            required.append("components/panel.js")
        elif uuid == "dash-to-dock@micxgx.gmail.com":
            required.append("dependencies/gi.js")
        return any(all((root / uuid / name).is_file() for name in required) for root in cls._extension_roots())

    def ensure_bundled_extensions(self):
        """Use bundled upstream extensions when the distro has no provider."""
        if not self.supports("org.gnome.shell", "enabled-extensions"):
            return []
        installed = self.extension_available
        enabled = list(self.get("org.gnome.shell", "enabled-extensions"))
        disabled = list(self.get("org.gnome.shell", "disabled-extensions")) if self.supports("org.gnome.shell", "disabled-extensions") else []
        candidates = {
            "blur-my-shell@aunetx": ("blur-my-shell@aunetx",),
            "dock": ("ubuntu-dock@ubuntu.com", "dash-to-dock@micxgx.gmail.com"),
        }
        selected = []
        removed = []
        for group in candidates.values():
            # A desktop may have both Ubuntu Dock and upstream Dash to Dock
            # installed.  Only one actor can own the dash; prefer an already
            # active provider, then prefer Ubuntu Dock when it is installed.
            candidate = next((uuid for uuid in group if installed(uuid) and uuid in enabled and uuid not in disabled), None)
            candidate = candidate or next((uuid for uuid in group if installed(uuid)), None)
            if not candidate:
                continue
            if candidate not in enabled or candidate in disabled:
                selected.append(candidate)
            for uuid in group:
                if uuid != candidate and uuid in enabled:
                    enabled.remove(uuid)
                    removed.append(uuid)
                if uuid != candidate and uuid in disabled:
                    disabled.remove(uuid)
        for uuid in selected:
            if uuid not in enabled:
                enabled.append(uuid)
            if uuid in disabled:
                disabled.remove(uuid)
        # The earlier GNOME Customizer companion contained a partial blur and
        # must not run beside the complete upstream Blur My Shell extension.
        # If the upstream extension is only installed per-user, however, its
        # schema is not necessarily visible to this application's GSettings
        # schema source. In that fallback case the companion still owns the
        # overview controls and must remain enabled across a session restart.
        companion = "gnome-customizer@io.github.gnomecustomizer"
        upstream_schema_available = bool(self.schema("org.gnome.shell.extensions.blur-my-shell"))
        companion_schema = "io.github.gnomecustomizer.shell"
        companion_surface_keys = (
            "panel-enabled", "menu-enabled", "overview-enabled",
            "alphabetical-app-grid", "folder-tile-transparency-enabled",
            "folder-dialog-transparency-enabled",
        )
        companion_needed = any(
            self.supports(companion_schema, key) and bool(self.get(companion_schema, key))
            for key in companion_surface_keys
        )
        companion_needed = companion_needed or (
            self.supports(companion_schema, "activities-button-enabled")
            and not self.get(companion_schema, "activities-button-enabled")
        )
        if installed("blur-my-shell@aunetx") and upstream_schema_available and companion in enabled and not companion_needed:
            enabled.remove(companion)
            removed.append(companion)
        elif installed(companion) and (not upstream_schema_available or companion_needed) and (companion not in enabled or companion in disabled):
            selected.append(companion)
        original_enabled = list(self.get("org.gnome.shell", "enabled-extensions"))
        original_disabled = list(self.get("org.gnome.shell", "disabled-extensions")) if self.supports("org.gnome.shell", "disabled-extensions") else []
        global_extensions_disabled = (
            self.supports("org.gnome.shell", "disable-user-extensions")
            and self.get("org.gnome.shell", "disable-user-extensions")
        )
        changed = (
            enabled != original_enabled
            or disabled != original_disabled
            or global_extensions_disabled
        )
        if changed:
            self.set("org.gnome.shell", "enabled-extensions", enabled)
            if self.supports("org.gnome.shell", "disable-user-extensions"):
                self.set("org.gnome.shell", "disable-user-extensions", False)
            if self.supports("org.gnome.shell", "disabled-extensions"):
                self.set("org.gnome.shell", "disabled-extensions", disabled)
        for uuid in selected:
            try:
                subprocess.run(["gnome-extensions", "enable", uuid], check=False, timeout=10, capture_output=True)
            except (OSError, subprocess.TimeoutExpired):
                pass
        for uuid in removed:
            try:
                subprocess.run(["gnome-extensions", "disable", uuid], check=False, timeout=10, capture_output=True)
            except (OSError, subprocess.TimeoutExpired):
                pass
        return selected

    def supports(self, schema_id: str, key: str) -> bool:
        if schema_id == POWER_PROFILES_SCHEMA:
            return key == POWER_PROFILE_KEY and self._power_proxy() is not None
        schema = self.schema(schema_id)
        return bool(schema and schema.has_key(key))

    def settings(self, schema_id: str) -> Gio.Settings:
        if not self.schema(schema_id):
            raise SettingsError(f"GSettings schema is unavailable: {schema_id}")
        if schema_id not in self._settings:
            self._settings[schema_id] = Gio.Settings.new(schema_id)
        return self._settings[schema_id]

    def get(self, schema_id: str, key: str) -> Any:
        if not self.supports(schema_id, key):
            raise SettingsError(f"Unsupported setting: {schema_id} {key}")
        if schema_id == POWER_PROFILES_SCHEMA:
            return self._power_property("ActiveProfile")
        return self.settings(schema_id).get_value(key).unpack()

    def default(self, schema_id: str, key: str) -> Any:
        if schema_id == POWER_PROFILES_SCHEMA and key == POWER_PROFILE_KEY:
            return "balanced"
        schema = self.schema(schema_id)
        if not schema or not schema.has_key(key):
            raise SettingsError(f"Unsupported setting: {schema_id} {key}")
        return schema.get_key(key).get_default_value().unpack()

    def range(self, schema_id: str, key: str) -> Any:
        if schema_id == POWER_PROFILES_SCHEMA and key == POWER_PROFILE_KEY:
            return "enum", POWER_PROFILE_CHOICES
        schema = self.schema(schema_id)
        return schema.get_key(key).get_range().unpack() if schema and schema.has_key(key) else None

    def choices(self, schema_id: str, key: str) -> list[str]:
        value = self.range(schema_id, key)
        if not value: return []
        kind, details = value
        if kind == "enum": return list(details)
        return []

    def set(self, schema_id: str, key: str, value: Any) -> None:
        if schema_id == POWER_PROFILES_SCHEMA:
            if key != POWER_PROFILE_KEY or value not in POWER_PROFILE_CHOICES:
                raise SettingsError(f"Invalid power profile: {value!r}")
            if self.get(schema_id, key) == value:
                return
            available = {item.get("Profile") for item in self.power_profile_info()}
            if value not in available:
                raise SettingsError(
                    f"{value.replace('-', ' ').title()} is not exposed by power-profiles-daemon on this hardware; "
                    "it cannot be forced safely without driver or firmware support"
                )
            try:
                self._power_proxy().call_sync(
                    "org.freedesktop.DBus.Properties.Set",
                    GLib.Variant("(ssv)", (POWER_PROFILES_SCHEMA, "ActiveProfile", GLib.Variant("s", value))),
                    Gio.DBusCallFlags.NONE, -1, None,
                )
            except GLib.Error as exc:
                raise SettingsError(f"Could not switch to {value.replace('-', ' ')}: {exc.message}") from exc
            if self.get(schema_id, key) != value:
                raise SettingsError(f"Power Profiles service did not activate {value.replace('-', ' ')}")
            return
        if schema_id == "io.github.gnomecustomizer.shell" and (key.endswith("-color") or key.endswith("-color2")):
            if not isinstance(value,str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?",value):raise SettingsError(f"Invalid controlled color for {key}")
        setting = self.settings(schema_id)
        if not setting.is_writable(key):
            raise SettingsError(f"GNOME has locked {schema_id} {key}")
        current = setting.get_value(key)
        try:
            variant = GLib.Variant(current.get_type_string(), value)
        except (TypeError, OverflowError) as exc:
            raise SettingsError(f"Invalid value for {schema_id} {key}: {value!r}") from exc
        if not setting.set_value(key, variant):
            raise SettingsError(f"GNOME rejected {schema_id} {key}")
        Gio.Settings.sync()
        if not setting.get_value(key).equal(variant):
            raise SettingsError(f"GNOME did not persist {schema_id} {key}")

    def reset_value(self, schema_id: str, key: str) -> Any:
        if schema_id == POWER_PROFILES_SCHEMA and key == POWER_PROFILE_KEY:
            return "balanced"
        if not self.supports(schema_id, key):
            raise SettingsError(f"Unsupported setting: {schema_id} {key}")
        ubuntu_defaults={
            ("org.gnome.shell.ubuntu","color-scheme"):"default",
            ("org.gnome.desktop.interface","color-scheme"):"default",
            ("org.gnome.desktop.interface","accent-color"):"orange",
            ("org.gnome.desktop.interface","gtk-theme"):"Yaru",
            ("org.gnome.desktop.interface","icon-theme"):"Yaru",
            ("org.gnome.desktop.interface","cursor-theme"):"Yaru",
            ("org.gnome.desktop.interface","font-name"):"Ubuntu Sans 11",
            ("org.gnome.desktop.sound","theme-name"):"Yaru",
            ("org.gnome.desktop.background","picture-uri"):"file:///usr/share/backgrounds/warty-final-ubuntu.png",
            ("org.gnome.desktop.background","picture-uri-dark"):"file:///usr/share/backgrounds/ubuntu-wallpaper-d.png",
        }
        target=ubuntu_defaults.get((schema_id,key)) if Path("/usr/share/themes/Yaru").is_dir() else None
        return target if target is not None else self.schema(schema_id).get_key(key).get_default_value().unpack()

    def reset(self, schema_id: str, key: str) -> None:
        if not self.supports(schema_id, key):
            raise SettingsError(f"Unsupported setting: {schema_id} {key}")
        if schema_id == POWER_PROFILES_SCHEMA:
            self.set(schema_id, key, self.reset_value(schema_id, key));return
        setting = self.settings(schema_id)
        if not setting.is_writable(key):
            raise SettingsError(f"GNOME has locked {schema_id} {key}")
        target=self.reset_value(schema_id,key)
        ubuntu_override=Path("/usr/share/themes/Yaru").is_dir() and (schema_id,key) in {
            ("org.gnome.shell.ubuntu","color-scheme"), ("org.gnome.desktop.interface","color-scheme"),
            ("org.gnome.desktop.interface","accent-color"), ("org.gnome.desktop.interface","gtk-theme"),
            ("org.gnome.desktop.interface","icon-theme"), ("org.gnome.desktop.interface","cursor-theme"),
            ("org.gnome.desktop.interface","font-name"), ("org.gnome.desktop.sound","theme-name"),
            ("org.gnome.desktop.background","picture-uri"), ("org.gnome.desktop.background","picture-uri-dark"),
        }
        if ubuntu_override:self.set(schema_id,key,target);return
        expected = self.schema(schema_id).get_key(key).get_default_value()
        setting.reset(key); Gio.Settings.sync()
        if not setting.get_value(key).equal(expected):
            raise SettingsError(f"GNOME did not reset {schema_id} {key}")
