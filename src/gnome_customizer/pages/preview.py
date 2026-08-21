from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk


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
        self.set_draw_func(self._draw)

    def update(self, mode, login_state):
        self.mode = mode
        self.login_state = login_state or {}
        self.queue_draw()

    def _value(self, schema, key, fallback=None):
        pending = self.changes.pending.get((schema, key))
        if pending is not None:
            return pending.value
        try:
            return self.settings.get(schema, key)
        except Exception:
            return fallback

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

    def _draw_desktop(self, context, width, height):
        dark = self._value("org.gnome.desktop.interface", "color-scheme", "default") == "prefer-dark"
        background = _rgba(self._value("org.gnome.desktop.background", "primary-color", None), "#202124" if dark else "#d9e2f3")
        panel = _rgba(self._value("io.github.gnomecustomizer.shell", "panel-color", None), "#282828" if dark else "#f8f8f8")
        accent = _rgba(self._value("org.gnome.desktop.interface", "accent-color", None), "#78aeed")
        text = (0.95, 0.95, 0.95, 1) if dark else (0.12, 0.12, 0.14, 1)
        muted = (0.72, 0.72, 0.75, 1) if dark else (0.34, 0.36, 0.4, 1)

        context.set_source_rgba(background.red, background.green, background.blue, 1)
        context.paint()

        panel_opacity = float(self._value("io.github.gnomecustomizer.shell", "panel-opacity", 1) or 1)
        context.set_source_rgba(panel.red, panel.green, panel.blue, max(0.1, min(1, panel_opacity)))
        context.rectangle(0, 0, width, 42)
        context.fill()
        self._text(context, "Activities", 18, 26, 13, text, True)
        clock_parts = ["Tue 10:30"]
        if self._value("org.gnome.desktop.interface", "clock-show-date", True):
            clock_parts.insert(0, "Aug 11")
        self._text(context, "  ".join(clock_parts), width / 2 - 30, 26, 12, text)
        self._text(context, "Wi-Fi   82%", width - 90, 26, 11, muted)

        # A small set of windows makes changes to scaling, accent, and surfaces easy to see.
        for index, (x, y, w, h) in enumerate(((width * .18, height * .22, width * .64, height * .45),
                                               (width * .08, height * .32, width * .28, height * .25))):
            surface = _rgba("#30343b" if dark else "#ffffff", "#ffffff")
            _rounded_rectangle(context, x, y, w, h, 14)
            context.set_source_rgba(surface.red, surface.green, surface.blue, .94)
            context.fill()
            context.set_source_rgba(accent.red, accent.green, accent.blue, .9)
            context.rectangle(x, y, w, 7)
            context.fill()
            self._text(context, "GNOME Customizer" if index == 0 else "Files", x + 18, y + 34, 14, text, True)
            self._text(context, "Preview of your staged appearance", x + 18, y + 62, 11, muted)
            context.set_source_rgba(accent.red, accent.green, accent.blue, .22)
            _rounded_rectangle(context, x + 18, y + 84, min(w - 36, 190), 24, 8)
            context.fill()

        dock_position = self._value("org.gnome.shell.extensions.dash-to-dock", "dock-position", "BOTTOM")
        dock = _rgba(self._value("org.gnome.shell.extensions.dash-to-dock", "background-color", None), "#1d1f24")
        dock_w, dock_h = (width * .48, 54) if dock_position in {"TOP", "BOTTOM"} else (62, height * .44)
        dock_x = (width - dock_w) / 2 if dock_position in {"TOP", "BOTTOM"} else (8 if dock_position == "LEFT" else width - dock_w - 8)
        dock_y = 50 if dock_position == "TOP" else (height - dock_h - 12 if dock_position == "BOTTOM" else (height - dock_h) / 2)
        _rounded_rectangle(context, dock_x, dock_y, dock_w, dock_h, 16)
        context.set_source_rgba(dock.red, dock.green, dock.blue, .92)
        context.fill()
        for index in range(5):
            icon_x = dock_x + 16 + index * 38 if dock_position in {"TOP", "BOTTOM"} else dock_x + 18
            icon_y = dock_y + 12 if dock_position in {"TOP", "BOTTOM"} else dock_y + 16 + index * 38
            context.set_source_rgba(accent.red, accent.green, accent.blue, 1 if index == 0 else .62)
            _rounded_rectangle(context, icon_x, icon_y, 26, 26, 7)
            context.fill()

        self._text(context, "Visual approximation — changes remain staged until Apply", 18, height - 12, 11, muted)

    def _draw_login(self, context, width, height):
        resource = self.login_state.get("resource", {})
        background = _rgba(resource.get("background_color"), "#101820")
        panel = _rgba(resource.get("panel_color"), "#16161a")
        panel_end = _rgba(resource.get("panel_color2"), "#303044")
        text = _rgba(resource.get("panel_text_color"), "#ffffff")
        context.set_source_rgba(background.red, background.green, background.blue, 1)
        context.paint()
        if resource.get("panel_gradient_enabled"):
            # Keep the preview dependency-free: the real GResource applies the
            # gradient, while this still communicates both endpoint colors.
            context.set_source_rgba(panel.red, panel.green, panel.blue, float(resource.get("panel_opacity", 1)))
        else:
            context.set_source_rgba(panel.red, panel.green, panel.blue, float(resource.get("panel_opacity", 1)))
        context.rectangle(0, 0, width, 42)
        context.fill()
        self._text(context, "Aug 11   10:30", width / 2 - 42, 26, 12, (text.red, text.green, text.blue, 1), True)
        card_w, card_h = min(300, width * .56), 190
        card_x, card_y = (width - card_w) / 2, (height - card_h) / 2
        card = _rgba("#ffffff", "#ffffff")
        _rounded_rectangle(context, card_x, card_y, card_w, card_h, float(resource.get("panel_radius", 12)))
        context.set_source_rgba(card.red, card.green, card.blue, .96)
        context.fill()
        accent = _rgba(self.login_state.get("accent"), "#3584e4")
        context.set_source_rgba(accent.red, accent.green, accent.blue, 1)
        context.arc(width / 2, card_y + 48, 22, 0, 6.2832)
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

    def __init__(self, settings, changes, login_state):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8, hexpand=True, vexpand=True)
        self.settings = settings
        self.changes = changes
        self.login_state = login_state
        self.mode = "desktop"
        self._listener = self._refresh
        self.changes.listeners.append(self._listener)

        toolbar = Gtk.Box(spacing=8)
        switcher = Gtk.StackSwitcher()
        self.mode_stack = Gtk.Stack()
        switcher.set_stack(self.mode_stack)
        toolbar.append(switcher)
        self.info = Gtk.Label(css_classes=["dim-label"])
        toolbar.append(self.info)
        self.append(toolbar)

        body = Gtk.Box(spacing=12, hexpand=True, vexpand=True)
        self.append(body)
        self.canvas = PreviewCanvas(settings, changes, content_width=360, content_height=300)
        self.mode_stack.add_titled(self.canvas, "desktop", "Desktop")
        login_canvas = PreviewCanvas(settings, changes, content_width=360, content_height=300)
        login_canvas.mode = "login"
        self.login_canvas = login_canvas
        self.mode_stack.add_titled(login_canvas, "login", "Login screen")
        self.mode_stack.connect("notify::visible-child-name", self._mode_changed)
        body.append(self.mode_stack)

        changes_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, width_request=210)
        heading = Gtk.Label(label="Pending changes", xalign=0, css_classes=["title-3"])
        changes_box.append(heading)
        self.change_count = Gtk.Label(xalign=0, css_classes=["dim-label"])
        changes_box.append(self.change_count)
        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.change_list = Gtk.ListBox(css_classes=["boxed-list"], selection_mode=Gtk.SelectionMode.NONE)
        scroll.set_child(self.change_list)
        changes_box.append(scroll)
        body.append(changes_box)
        self._refresh()

    def _mode_changed(self, *_):
        self.mode = self.mode_stack.get_visible_child_name() or "desktop"
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
            self.change_list.append(Gtk.Label(label="Change a setting to see exactly what will be applied here.", wrap=True, xalign=0, margin_top=12, margin_bottom=12, margin_start=12, margin_end=12))
        else:
            for label, schema, key, value in items:
                row = Adw.ActionRow(title=label, subtitle=self._format_value(value))
                row.set_tooltip_text(f"{schema}:{key}")
                self.change_list.append(row)
        state = self.login_state()
        self.canvas.update(self.mode, state)
        self.login_canvas.update("login", state)
        self.info.set_label("Live · staged only")
