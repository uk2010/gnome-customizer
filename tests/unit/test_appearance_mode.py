import unittest
from pathlib import Path

from gnome_customizer.backend.settings import SettingsBackend, yaru_theme_for_accent
from gnome_customizer.backend.themes import SHELL_SURFACE_SETTINGS

ROOT=Path(__file__).parents[2]


class AppearanceModeTests(unittest.TestCase):
    def test_native_window_and_desktop_icon_placement_controls_are_exposed(self):
        preferences=(ROOT/"src/gnome_customizer/pages/preferences.py").read_text()
        window=(ROOT/"src/gnome_customizer/window.py").read_text()
        self.assertIn('"Always Center New Windows","org.gnome.mutter","center-new-windows"',preferences)
        self.assertIn('schema="org.gnome.shell.extensions.ding"',preferences)
        self.assertIn('"Starting Corner",schema,"start-corner"',preferences)
        for corner in ("top-left","top-right","bottom-left","bottom-right"):
            self.assertIn(f'"{corner}"',preferences)
        self.assertIn('(\"placement\",\"Placement\",\"view-grid-symbolic\")',window)
        self.assertIn('self._add("placement",self.factory.placement())',window)

    def test_color_scheme_has_no_old_application_theme_override(self):
        source=(Path(__file__).parents[2]/"src/gnome_customizer/window.py").read_text()
        self.assertNotIn("_stage_color_scheme",source)
        self.assertNotIn("app_theme.apply",source)
        self.assertNotIn("application_theme_pending",source)

    def test_legacy_implicit_shell_surface_is_migrated_to_opt_in(self):
        source=(Path(__file__).parents[2]/"src/gnome_customizer/window.py").read_text()
        self.assertIn('self.settings.set(schema,"overview-enabled",False)',source)
        self.assertEqual(SHELL_SURFACE_SETTINGS["panel"]["enabled"],"panel-enabled")
        self.assertEqual(SHELL_SURFACE_SETTINGS["menus"]["enabled"],"menu-enabled")

    def test_shell_extensions_are_repaired_without_opening_the_window(self):
        entrypoint=(Path(__file__).parents[2]/"src/gnome_customizer/__main__.py").read_text()
        autostart=(Path(__file__).parents[2]/"data/autostart/io.github.gnomecustomizer-extensions.desktop").read_text()
        settings=(Path(__file__).parents[2]/"src/gnome_customizer/backend/settings.py").read_text()
        self.assertIn('"--ensure-extensions"',entrypoint)
        self.assertIn('Exec=gnome-customizer --ensure-extensions',autostart)
        self.assertIn('or global_extensions_disabled',settings)

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
        light=backend.reset_value("org.gnome.desktop.background","picture-uri")
        dark=backend.reset_value("org.gnome.desktop.background","picture-uri-dark")
        if Path("/usr/share/themes/Yaru").is_dir():
            self.assertEqual(light,"file:///usr/share/backgrounds/warty-final-ubuntu.png")
            self.assertEqual(dark,"file:///usr/share/backgrounds/ubuntu-wallpaper-d.png")
        else:
            self.assertEqual(light,backend.default("org.gnome.desktop.background","picture-uri"))
            self.assertEqual(dark,backend.default("org.gnome.desktop.background","picture-uri-dark"))

    def test_theme_apply_refreshes_wallpaper_names_and_saves_complete_login_state(self):
        source=(ROOT/"src/gnome_customizer/window.py").read_text()
        self.assertIn('self.desktop_wallpaper_rows[key].set_subtitle(source.name)',source)
        self.assertIn('transaction["settings"]=self.factory.gdm_settings()',source)
        self.assertIn('transaction["monitor_default"]=True',source)

    def test_login_display_layout_is_applied_directly(self):
        source=(ROOT/"src/gnome_customizer/window.py").read_text()
        self.assertIn('Gtk.Button(label="Apply"',source)
        self.assertIn('self.helper.call("ApplyMonitorConfiguration",{"xml":xml})',source)
        self.assertIn('result.get("sha256")!=hashlib.sha256(xml.encode()).hexdigest()',source)
        self.assertNotIn('Gtk.Button(label="Stage"',source)


if __name__ == "__main__":
    unittest.main()
