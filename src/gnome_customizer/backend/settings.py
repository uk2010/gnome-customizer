from __future__ import annotations

from typing import Any
import re
from pathlib import Path

from gi.repository import Gio, GLib


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

    def schema(self, schema_id: str):
        return self.source.lookup(schema_id, True) if self.source else None

    def supports(self, schema_id: str, key: str) -> bool:
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
        return self.settings(schema_id).get_value(key).unpack()

    def default(self, schema_id: str, key: str) -> Any:
        schema = self.schema(schema_id)
        if not schema or not schema.has_key(key):
            raise SettingsError(f"Unsupported setting: {schema_id} {key}")
        return schema.get_key(key).get_default_value().unpack()

    def range(self, schema_id: str, key: str) -> Any:
        schema = self.schema(schema_id)
        return schema.get_key(key).get_range().unpack() if schema and schema.has_key(key) else None

    def choices(self, schema_id: str, key: str) -> list[str]:
        value = self.range(schema_id, key)
        if not value: return []
        kind, details = value
        if kind == "enum": return list(details)
        return []

    def set(self, schema_id: str, key: str, value: Any) -> None:
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
