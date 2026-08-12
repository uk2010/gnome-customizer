#!/usr/bin/python3
"""Exercise the real Appearance accent control under a compositor."""

from __future__ import annotations

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
    window._apply()

    loop = GLib.MainLoop()
    GLib.timeout_add(500, lambda: (loop.quit(), GLib.SOURCE_REMOVE)[1])
    loop.run()
    actual = (
        settings.get_string("accent-color"),
        settings.get_string("gtk-theme"),
        settings.get_string("icon-theme"),
    )
    expected = ("red", "Yaru-dark", "Yaru-dark")
    if actual != expected:
        raise SystemExit(f"Native accent runtime mismatch: expected {expected!r}, got {actual!r}")
    window.destroy()
    print("Appearance accent runtime passed: control and Apply wrote GNOME's native red accent")


if __name__ == "__main__":
    main()
