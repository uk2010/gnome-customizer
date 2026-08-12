import unittest
from pathlib import Path

from gnome_customizer.backend.settings import SettingsBackend, neutral_yaru_theme


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

    def test_legacy_yaru_accent_variants_are_unpinned_for_native_accent(self):
        source=(Path(__file__).parents[2]/"src/gnome_customizer/window.py").read_text()
        self.assertIn('marker="native_accent_ownership_v2"',source)
        self.assertEqual(neutral_yaru_theme("Yaru-blue-dark",True),"Yaru-dark")
        self.assertEqual(neutral_yaru_theme("Yaru-red",False),"Yaru")
        self.assertEqual(neutral_yaru_theme("Yaru-wartybrown-dark",False),"Yaru")
        self.assertEqual(neutral_yaru_theme("Yaru-dark",True),"Yaru-dark")
        self.assertEqual(neutral_yaru_theme("Adwaita-dark",True),"Adwaita-dark")

    def test_accent_control_uses_only_gnome_50_native_setting(self):
        source=(Path(__file__).parents[2]/"src/gnome_customizer/pages/preferences.py").read_text()
        accent_line=next(line for line in source.splitlines() if 'self.combo(g,"Accent Color"' in line)
        self.assertIn('"org.gnome.desktop.interface","accent-color"',accent_line)
        self.assertNotIn("gtk-theme",accent_line)
        self.assertNotIn("icon-theme",accent_line)

    def test_ubuntu_wallpaper_defaults_are_real_image_uris(self):
        backend=SettingsBackend()
        self.assertEqual(backend.reset_value("org.gnome.desktop.background","picture-uri"),"file:///usr/share/backgrounds/warty-final-ubuntu.png")
        self.assertEqual(backend.reset_value("org.gnome.desktop.background","picture-uri-dark"),"file:///usr/share/backgrounds/ubuntu-wallpaper-d.png")


if __name__ == "__main__":
    unittest.main()
