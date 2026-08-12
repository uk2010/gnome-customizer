#!/usr/bin/python3
"""Exercise the real Appearance accent control under a compositor."""

from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile

import gi

gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib

from gnome_customizer.window import CustomizerWindow
from gnome_customizer.backend.themes import DESKTOP_THEME_SETTINGS, DOCK_THEME_SETTINGS, SHELL_SURFACE_SETTINGS, capture_current_theme, export_theme, import_theme, inspect_archive


def walk(widget):
    yield widget
    child = widget.get_first_child()
    while child:
        yield from walk(child)
        child = child.get_next_sibling()


def main() -> None:
    settings = Gio.Settings.new("org.gnome.desktop.interface")
    settings.set_string("color-scheme", "prefer-dark")
    settings.set_string("gtk-theme", "Yaru-blue-dark")
    settings.set_string("icon-theme", "Yaru-blue-dark")
    settings.set_string("accent-color", "blue")
    Gio.Settings.sync()

    app = Adw.Application(application_id="io.github.gnomecustomizer.AccentRuntimeTest")
    if not app.register(None):
        raise SystemExit("Could not register accent runtime test application")
    window = CustomizerWindow(app)
    shell_settings = Gio.Settings.new("io.github.gnomecustomizer.shell")
    shell_settings.set_boolean("overview-enabled", True)
    shell_settings.set_string("overview-hover-color", "#123456")
    shell_settings.set_double("overview-hover-opacity", 0.35)
    Gio.Settings.sync()
    accent = next(
        widget for widget in walk(window)
        if isinstance(widget, Adw.ComboRow) and widget.get_title() == "Accent Color"
    )
    choices = window.settings.choices("org.gnome.desktop.interface", "accent-color")
    accent.set_selected(choices.index("red"))
    pending = window.changes.pending.get(("org.gnome.desktop.interface", "accent-color"))
    if not pending or pending.value != "red":
        raise SystemExit("Appearance accent control did not stage the selected native value")
    staged_themes = (
        window.changes.pending.get(("org.gnome.desktop.interface", "gtk-theme")).value,
        window.changes.pending.get(("org.gnome.desktop.interface", "icon-theme")).value,
    )
    if staged_themes != ("Yaru-red-dark", "Yaru-red-dark"):
        raise SystemExit(f"Appearance accent did not stage GNOME's dark folder theme: {staged_themes!r}")
    window._apply()

    loop = GLib.MainLoop()
    GLib.timeout_add(500, lambda: (loop.quit(), GLib.SOURCE_REMOVE)[1])
    loop.run()
    actual = (
        settings.get_string("accent-color"),
        settings.get_string("gtk-theme"),
        settings.get_string("icon-theme"),
    )
    expected = ("red", "Yaru-red-dark", "Yaru-red-dark")
    if actual != expected:
        raise SystemExit(f"Native accent runtime mismatch: expected {expected!r}, got {actual!r}")
    accent.set_selected(choices.index("blue"))
    scheme = next(
        widget for widget in walk(window)
        if isinstance(widget, Adw.ComboRow) and widget.get_title() == "Color Scheme"
    )
    schemes = window.settings.choices("org.gnome.desktop.interface", "color-scheme")
    scheme.set_selected(schemes.index("default"))
    light = (
        window.changes.pending[("org.gnome.desktop.interface", "gtk-theme")].value,
        window.changes.pending[("org.gnome.desktop.interface", "icon-theme")].value,
    )
    if light != ("Yaru-blue", "Yaru-blue"):
        raise SystemExit(f"Light mode did not remap GNOME's folder theme: {light!r}")
    window._apply()
    Gio.Settings.sync()
    actual_light = (
        settings.get_string("accent-color"),
        settings.get_string("color-scheme"),
        settings.get_string("gtk-theme"),
        settings.get_string("icon-theme"),
    )
    expected_light = ("blue", "default", "Yaru-blue", "Yaru-blue")
    if actual_light != expected_light:
        raise SystemExit(f"Light accent runtime mismatch: expected {expected_light!r}, got {actual_light!r}")
    blue_folder = Path("/usr/share/icons/Yaru-blue/48x48/places/folder.png")
    red_folder = Path("/usr/share/icons/Yaru-red-dark/48x48/places/folder.png")
    if not blue_folder.is_file() or not red_folder.is_file():
        raise SystemExit("The GNOME-selected Yaru folder icon assets are not installed")
    if hashlib.sha256(blue_folder.read_bytes()).digest() == hashlib.sha256(red_folder.read_bytes()).digest():
        raise SystemExit("The selected blue and red Yaru folder assets are unexpectedly identical")
    save_row = next(
        widget for widget in walk(window)
        if isinstance(widget, Adw.ActionRow) and widget.get_title() == "Save Current Settings"
    )
    if not save_row:
        raise SystemExit("Themes page does not expose Save Current Settings")
    with tempfile.TemporaryDirectory(prefix="gnome-customizer-current-theme-") as temporary:
        expected_desktop = {field: window.settings.get(schema, key) for field, (schema, key) in DESKTOP_THEME_SETTINGS.items() if window.settings.supports(schema, key)}
        expected_shell = {surface: {field: window.settings.get("io.github.gnomecustomizer.shell", key) for field, key in fields.items() if window.settings.supports("io.github.gnomecustomizer.shell", key)} for surface, fields in SHELL_SURFACE_SETTINGS.items()}
        dock_schema = "org.gnome.shell.extensions.dash-to-dock"
        expected_dock = {field: window.settings.get(dock_schema, key) for field, key in DOCK_THEME_SETTINGS.items() if window.settings.supports(dock_schema, key)} if window.settings.schema(dock_schema) else {}
        manifest, assets = capture_current_theme(window.settings, "Runtime Current Theme", "Runtime Test")
        overview = manifest.get("shell", {}).get("overview", {})
        if (overview.get("hover_color"), overview.get("hover_opacity")) != ("#123456", 0.35):
            raise SystemExit(f"Current theme did not capture hover background settings: {overview!r}")
        archive_path = export_theme(manifest, assets, Path(temporary) / "current.gctheme")
        saved, archive = inspect_archive(archive_path)
        archive.close()
        if saved.get("desktop", {}).get("accent") != "blue":
            raise SystemExit("Saved current theme did not round-trip the applied native accent")
        for field, value in expected_desktop.items():
            if saved.get("desktop", {}).get(field) != value:
                raise SystemExit(f"Saved current theme lost desktop setting {field}: {saved.get('desktop', {}).get(field)!r} != {value!r}")
        for field, value in expected_dock.items():
            if saved.get("shell", {}).get("dock", {}).get(field) != value:
                raise SystemExit(f"Saved current theme lost Dock setting {field}: {saved.get('shell', {}).get('dock', {}).get(field)!r} != {value!r}")
        for surface, fields in expected_shell.items():
            for field, value in fields.items():
                if saved.get("shell", {}).get(surface, {}).get(field) != value:
                    raise SystemExit(f"Saved current theme lost Shell setting {surface}.{field}")
        imported = import_theme(archive_path, Path(temporary) / "themes")
        window._stage_theme(imported)
        staged_hover = window.changes.pending.get(("io.github.gnomecustomizer.shell", "overview-hover-color"))
        staged_menu = window.changes.pending.get(("io.github.gnomecustomizer.shell", "menu-enabled"))
        if not staged_hover or staged_hover.value != "#123456" or not staged_menu or staged_menu.value is not False:
            raise SystemExit("Applying the saved current theme did not restore hover tint and disabled surfaces")
        for field, (schema, key) in DESKTOP_THEME_SETTINGS.items():
            if field in expected_desktop and (not (pending := window.changes.pending.get((schema, key))) or pending.value != expected_desktop[field]):
                raise SystemExit(f"Applying the saved theme did not stage desktop setting {field}")
        for field, key in DOCK_THEME_SETTINGS.items():
            if field in expected_dock and (not (pending := window.changes.pending.get((dock_schema, key))) or pending.value != expected_dock[field]):
                raise SystemExit(f"Applying the saved theme did not stage Dock setting {field}")
        for surface, fields in SHELL_SURFACE_SETTINGS.items():
            for field, key in fields.items():
                if field in expected_shell[surface] and (not (pending := window.changes.pending.get(("io.github.gnomecustomizer.shell", key))) or pending.value != expected_shell[surface][field]):
                    raise SystemExit(f"Applying the saved theme did not stage Shell setting {surface}.{field}")
        window._apply()
        apply_loop = GLib.MainLoop()
        GLib.timeout_add(500, lambda: (apply_loop.quit(), GLib.SOURCE_REMOVE)[1])
        apply_loop.run()
        Gio.Settings.sync()
        for field, (schema, key) in DESKTOP_THEME_SETTINGS.items():
            if field in expected_desktop and window.settings.get(schema, key) != expected_desktop[field]:
                raise SystemExit(f"Restored desktop setting did not verify after Apply: {field}")
        for field, key in DOCK_THEME_SETTINGS.items():
            if field in expected_dock and window.settings.get(dock_schema, key) != expected_dock[field]:
                raise SystemExit(f"Restored Dock setting did not verify after Apply: {field}")
        for surface, fields in SHELL_SURFACE_SETTINGS.items():
            for field, key in fields.items():
                if field in expected_shell[surface] and window.settings.get("io.github.gnomecustomizer.shell", key) != expected_shell[surface][field]:
                    raise SystemExit(f"Restored Shell setting did not verify after Apply: {surface}.{field}")
    window.destroy()
    print("Appearance accent runtime passed: native accent, folder icons, and light/dark themes match GNOME Settings")


if __name__ == "__main__":
    main()
