import unittest

import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GdkPixbuf", "2.0")

from gnome_customizer.pages.preview import PreviewCanvas


class _Settings:
    def get(self, *_args):
        raise KeyError


class _Changes:
    pending = {}


def _canvas():
    # DrawingArea construction needs a live display.  The render callback
    # itself is display-independent, so exercise it with a Cairo surface.
    canvas = PreviewCanvas.__new__(PreviewCanvas)
    canvas.settings = _Settings()
    canvas.changes = _Changes()
    canvas.mode = "desktop"
    canvas.login_state = {}
    canvas._wallpaper_uri = None
    canvas._wallpaper = None
    canvas._login_asset_cache = {}
    canvas._dock_icons = {}
    canvas._last_draw_error = None
    return canvas


class PreviewTests(unittest.TestCase):
    def test_desktop_and_login_callbacks_render_without_a_display(self):
        canvas = _canvas()
        for mode in ("desktop", "login"):
            canvas.mode = mode
            surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 360, 300)
            canvas._draw(None, cairo.Context(surface), 360, 300)
            self.assertIsNone(canvas._last_draw_error)

    def test_callback_falls_back_instead_of_leaving_a_blank_preview(self):
        canvas = _canvas()
        canvas._draw_desktop = lambda *_args: (_ for _ in ()).throw(RuntimeError("renderer failure"))
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 360, 300)
        canvas._draw(None, cairo.Context(surface), 360, 300)
        self.assertIn("RuntimeError", canvas._last_draw_error)


if __name__ == "__main__":
    unittest.main()
