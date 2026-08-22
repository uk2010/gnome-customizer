from __future__ import annotations

import base64

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Adw, Gdk, GdkPixbuf, Gio, GLib, Gtk


ACCENT_COLORS = {
    "blue": "#3584e4", "teal": "#2190a4", "green": "#3a944a",
    "yellow": "#e5a50a", "orange": "#e66100", "red": "#c01c28",
    "pink": "#c061cb", "purple": "#9141ac", "slate": "#6f8396",
    "brown": "#986a44",
}


def _rgba(value, fallback):
    color = Gdk.RGBA()
    try:
        if value and color.parse(str(value)):
            return color
    except (TypeError, ValueError):
        pass
    color.parse(fallback)
    return color


def _rounded_rectangle(context, x, y, width, height, radius):
    radius = min(radius, width / 2, height / 2)
    context.new_sub_path()
    context.arc(x + width - radius, y + radius, radius, -1.5708, 0)
    context.arc(x + width - radius, y + height - radius, radius, 0, 1.5708)
    context.arc(x + radius, y + height - radius, radius, 1.5708, 3.1416)
    context.arc(x + radius, y + radius, radius, 3.1416, 4.7124)
    context.close_path()


class PreviewCanvas(Gtk.DrawingArea):
    """A compositor-independent approximation of the currently staged UI."""

    def __init__(self, settings, changes, content_width=620, content_height=400):
        super().__init__(content_width=content_width, content_height=content_height, hexpand=True, vexpand=True)
        self.settings = settings
        self.changes = changes
        self.mode = "desktop"
        self.login_state = {}
        self._wallpaper_uri = None
        self._wallpaper = None
        self._login_asset_cache = {}
        self._dock_icons = {}
        self._desktop_capture = None
        self.set_draw_func(self._draw)

    def update(self, mode, login_state):
        self.mode = mode
        self.login_state = login_state or {}
        if mode == "desktop":
            self._load_wallpaper()
            self._load_dock_icons()
        self.queue_draw()

    def set_desktop_capture(self, uri):
        self._desktop_capture = None
        try:
            path = Gio.File.new_for_uri(str(uri)).get_path() if uri else None
            if path:
                self._desktop_capture = GdkPixbuf.Pixbuf.new_from_file(path)
        except (GLib.Error, TypeError, ValueError):
            self._desktop_capture = None
        self.queue_draw()

    def _value(self, schema, key, fallback=None):
        pending = self.changes.pending.get((schema, key))
        if pending is not None:
            return pending.value
        try:
            return self.settings.get(schema, key)
        except Exception:
            return fallback

    def _accent(self):
        value = self._value("org.gnome.desktop.interface", "accent-color", "blue")
        return _rgba(ACCENT_COLORS.get(str(value), value), "#3584e4")

    def _load_wallpaper(self):
        dark = self._value("org.gnome.desktop.interface", "color-scheme", "default") == "prefer-dark"
        key = "picture-uri-dark" if dark else "picture-uri"
        uri = self._value("org.gnome.desktop.background", key, None)
        if not uri:
            uri = self._value("org.gnome.desktop.background", "picture-uri", None)
        if uri == self._wallpaper_uri:
            return
        self._wallpaper_uri = uri
        self._wallpaper = None
        try:
            path = Gio.File.new_for_uri(str(uri)).get_path() if uri else None
            if path:
                self._wallpaper = GdkPixbuf.Pixbuf.new_from_file(path)
        except (GLib.Error, TypeError, ValueError):
            pass

    def _load_dock_icons(self):
        names = ("org.gnome.Nautilus", "web-browser", "org.gnome.Settings", "utilities-terminal", "view-app-grid", "user-trash")
        try:
            theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
            for name in names:
                if name in self._dock_icons:
                    continue
                paintable = theme.lookup_icon(name, [], 64, 1, Gtk.TextDirection.NONE, 0)
                file = paintable.get_file() if paintable else None
                path = file.get_path() if file else None
                if path:
                    self._dock_icons[name] = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 64, 64, True)
        except (GLib.Error, TypeError, ValueError):
            pass

    def _paint_wallpaper(self, context, width, height, dark):
        image = self._desktop_capture or self._wallpaper
        if image is not None:
            source_width = image.get_width()
            source_height = image.get_height()
            scale = max(width / source_width, height / source_height)
            draw_width, draw_height = source_width * scale, source_height * scale
            context.save()
            context.translate((width - draw_width) / 2, (height - draw_height) / 2)
            context.scale(scale, scale)
            Gdk.cairo_set_source_pixbuf(context, image, 0, 0)
            context.paint()
            context.restore()
            return

        primary = _rgba(self._value("org.gnome.desktop.background", "primary-color", None), "#202124" if dark else "#d9e2f3")
        secondary = _rgba(self._value("org.gnome.desktop.background", "secondary-color", None), "#30343b" if dark else "#f7f9fc")
        # Cairo's pattern API is available through the context without adding
        # a dependency on a separate graphics package.
        import cairo
        pattern = cairo.LinearGradient(0, 0, width, height)
        pattern.add_color_stop_rgba(0, primary.red, primary.green, primary.blue, 1)
        pattern.add_color_stop_rgba(1, secondary.red, secondary.green, secondary.blue, 1)
        context.set_source(pattern)
        context.paint()

    def _load_login_asset(self, role):
        asset = self.login_state.get("assets", {}).get(role)
        if not asset:
            return None
        key = (role, asset.get("data") if isinstance(asset, dict) else str(asset))
        if key in self._login_asset_cache:
            return self._login_asset_cache[key]
        image = None
        try:
            if isinstance(asset, dict) and asset.get("data"):
                loader = GdkPixbuf.PixbufLoader()
                loader.write(base64.b64decode(asset["data"]))
                loader.close()
                image = loader.get_pixbuf()
            elif isinstance(asset, str):
                path = Gio.File.new_for_uri(asset).get_path() if asset.startswith("file:") else asset
                if path:
                    image = GdkPixbuf.Pixbuf.new_from_file(path)
        except (GLib.Error, TypeError, ValueError):
            image = None
        self._login_asset_cache[key] = image
        return image

    @staticmethod
    def _paint_login_image(context, image, x, y, width, height, contain=False):
        if image is None:
            return
        source_width, source_height = image.get_width(), image.get_height()
        scale = min(width / source_width, height / source_height) if contain else max(width / source_width, height / source_height)
        draw_width, draw_height = source_width * scale, source_height * scale
        context.save()
        context.rectangle(x, y, width, height)
        context.clip()
        context.translate(x + (width - draw_width) / 2, y + (height - draw_height) / 2)
        context.scale(scale, scale)
        Gdk.cairo_set_source_pixbuf(context, image, 0, 0)
        context.paint()
        context.restore()

    @staticmethod
    def _text(context, text, x, y, size=13, color=(1, 1, 1, 1), bold=False):
        context.set_source_rgba(*color)
        context.select_font_face("Sans", 0, 1 if bold else 0)
        context.set_font_size(size)
        context.move_to(x, y)
        context.show_text(str(text))

    def _draw(self, area, context, width, height):
        if self.mode == "login":
            self._draw_login(context, width, height)
        else:
            self._draw_desktop(context, width, height)

    def _window(self, context, x, y, w, h, title, kind, dark, accent, text, muted):
        """Draw a small GNOME-style application window, not a bare rectangle."""
        surface = _rgba("#252525" if dark else "#ffffff", "#ffffff")
        header = _rgba("#303030" if dark else "#f6f5f4", "#f6f5f4")
        border = _rgba("#555555" if dark else "#d0d0d0", "#d0d0d0")
        context.save()
        context.set_source_rgba(0, 0, 0, .28)
        _rounded_rectangle(context, x + 5, y + 7, w, h, 12)
        context.fill()
        _rounded_rectangle(context, x, y, w, h, 12)
        context.set_source_rgba(surface.red, surface.green, surface.blue, .98)
        context.fill()
        _rounded_rectangle(context, x, y, w, 38, 12)
        context.set_source_rgba(header.red, header.green, header.blue, .99)
        context.fill()
        context.set_source_rgba(border.red, border.green, border.blue, .65)
        context.set_line_width(1)
        _rounded_rectangle(context, x, y, w, h, 12)
        context.stroke()
        self._text(context, title, x + 44, y + 25, 12, text, True)
        context.set_source_rgba(accent.red, accent.green, accent.blue, 1)
        context.arc(x + 20, y + 19, 9, 0, 6.2832)
        context.fill()
        for index, shade in enumerate(((.65, .65, .65), (.48, .48, .48), (.34, .34, .34))):
            context.set_source_rgba(*shade, .9)
            context.arc(x + w - 52 + index * 16, y + 19, 4, 0, 6.2832)
            context.fill()

        body_y = y + 38
        if kind == "files":
            sidebar_w = min(120, w * .25)
            context.set_source_rgba(header.red, header.green, header.blue, .72)
            context.rectangle(x, body_y, sidebar_w, h - 38)
            context.fill()
            for index, label in enumerate(("Home", "Recent", "Starred", "Downloads")):
                self._text(context, label, x + 14, body_y + 28 + index * 25, 10, muted if index else (accent.red, accent.green, accent.blue, 1), index == 0)
            content_x = x + sidebar_w + 18
            self._text(context, "Home", content_x, body_y + 26, 11, text, True)
            for index, label in enumerate(("Documents", "Pictures", "Downloads", "Music")):
                col, row = index % 2, index // 2
                cell_x, cell_y = content_x + col * 86, body_y + 52 + row * 66
                context.set_source_rgba(accent.red, accent.green, accent.blue, .18)
                _rounded_rectangle(context, cell_x, cell_y, 54, 40, 8)
                context.fill()
                self._text(context, "▰", cell_x + 18, cell_y + 24, 16, (accent.red, accent.green, accent.blue, 1), True)
                self._text(context, label, cell_x - 4, cell_y + 55, 9, muted)
        elif kind == "settings":
            sidebar_w = min(105, w * .24)
            context.set_source_rgba(header.red, header.green, header.blue, .72)
            context.rectangle(x, body_y, sidebar_w, h - 38)
            context.fill()
            for index, label in enumerate(("Wi-Fi", "Appearance", "Notifications", "Power")):
                self._text(context, label, x + 11, body_y + 28 + index * 25, 9, (accent.red, accent.green, accent.blue, 1) if index == 1 else muted, index == 1)
            content_x = x + sidebar_w + 18
            self._text(context, "Appearance", content_x, body_y + 26, 12, text, True)
            self._text(context, "Style", content_x, body_y + 54, 9, muted)
            self._text(context, "Dark" if dark else "Light", content_x + 72, body_y + 54, 10, text)
            self._text(context, "Accent color", content_x, body_y + 82, 9, muted)
            context.set_source_rgba(accent.red, accent.green, accent.blue, 1)
            context.arc(content_x + 78, body_y + 78, 8, 0, 6.2832)
            context.fill()
            self._text(context, "Text scaling", content_x, body_y + 110, 9, muted)
            self._text(context, f"{float(self._value('org.gnome.desktop.interface', 'text-scaling-factor', 1)):.2f}×", content_x + 72, body_y + 110, 10, text)
        else:
            content_x = x + 18
            self._text(context, "GNOME Customizer", content_x, body_y + 28, 12, text, True)
            for index, label in enumerate(("Appearance", "Dock", "Blur", "Top Bar")):
                row_y = body_y + 50 + index * 25
                context.set_source_rgba(accent.red, accent.green, accent.blue, .16 if index == 0 else .08)
                _rounded_rectangle(context, content_x, row_y - 14, w - 36, 20, 6)
                context.fill()
                self._text(context, label, content_x + 9, row_y, 9, text if index == 0 else muted)
        context.restore()

    def _draw_desktop(self, context, width, height):
        dark = self._value("org.gnome.desktop.interface", "color-scheme", "default") == "prefer-dark"
        self._paint_wallpaper(context, width, height, dark)
        if self._desktop_capture is not None:
            muted = (0.82, 0.82, 0.85, 1)
            self._text(context, "Current desktop capture · staged values remain in the inspector", 18, height - 12, 11, muted)
            return
        panel = _rgba(self._value("io.github.gnomecustomizer.shell", "panel-color", None), "#282828" if dark else "#f8f8f8")
        panel2 = _rgba(self._value("io.github.gnomecustomizer.shell", "panel-color2", None), "#40404a")
        accent = self._accent()
        panel_text = _rgba(self._value("io.github.gnomecustomizer.shell", "panel-text-color", None), "#ffffff" if dark else "#202124")
        text = (panel_text.red, panel_text.green, panel_text.blue, 1)
        muted = (0.72, 0.72, 0.75, 1) if dark else (0.34, 0.36, 0.4, 1)

        overview_enabled = bool(self._value("io.github.gnomecustomizer.shell", "overview-enabled", False))
        if overview_enabled:
            overview = _rgba(self._value("io.github.gnomecustomizer.shell", "overview-color", None), "#18243a")
            opacity = float(self._value("io.github.gnomecustomizer.shell", "overview-opacity", 0.0) or 0)
            context.set_source_rgba(overview.red, overview.green, overview.blue, max(0, min(1, opacity)))
            context.paint()

        panel_opacity = float(self._value("io.github.gnomecustomizer.shell", "panel-opacity", 1) or 1)
        panel_gradient = bool(self._value("io.github.gnomecustomizer.shell", "panel-gradient-enabled", False))
        panel_radius = float(self._value("io.github.gnomecustomizer.shell", "panel-radius", 0) or 0)
        _rounded_rectangle(context, 0, 0, width, 42, panel_radius)
        if panel_gradient:
            import cairo
            pattern = cairo.LinearGradient(0, 0, width, 0)
            pattern.add_color_stop_rgba(0, panel.red, panel.green, panel.blue, max(0, min(1, panel_opacity)))
            pattern.add_color_stop_rgba(1, panel2.red, panel2.green, panel2.blue, max(0, min(1, panel_opacity)))
            context.set_source(pattern)
        else:
            context.set_source_rgba(panel.red, panel.green, panel.blue, max(0.1, min(1, panel_opacity)))
        context.fill()
        activities = bool(self._value("io.github.gnomecustomizer.shell", "activities-button-enabled", True))
        if activities:
            self._text(context, "Activities", 18, 26, 13, text, True)
        clock_format = self._value("org.gnome.desktop.interface", "clock-format", "24h")
        clock = "10:30 AM" if clock_format == "12h" else "10:30"
        if self._value("org.gnome.desktop.interface", "clock-show-seconds", False):
            clock = clock.replace(" AM", ":42 AM").replace("10:30", "10:30:42")
        clock_parts = [clock]
        if self._value("org.gnome.desktop.interface", "clock-show-date", True):
            clock_parts.insert(0, "Aug 11")
        if self._value("org.gnome.desktop.interface", "clock-show-weekday", False):
            clock_parts.insert(0, "Tue")
        self._text(context, "  ".join(clock_parts), width / 2 - 30, 26, 12, text)
        battery = " 82%" if self._value("org.gnome.desktop.interface", "show-battery-percentage", False) else ""
        self._text(context, f"Wi-Fi{battery}", width - 90, 26, 11, muted)

        # Use a restrained pair of representative windows when a real desktop
        # capture is not available. This makes the preview feel like a real
        # workspace while keeping the result clearly illustrative.
        if self._desktop_capture is None:
            primary_w = min(width * .68, 430)
            primary_h = min(height * .46, 190)
            self._window(context, (width - primary_w) * .42, max(58, height * .18), primary_w, primary_h, "Files", "files", dark, accent, text, muted)
            secondary_w = min(width * .34, 220)
            secondary_h = min(height * .34, 138)
            self._window(context, width - secondary_w - 18, max(76, height * .34), secondary_w, secondary_h, "Settings", "settings", dark, accent, text, muted)

        dock_position = self._value("org.gnome.shell.extensions.dash-to-dock", "dock-position", "BOTTOM")
        dock = _rgba(self._value("org.gnome.shell.extensions.dash-to-dock", "background-color", None), "#1d1f24")
        dock_opacity = float(self._value("org.gnome.shell.extensions.dash-to-dock", "background-opacity", .92) or 0)
        dock_panel = bool(self._value("org.gnome.shell.extensions.dash-to-dock", "extend-height", False))
        dock_autohide = bool(self._value("org.gnome.shell.extensions.dash-to-dock", "autohide", False))
        if dock_autohide and not self._value("org.gnome.shell.extensions.dash-to-dock", "dock-fixed", False):
            dock_opacity *= .25
        requested_icon_size = float(self._value("org.gnome.shell.extensions.dash-to-dock", "dash-max-icon-size", 26) or 26)
        icon_size = max(16, min(52, requested_icon_size))
        count = 5
        if not self._value("org.gnome.shell.extensions.dash-to-dock", "show-favorites", True):
            count -= 2
        if not self._value("org.gnome.shell.extensions.dash-to-dock", "show-running", True):
            count -= 1
        if not self._value("org.gnome.shell.extensions.dash-to-dock", "show-show-apps-button", True):
            count -= 1
        count = max(1, count)
        if dock_position in {"TOP", "BOTTOM"}:
            dock_w = min(width - 24, max(width * .48, count * icon_size + (count - 1) * 12 + 32))
            dock_h = icon_size + 28
            icon_size = min(icon_size, max(16, dock_w - 32 - (count - 1) * 8) / count)
        else:
            dock_w = icon_size + 28
            dock_h = min(height - 70, max(height * .44, count * icon_size + (count - 1) * 12 + 32))
            icon_size = min(icon_size, max(16, dock_h - 32 - (count - 1) * 8) / count)
        if dock_panel and dock_position in {"TOP", "BOTTOM"}:
            dock_w = width
        elif dock_panel:
            dock_h = height
        dock_x = (width - dock_w) / 2 if dock_position in {"TOP", "BOTTOM"} else (8 if dock_position == "LEFT" else width - dock_w - 8)
        dock_y = 50 if dock_position == "TOP" else (height - dock_h - 12 if dock_position == "BOTTOM" else (height - dock_h) / 2)
        _rounded_rectangle(context, dock_x, dock_y, dock_w, dock_h, 0 if dock_panel else 16)
        context.set_source_rgba(dock.red, dock.green, dock.blue, max(0, min(1, dock_opacity)))
        context.fill()
        available = dock_w if dock_position in {"TOP", "BOTTOM"} else dock_h
        icon_gap = max(6, (available - 32 - count * icon_size) / max(1, count - 1))
        icon_names = ("org.gnome.Nautilus", "web-browser", "org.gnome.Settings", "utilities-terminal", "view-app-grid", "user-trash")
        for index in range(max(1, count)):
            icon_x = dock_x + 16 + index * (icon_size + icon_gap) if dock_position in {"TOP", "BOTTOM"} else dock_x + (dock_w - icon_size) / 2
            icon_y = dock_y + (dock_h - icon_size) / 2 if dock_position in {"TOP", "BOTTOM"} else dock_y + 16 + index * (icon_size + icon_gap)
            icon = self._dock_icons.get(icon_names[index % len(icon_names)])
            if icon is not None:
                context.save()
                context.translate(icon_x, icon_y)
                context.scale(icon_size / icon.get_width(), icon_size / icon.get_height())
                Gdk.cairo_set_source_pixbuf(context, icon, 0, 0)
                context.paint_with_alpha(1 if index == 0 else .78)
                context.restore()
            else:
                context.set_source_rgba(accent.red, accent.green, accent.blue, 1 if index == 0 else .62)
                _rounded_rectangle(context, icon_x, icon_y, icon_size, icon_size, 7)
                context.fill()
        if dock_autohide:
            self._text(context, "Dock auto-hidden", dock_x + 12, dock_y - 8 if dock_position == "BOTTOM" else dock_y + dock_h + 16, 9, muted)

        blur = self._value("io.github.gnomecustomizer.shell", "overview-blur", 0)
        self._text(context, f"Live staged preview · accent {self._value('org.gnome.desktop.interface', 'accent-color', 'blue')} · blur {blur}", 18, height - 12, 11, muted)

    def _draw_login(self, context, width, height):
        resource = self.login_state.get("resource", {})
        background = _rgba(resource.get("background_color"), "#101820")
        panel = _rgba(resource.get("panel_color"), "#16161a")
        panel_end = _rgba(resource.get("panel_color2"), "#303044")
        text = _rgba(resource.get("panel_text_color"), "#ffffff")
        context.set_source_rgba(background.red, background.green, background.blue, 1)
        context.paint()
        self._paint_login_image(context, self._load_login_asset("wallpaper"), 0, 0, width, height)
        opacity = max(0.0, min(1.0, float(resource.get("panel_opacity", 1) or 1)))
        if resource.get("panel_gradient_enabled"):
            import cairo
            vertical = resource.get("panel_gradient_direction") == "vertical"
            pattern = cairo.LinearGradient(0, 0, 0, 42) if vertical else cairo.LinearGradient(0, 0, width, 0)
            pattern.add_color_stop_rgba(0, panel.red, panel.green, panel.blue, opacity)
            pattern.add_color_stop_rgba(1, panel_end.red, panel_end.green, panel_end.blue, opacity)
            context.set_source(pattern)
        else:
            context.set_source_rgba(panel.red, panel.green, panel.blue, opacity)
        context.rectangle(0, 0, width, 42)
        context.fill()
        interface = self.login_state.get("interface", {})
        clock_format = interface.get("clock-format", "24h")
        clock = "10:30 AM" if clock_format == "12h" else "10:30"
        if interface.get("clock-show-seconds"):
            clock = clock.replace(" AM", ":42 AM").replace("10:30", "10:30:42")
        clock_parts = [clock]
        if interface.get("clock-show-date", True):
            clock_parts.insert(0, "Aug 11")
        if interface.get("clock-show-weekday"):
            clock_parts.insert(0, "Tue")
        clock_text = "  ".join(clock_parts)
        self._text(context, clock_text, width / 2 - max(42, len(clock_text) * 3.5), 26, 12, (text.red, text.green, text.blue, 1), True)
        if interface.get("show-battery-percentage"):
            self._text(context, "Battery 82%", width - 82, 26, 10, (text.red, text.green, text.blue, 1))
        card_w, card_h = min(300, width * .56), 190
        card_x, card_y = (width - card_w) / 2, (height - card_h) / 2
        card = _rgba("#ffffff", "#ffffff")
        _rounded_rectangle(context, card_x, card_y, card_w, card_h, float(resource.get("panel_radius", 12)))
        context.set_source_rgba(card.red, card.green, card.blue, .96)
        context.fill()
        accent_value = self.login_state.get("accent", "blue")
        accent = _rgba(ACCENT_COLORS.get(str(accent_value), accent_value), "#3584e4")
        logo = self._load_login_asset("logo")
        if logo is not None:
            self._paint_login_image(context, logo, width / 2 - 34, card_y + 12, 68, 52, contain=True)
        else:
            context.set_source_rgba(accent.red, accent.green, accent.blue, 1)
            context.arc(width / 2, card_y + 38, 22, 0, 6.2832)
            context.fill()
        banner = self.login_state.get("banner") or "Welcome"
        self._text(context, banner, width / 2 - min(80, len(str(banner)) * 3.5), card_y + 94, 16, (.16, .16, .18, 1), True)
        context.set_source_rgba(.88, .88, .9, 1)
        _rounded_rectangle(context, card_x + 28, card_y + 118, card_w - 56, 32, 8)
        context.fill()
        self._text(context, "Password", card_x + 42, card_y + 139, 12, (.45, .45, .48, 1))
        self._text(context, "Visual approximation — login changes need logout or reboot", 18, height - 12, 11, (.72, .72, .75, 1))


