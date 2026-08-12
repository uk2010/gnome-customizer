import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ShellExtensionTests(unittest.TestCase):
    def test_companion_does_not_create_or_suppress_a_dock(self):
        extension = (ROOT / "shell/extension.js").read_text()
        stylesheet = (ROOT / "shell/stylesheet.css").read_text()
        schema = (ROOT / "shell/schemas/io.github.gnomecustomizer.shell.gschema.xml").read_text()
        for legacy in ("class Dock", "gnome-customizer-dock", "dashtodockContainer", "_syncExternalDocks", "dock-enabled"):
            self.assertNotIn(legacy, extension)
        self.assertNotIn("gnome-customizer-dock", stylesheet)
        self.assertNotIn("dock-enabled", schema)

    def test_dock_page_uses_native_dash_to_dock_settings(self):
        preferences = (ROOT / "src/gnome_customizer/pages/preferences.py").read_text()
        self.assertIn('schema="org.gnome.shell.extensions.dash-to-dock"', preferences)
        for key in ("dock-position", "dash-max-icon-size", "show-favorites", "show-running", "show-show-apps-button", "dock-fixed", "autohide", "intellihide", "background-opacity"):
            self.assertIn(f'"{key}"', preferences)
        self.assertNotIn('"Enable Custom Dock"', preferences)

    def test_panel_background_survives_the_overview_pseudo_state(self):
        extension=(ROOT/"shell/extension.js").read_text();stylesheet=(ROOT/"shell/stylesheet.css").read_text()
        self.assertIn("name:'gnome-customizer-panel-background'",extension)
        self.assertIn("Main.panel.insert_child_at_index(this._panelBackground,0)",extension)
        self.assertNotIn("Main.layoutManager.panelBox.insert_child_at_index(this._panelBackground,0)",extension)
        self.assertIn("backgroundStyle(this._settings, 'panel', opacity)",extension)
        self.assertIn("Main.panel.set_style(`background-color: transparent; color: ${text};`)",extension)
        self.assertIn("Main.panel.add_style_class_name('gnome-customizer-panel')",extension)
        self.assertIn("#panel.gnome-customizer-panel { background-color: transparent; }",stylesheet)
        self.assertNotIn("this._blur(Main.panel, 'gnome-customizer-panel-blur'",extension)

    def test_panel_style_is_restored_after_overview_clears_it(self):
        extension=(ROOT/"shell/extension.js").read_text()
        self.assertIn("Main.overview.connect('hidden', () => this._queuePanelStyleRestore())",extension)
        self.assertIn("GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE",extension)
        self.assertIn("Main.overview.disconnect(this._overviewHidden)",extension)
        self.assertIn("GLib.Source.remove(this._panelRestoreSource)",extension)

    def test_overview_uses_blurred_wallpaper_backgrounds(self):
        extension = (ROOT / "shell/extension.js").read_text()
        schema = (ROOT / "shell/schemas/io.github.gnomecustomizer.shell.gschema.xml").read_text()
        self.assertIn("new Meta.BackgroundGroup", extension)
        self.assertIn("new Background.BackgroundManager", extension)
        self.assertIn("mode:Shell.BlurMode.ACTOR", extension)
        self.assertIn("Main.layoutManager.overviewGroup.set_style(enabled ? 'background-color: transparent;'", extension)
        self.assertIn("y:monitor.y+0.5,z_position:1", extension)
        self.assertIn("radius:sigma*scale", extension)
        self.assertIn("Main.overview.connect('showing', () => this._lowerOverviewBackground())", extension)
        for key in ("overview-enabled", "overview-opacity", "overview-brightness", "overview-saturation"):
            self.assertIn(key, schema)

    def test_unenabled_surfaces_leave_gnome_shell_in_control(self):
        extension=(ROOT/"shell/extension.js").read_text();schema=(ROOT/"shell/schemas/io.github.gnomecustomizer.shell.gschema.xml").read_text()
        self.assertIn('<key name="panel-enabled" type="b"><default>false</default></key>',schema)
        self.assertIn('<key name="menu-enabled" type="b"><default>false</default></key>',schema)
        self.assertIn('<key name="overview-enabled" type="b"><default>false</default></key>',schema)
        self.assertIn("get_boolean('panel-enabled')",extension);self.assertIn("get_boolean('menu-enabled')",extension)
        self.assertIn("Main.layoutManager.overviewGroup.set_style(enabled ? 'background-color: transparent;' : this._overviewStyle)",extension)

    def test_surface_opacity_is_applied_to_background_alpha(self):
        extension = (ROOT / "shell/extension.js").read_text()
        self.assertIn("function colorWithOpacity", extension)
        self.assertIn("colorWithOpacity(color, opacity)", extension)
        self.assertIn("if (opacity <= 0) return 'background-color: transparent;'",extension)
        self.assertNotIn("backgroundStyle(this._settings, 'panel')} opacity:", extension)


if __name__ == "__main__":
    unittest.main()
