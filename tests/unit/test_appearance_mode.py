import unittest
from pathlib import Path

from gnome_customizer.backend.settings import SettingsBackend


class AppearanceModeTests(unittest.TestCase):
    def test_color_scheme_does_not_stage_competing_gtk_or_icon_themes(self):
        source=(Path(__file__).parents[2]/"src/gnome_customizer/window.py").read_text()
        self.assertNotIn("_stage_color_scheme",source)
        self.assertNotIn("app_theme.apply",source)
        self.assertNotIn("application_theme_pending",source)

    def test_legacy_implicit_shell_surface_is_migrated_to_opt_in(self):
        source=(Path(__file__).parents[2]/"src/gnome_customizer/window.py").read_text()
        self.assertIn('self.settings.set(schema,"overview-enabled",False)',source)
        self.assertIn('"panel":"panel-enabled"',source)
        self.assertIn('"menus":"menu-enabled"',source)

    def test_legacy_dark_yaru_names_are_unpinned_in_light_mode(self):
        source=(Path(__file__).parents[2]/"src/gnome_customizer/window.py").read_text()
        self.assertIn('marker="native_theme_ownership_v1"',source)
        self.assertIn('current.endswith("-dark")',source)

    def test_ubuntu_wallpaper_defaults_are_real_image_uris(self):
        backend=SettingsBackend()
        self.assertEqual(backend.reset_value("org.gnome.desktop.background","picture-uri"),"file:///usr/share/backgrounds/warty-final-ubuntu.png")
        self.assertEqual(backend.reset_value("org.gnome.desktop.background","picture-uri-dark"),"file:///usr/share/backgrounds/ubuntu-wallpaper-d.png")


if __name__ == "__main__":
    unittest.main()
