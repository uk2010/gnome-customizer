from __future__ import annotations

from gi.repository import Gdk, Gtk


def rgba(value: str) -> Gdk.RGBA:
    color = Gdk.RGBA()
    if not color.parse(value):
        color.parse("#000000")
    return color


def hex_color(color: Gdk.RGBA, alpha: bool = False) -> str:
    parts = [round(channel * 255) for channel in (color.red, color.green, color.blue)]
    if alpha:
        parts.append(round(color.alpha * 255))
    return "#" + "".join(f"{part:02X}" for part in parts)


def css_rgba(value: str, opacity: float = 1.0) -> str:
    color = rgba(value)
    alpha = max(0.0, min(1.0, color.alpha * opacity))
    channels = (round(color.red * 255), round(color.green * 255), round(color.blue * 255))
    return f"rgba({channels[0]}, {channels[1]}, {channels[2]}, {alpha:.3f})"


def color_button(value: str, title: str, alpha: bool = False) -> Gtk.ColorDialogButton:
    dialog = Gtk.ColorDialog(title=f"Choose {title}", with_alpha=alpha)
    button = Gtk.ColorDialogButton(dialog=dialog, valign=Gtk.Align.CENTER)
    button.set_rgba(rgba(value))
    button.set_tooltip_text(f"Choose {title.lower()}")
    return button
