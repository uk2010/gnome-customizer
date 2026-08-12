#!/usr/bin/python3
"""Exercise the real Appearance accent control under a compositor."""

from __future__ import annotations

import hashlib
from pathlib import Path

import gi

gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib

from gnome_customizer.window import CustomizerWindow


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
    window.destroy()
    print("Appearance accent runtime passed: native accent, folder icons, and light/dark themes match GNOME Settings")


if __name__ == "__main__":
    main()
