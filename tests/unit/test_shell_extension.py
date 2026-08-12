import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ShellExtensionTests(unittest.TestCase):
    def test_custom_dock_keeps_show_applications_button(self):
        extension = (ROOT / "shell/extension.js").read_text()
        schema = (ROOT / "shell/schemas/io.github.gnomecustomizer.shell.gschema.xml").read_text()
        self.assertIn("dock-show-apps", schema)
        self.assertIn("dock-show-apps-position", schema)
        self.assertIn("view-app-grid-${Main.sessionMode.currentMode}-symbolic", extension)
        self.assertIn("ControlsState.APP_GRID", extension)
        self.assertIn("get_boolean('dock-show-apps')", extension)
        self.assertIn("Main.overview.hide()", extension)
        self.assertIn("toggle_mode: true", extension)

    def test_show_applications_uses_unchanged_native_ubuntu_icon(self):
        extension=(ROOT/"shell/extension.js").read_text()
        self.assertIn("`view-app-grid-${Main.sessionMode.currentMode}-symbolic`",extension)
        self.assertNotIn("changed::color-scheme",extension)
        self.assertNotIn("icon.set_style",extension)

    def test_running_indicator_has_visible_shell_compatible_style(self):
        extension=(ROOT/"shell/extension.js").read_text();stylesheet=(ROOT/"shell/stylesheet.css").read_text();schema=(ROOT/"shell/schemas/io.github.gnomecustomizer.shell.gschema.xml").read_text()
        self.assertIn("app.state === Shell.AppState.RUNNING",extension)
        self.assertIn("indicatorStyle !== 'none'",extension)
        self.assertIn('<choice value="none"/>',schema)
        self.assertIn("indicatorStyle === 'dot' ? 7",extension)
        self.assertIn("background-color: #ffffff",extension)
        self.assertNotIn("background-color: currentColor",stylesheet)

    def test_every_dock_icon_reserves_a_fixed_indicator_lane(self):
        extension=(ROOT/"shell/extension.js").read_text();stylesheet=(ROOT/"shell/stylesheet.css").read_text()
        self.assertIn("_iconContent(app.create_icon_texture(size),size)",extension)
        self.assertIn("child: this._iconContent(icon,size)[0]",extension)
        self.assertIn("height:7",extension)
        self.assertIn("style:'spacing: 0;'",extension)
        self.assertIn("y_align:Clutter.ActorAlign.START",extension)
        self.assertIn("indicatorLane.set_child",extension)
        self.assertIn("gnome-customizer-indicator-lane",stylesheet)

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

    def test_corner_radius_is_independent_of_floating_margin(self):
        extension=(ROOT/"shell/extension.js").read_text()
        self.assertIn("const radius = this._settings.get_int('dock-radius');",extension)
        self.assertNotIn("floating ? this._settings.get_int('dock-radius') : 0",extension)

    def test_floating_dock_stays_close_to_the_screen_edge(self):
        extension=(ROOT/"shell/extension.js").read_text()
        self.assertIn("const margin = floating ? 2 : 0",extension)

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
        schema = (ROOT / "shell/schemas/io.github.gnomecustomizer.shell.gschema.xml").read_text()
        preferences = (ROOT / "src/gnome_customizer/pages/preferences.py").read_text()
        self.assertIn('<key name="dock-opacity" type="d"><range min="0.0" max="1.0"/>',schema)
        self.assertIn('self.spin(g,"Opacity",schema,"dock-opacity",0,1,.01)',preferences)
        self.assertIn("function colorWithOpacity", extension)
        self.assertIn("backgroundStyle(this._settings, 'dock', opacity)", extension)
        self.assertIn("colorWithOpacity(color, opacity)", extension)
        self.assertIn("if (opacity <= 0) return 'background-color: transparent;'",extension)
        self.assertIn("if (opacity > 0 && sigma > 0)",extension)
        self.assertNotIn("backgroundStyle(this._settings, 'dock')} opacity:", extension)
        self.assertNotIn("backgroundStyle(this._settings, 'panel')} opacity:", extension)

    def test_dock_reanchors_after_shell_allocates_its_final_size(self):
        extension = (ROOT / "shell/extension.js").read_text()
        self.assertIn("notify::width", extension)
        self.assertIn("notify::height", extension)
        self.assertIn("_queuePosition()", extension)
        self.assertIn("this.actor.height > 0 ? this.actor.height : naturalHeight", extension)
        self.assertIn("monitor.y + monitor.height - height - this._margin", extension)
        self.assertIn("if (!this.actor || !this._settings) return;", extension)


if __name__ == "__main__":
    unittest.main()