class LivePreviewPanel(Gtk.Box):
    """Embedded preview for staged settings; it never opens another window."""

    def __init__(self, settings, changes, login_state, capture_desktop=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, hexpand=True, vexpand=True)
        self.add_css_class("preview-panel")
        self.settings = settings
        self.changes = changes
        self.login_state = login_state
        self.capture_desktop = capture_desktop
        self.mode = "desktop"
        self._listener = self._refresh
        self.changes.listeners.append(self._listener)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, css_classes=["preview-toolbar"])
        toolbar_top = Gtk.Box(spacing=10)
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        title_box.append(Gtk.Label(label="Live preview", xalign=0, css_classes=["preview-toolbar-title"]))
        title_box.append(Gtk.Label(label="See your staged changes before you apply them", xalign=0, css_classes=["preview-toolbar-subtitle"]))
        toolbar_top.append(title_box)
        if capture_desktop:
            capture = Gtk.Button(label="Capture", icon_name="camera-photo-symbolic", tooltip_text="Use the actual current desktop as the preview baseline", css_classes=["flat", "preview-capture"])
            capture.connect("clicked", lambda *_: capture_desktop())
            toolbar_top.append(capture)
        self.info = Gtk.Label(css_classes=["status-pill"], halign=Gtk.Align.END)
        self.info.set_hexpand(True)
        toolbar_top.append(self.info)
        toolbar.append(toolbar_top)
        self.append(toolbar)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, hexpand=True, vexpand=True, css_classes=["preview-stage"])
        self.append(body)
        self.canvas = PreviewCanvas(settings, changes, content_width=360, content_height=300)
        self.canvas.add_css_class("preview-canvas")
        desktop_frame = Gtk.Frame(css_classes=["preview-frame"])
        desktop_frame.set_child(self.canvas)
        body.append(desktop_frame)

        changes_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, height_request=250, vexpand=True, css_classes=["preview-inspector"])
        heading = Gtk.Label(label="Changes staged", xalign=0, css_classes=["preview-inspector-title"])
        changes_box.append(heading)
        self.change_count = Gtk.Label(xalign=0, css_classes=["dim-label"])
        changes_box.append(self.change_count)
        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.change_list = Gtk.ListBox(css_classes=["preview-list"], selection_mode=Gtk.SelectionMode.NONE)
        scroll.set_child(self.change_list)
        changes_box.append(scroll)
        body.append(changes_box)
        self._refresh()

    def set_mode(self, mode):
        mode = "login" if mode == "login" else "desktop"
        if self.mode == mode:
            self._refresh()
            return
        self.mode = mode
        self._refresh()

    @staticmethod
    def _format_value(value):
        if isinstance(value, bool):
            return "On" if value else "Off"
        if isinstance(value, (list, tuple)):
            return ", ".join(str(item) for item in value) or "None"
        if isinstance(value, float):
            return f"{value:.2f}".rstrip("0").rstrip(".")
        text = str(value)
        return text if len(text) < 100 else text[:97] + "…"

    @staticmethod
    def _label(schema, key):
        return key.replace("-", " ").replace("_", " ").strip().capitalize()

    @staticmethod
    def _target(schema, key):
        if schema in {"resource", "asset"} or schema.startswith("org.gnome.login-screen"):
            return "Login screen"
        if schema == "org.gnome.desktop.background":
            return "Wallpaper"
        if schema == "org.gnome.shell.extensions.dash-to-dock":
            return "Dock"
        if schema == "io.github.gnomecustomizer.shell":
            if key.startswith("panel-") or key in {"activities-button-enabled"}:
                return "Top Bar"
            if key.startswith("overview-") or key.startswith("folder-"):
                return "Overview"
            if key.startswith("menu-"):
                return "Menus"
            return "Shell"
        if schema.startswith("org.gnome.shell.extensions.blur-my-shell"):
            return schema.rsplit(".", 1)[-1].replace("-", " ").title()
        if schema == "org.gnome.desktop.interface":
            return "Desktop appearance"
        return "Desktop settings"

    def _change_subtitle(self, schema, key, value):
        staged = self._format_value(value)
        if schema in {"resource", "asset"}:
            return f"Staged: {staged}"
        try:
            current = self.settings.get(schema, key)
        except Exception:
            return f"Staged: {staged}"
        return f"Current: {self._format_value(current)}  →  Staged: {staged}"

    def _control_snapshot(self, value):
        """Return a real-looking, read-only control for the staged value."""
        if isinstance(value, bool):
            control = Gtk.Switch(active=value, valign=Gtk.Align.CENTER)
            control.set_sensitive(False)
            return control
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            adjustment = Gtk.Adjustment(value=float(value), lower=-100000, upper=100000, step_increment=1, page_increment=10)
            control = Gtk.SpinButton(adjustment=adjustment, digits=2 if isinstance(value, float) else 0, width_request=86, valign=Gtk.Align.CENTER)
            control.set_sensitive(False)
            return control
        text = self._format_value(value)
        if isinstance(value, str) and (text.startswith("#") or text.startswith("file:")):
            label = Gtk.Label(label=text, css_classes=["preview-value"], valign=Gtk.Align.CENTER)
            label.set_max_width_chars(18)
            label.set_ellipsize(3)  # Pango.EllipsizeMode.END without another import.
            return label
        label = Gtk.Label(label=text, css_classes=["preview-value"], valign=Gtk.Align.CENTER)
        label.set_max_width_chars(16)
        label.set_ellipsize(3)
        return label

    def _pending_items(self):
        items = [(change.label, change.schema, change.key, change.value) for change in self.changes.pending.values()]
        state = self.login_state()
        for schema, values in state.get("gdm_pending", {}).items():
            for key, value in values.items():
                items.append((f"Login screen · {self._label(schema, key)}", schema, key, value))
        for key, value in state.get("gdm_resource", {}).items():
            items.append((f"Login screen · {self._label('', key)}", "resource", key, value))
        for role in state.get("gdm_assets", {}):
            items.append((f"Login screen · {role.capitalize()}", "asset", role, "New image selected"))
        if state.get("monitor_pending"):
            items.append(("Login screen · Display layout", "resource", "monitors", "Current monitor layout"))
        return items

    def _refresh(self):
        items = self._pending_items()
        self.change_count.set_label(f"{len(items)} change{'s' if len(items) != 1 else ''} staged · nothing written yet")
        while child := self.change_list.get_first_child():
            self.change_list.remove(child)
        if not items:
            empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
            empty_icon = Gtk.Image.new_from_icon_name("document-edit-symbolic")
            empty_icon.add_css_class("empty-state-icon")
            empty.append(empty_icon)
            empty.append(Gtk.Label(label="Nothing staged yet", css_classes=["preview-empty"]))
            empty.append(Gtk.Label(label="Change a setting to see it appear here.", css_classes=["preview-toolbar-subtitle"]))
            self.change_list.append(empty)
        else:
            for label, schema, key, value in items:
                target = self._target(schema, key)
                row = Adw.ActionRow(title=f"{target} · {label}", subtitle=self._change_subtitle(schema, key, value))
                row.set_tooltip_text(f"{schema}:{key}")
                row.add_suffix(self._control_snapshot(value))
                self.change_list.append(row)
        state = self.login_state()
        self.canvas.update(self.mode, state)
        self.info.set_label("Live" if self.mode == "desktop" else "Preview")


class LivePreviewWindow(Gtk.Window):
    """A separate, resizable preview window sharing the live staged state."""

    def __init__(self, parent, settings, changes, login_state):
        # Keep this a normal application window, rather than a transient or
        # modal child. The editor must remain reachable while the preview is
        # visible so controls can be changed and observed side by side.
        super().__init__(application=parent.get_application(), title="GNOME Customizer · Live Preview", default_width=720, default_height=680)
        self.set_modal(False)
        self.set_resizable(True)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        header = Adw.HeaderBar()
        controls = Gtk.Button(label="Show Controls", icon_name="go-previous-symbolic", tooltip_text="Return to the settings controls")
        controls.connect("clicked", lambda *_: parent.present())
        header.pack_start(controls)
        root.append(header)
        self.panel = LivePreviewPanel(settings, changes, login_state)
        root.append(self.panel)
        self.set_child(root)

    def refresh(self):
        self.panel._refresh()
