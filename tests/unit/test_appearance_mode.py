import unittest
from pathlib import Path

from gnome_customizer.backend.settings import SettingsBackend, yaru_theme_for_accent


class AppearanceModeTests(unittest.TestCase):
    def test_color_scheme_has_no_old_application_theme_override(self):
        source=(Path(__file__).parents[2]/"src/gnome_customizer/window.py").read_text()
        self.assertNotIn("_stage_color_scheme",source)
        self.assertNotIn("app_theme.apply",source)
        self.assertNotIn("application_theme_pending",source)

    def test_legacy_implicit_shell_surface_is_migrated_to_opt_in(self):
        source=(Path(__file__).parents[2]/"src/gnome_customizer/window.py").read_text()
        self.assertIn('self.settings.set(schema,"overview-enabled",False)',source)
        self.assertIn('"panel":"panel-enabled"',source)
        self.assertIn('"menus":"menu-enabled"',source)

    def test_gnome_50_yaru_accent_mapping_in_light_and_dark(self):
        source=(Path(__file__).parents[2]/"src/gnome_customizer/window.py").read_text()
        self.assertIn('marker="native_accent_ownership_v3"',source)
        expected={"blue":"blue","teal":"prussiangreen","green":"olive","yellow":"yellow","orange":None,"red":"red","pink":"magenta","purple":"purple","slate":"sage","brown":"wartybrown"}
        for accent,suffix in expected.items():
            base="Yaru"+(f"-{suffix}" if suffix else "")
            self.assertEqual(yaru_theme_for_accent(accent,False),base)
            self.assertEqual(yaru_theme_for_accent(accent,True),base+"-dark")

    def test_accent_control_uses_gnome_50_native_setting(self):
        source=(Path(__file__).parents[2]/"src/gnome_customizer/pages/preferences.py").read_text()
        accent_line=next(line for line in source.splitlines() if 'self.combo(g,"Accent Color"' in line)
        self.assertIn('"org.gnome.desktop.interface","accent-color"',accent_line)

    def test_ubuntu_wallpaper_defaults_are_real_image_uris(self):
        backend=SettingsBackend()
        self.assertEqual(backend.reset_value("org.gnome.desktop.background","picture-uri"),"file:///usr/share/backgrounds/warty-final-ubuntu.png")
        self.assertEqual(backend.reset_value("org.gnome.desktop.background","picture-uri-dark"),"file:///usr/share/backgrounds/ubuntu-wallpaper-d.png")


if __name__ == "__main__":
    unittest.main()
