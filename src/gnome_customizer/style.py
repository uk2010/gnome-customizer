from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk


APP_CSS = """
/* GNOME Customizer's own chrome stays intentionally restrained so the
 * settings it previews remain the visual focus. */
.gnome-customizer-window {
  background: @window_bg_color;
}

.gnome-customizer-window > box {
  background: @window_bg_color;
}

.gnome-customizer-headerbar {
  padding: 4px 8px;
}

.gnome-customizer-headerbar .mode-switcher {
  min-width: 280px;
}

.navigation-sidebar {
  padding: 8px 4px;
}

.navigation-search {
  margin: 0 4px 4px;
}

.navigation-sidebar > row {
  min-height: 42px;
  margin: 2px 0;
  padding: 0 12px;
  border-radius: 10px;
  color: alpha(@window_fg_color, .78);
}

.navigation-sidebar > row:hover {
  background: alpha(@window_fg_color, .06);
}

.navigation-sidebar > row:selected {
  background: alpha(@accent_bg_color, .16);
  color: @accent_color;
  font-weight: 600;
}

.navigation-sidebar > row:selected image {
  color: @accent_color;
}

.navigation-empty {
  padding: 18px 8px;
  color: alpha(@window_fg_color, .55);
}

.editor-pane {
  background: @view_bg_color;
}

.editor-pane > * {
  background: transparent;
}

.editor-pane .preferences-page {
  background: transparent;
}

.editor-pane .preferences-group {
  margin: 16px 0;
}

.editor-pane .preferences-group > label {
  margin: 0 4px 8px;
  color: alpha(@window_fg_color, .72);
  font-weight: 700;
}

.editor-pane .preferences-group > box {
  background: @card_bg_color;
  border: 1px solid alpha(@window_fg_color, .08);
  border-radius: 14px;
  box-shadow: 0 4px 18px alpha(#000000, .06);
}

.editor-pane .preferences-group row {
  min-height: 54px;
}

.editor-pane .preferences-group row + row {
  border-top: 1px solid alpha(@window_fg_color, .06);
}

.editor-pane .preferences-group row:hover {
  background: alpha(@window_fg_color, .035);
}

.editor-pane .preferences-group row:active,
.editor-pane .preferences-group row:selected {
  background: alpha(@accent_bg_color, .08);
}

.editor-scroll {
  padding: 10px 18px 26px;
}

.editor-scroll > viewport {
  background: transparent;
}

.preview-pane {
  min-width: 440px;
  background: alpha(@headerbar_bg_color, .65);
  border-left: 1px solid alpha(@window_fg_color, .08);
}

.preview-toolbar {
  padding: 12px 14px 10px;
  border-bottom: 1px solid alpha(@window_fg_color, .08);
}

.preview-toolbar-title {
  font-weight: 700;
}

.preview-toolbar-subtitle {
  color: alpha(@window_fg_color, .62);
  font-size: 0.9em;
}

.preview-stage {
  padding: 14px;
}

.preview-frame,
.preview-inspector {
  border: 1px solid alpha(@window_fg_color, .10);
  border-radius: 14px;
  background: alpha(@card_bg_color, .72);
  box-shadow: 0 8px 26px alpha(#000000, .12);
}

.preview-frame {
  padding: 4px;
}

.preview-canvas {
  border-radius: 11px;
}

.preview-inspector {
  padding: 14px;
}

.preview-inspector-title {
  font-weight: 700;
  font-size: 1.05em;
}

.preview-inspector-count {
  color: alpha(@window_fg_color, .62);
  font-size: 0.88em;
}

.preview-empty {
  color: alpha(@window_fg_color, .62);
  padding: 18px 10px;
}

.preview-list row {
  padding: 8px 0;
  border-bottom: 1px solid alpha(@window_fg_color, .06);
}

.preview-list row:last-child {
  border-bottom: none;
}

.preview-value {
  padding: 4px 8px;
  border-radius: 7px;
  background: alpha(@window_fg_color, .07);
  color: alpha(@window_fg_color, .76);
  font-size: 0.86em;
}

.status-pill {
  padding: 4px 9px;
  border-radius: 999px;
  background: alpha(@accent_bg_color, .14);
  color: @accent_color;
  font-size: 0.82em;
  font-weight: 600;
}

.action-bar {
  padding: 10px 16px 12px;
  border-top: 1px solid alpha(@window_fg_color, .08);
  background: alpha(@headerbar_bg_color, .8);
}

.pending-label {
  color: alpha(@window_fg_color, .68);
}

.empty-state-icon {
  color: alpha(@window_fg_color, .45);
}
"""

_installed_display = None


def install() -> None:
    global _installed_display
    display = Gdk.Display.get_default()
    if display is None or display is _installed_display:
        return
    provider = Gtk.CssProvider()
    provider.load_from_data(APP_CSS.encode("utf-8"))
    Gtk.StyleContext.add_provider_for_display(
        display,
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
    _installed_display = display
