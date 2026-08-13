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
        self.assertIn('"Shrink the Dash",schema,"custom-theme-shrink"',preferences)

    def test_real_panel_is_styled_and_restored_after_overview(self):
        extension=(ROOT/"shell/extension.js").read_text();stylesheet=(ROOT/"shell/stylesheet.css").read_text()
        self.assertNotIn("gnome-customizer-panel-background",extension)
        self.assertIn("backgroundStyle(this._settings, 'panel', opacity)",extension)
        self.assertIn("const style=`${backgroundStyle(this._settings, 'panel', opacity)}",extension)
        self.assertIn("Main.panel.set_style(style);",extension)
        self.assertIn("this._blur(Main.panel, 'gnome-customizer-panel-blur'",extension)
        self.assertEqual(stylesheet.strip(),"")

    def test_shell_surfaces_wait_for_startup_and_blur_requires_allocation(self):
        extension=(ROOT/"shell/extension.js").read_text()
        self.assertIn("if (Main.layoutManager._startingUp)",extension)
        self.assertIn("Main.layoutManager.connect('startup-complete', () => this._start())",extension)
        self.assertIn("if (!this._started) return;",extension)
        self.assertIn("sigma > 0 && actor.width > 0 && actor.height > 0",extension)

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
        self.assertIn("container:wallpaper", extension)
        self.assertIn("tint.set_opacity(Math.round(255*", extension)
        self.assertIn("wallpaper.add_effect_with_name('gnome-customizer-overview-blur'", extension)
        self.assertIn("Main.overview.connect('showing', () => { this._lowerOverviewBackground();this._queueOverviewHoverScan(); })", extension)
        for key in ("overview-enabled", "overview-opacity", "overview-brightness", "overview-saturation"):
            self.assertIn(key, schema)

    def test_overview_hover_background_opacity_is_applied_without_fading_icon(self):
        extension=(ROOT/"shell/extension.js").read_text();preferences=(ROOT/"src/gnome_customizer/pages/preferences.py").read_text();schema=(ROOT/"shell/schemas/io.github.gnomecustomizer.shell.gschema.xml").read_text()
        self.assertIn('name="overview-hover-opacity"',schema)
        self.assertIn('"Hover Background Opacity",schema,"overview-hover-opacity"',preferences)
        self.assertIn("classes.includes('overview-tile') || classes.includes('grid-search-result')",extension)
        self.assertIn("actor.connect('notify::hover'",extension)
        self.assertIn('"Hover Background Tint",schema,"overview-hover-color"',preferences)
        self.assertIn("colorWithOpacity(this._settings.get_string('overview-hover-color'),opacity)",extension)
        self.assertIn("background-color: ${color}",extension)
        self.assertIn("actor.set_style(record.style)",extension)
        self.assertNotIn("icon.set_opacity",extension)

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

    def test_menu_blur_is_reapplied_when_a_popup_maps(self):
        extension=(ROOT/"shell/extension.js").read_text()
        self.assertIn("actor.connect('notify::mapped', () => this._queueMenuStyle(actor))",extension)
        self.assertIn("this._syncMenuActor(actor)",extension)
        self.assertIn("actor.disconnect(record.mappedId);actor.disconnect(record.destroyId)",extension)

    def test_custom_menu_removes_the_theme_shadow_that_uses_the_stock_radius(self):
        extension=(ROOT/"shell/extension.js").read_text()
        self.assertIn("border: 1px solid ${border}; box-shadow: none;",extension)
        self.assertIn("actor.set_style(record.style)",extension)

    def test_app_grid_can_be_alphabetized_without_reordering_search_results(self):
        extension=(ROOT/"shell/extension.js").read_text();preferences=(ROOT/"src/gnome_customizer/pages/preferences.py").read_text();schema=(ROOT/"shell/schemas/io.github.gnomecustomizer.shell.gschema.xml").read_text()
        self.assertIn('name="alphabetical-app-grid" type="b"',schema)
        self.assertIn('"Alphabetical App Grid","io.github.gnomecustomizer.shell","alphabetical-app-grid"',preferences)
        self.assertIn("overrideMethod(AppDisplay.AppDisplay.prototype, '_compareItems'",extension)
        self.assertIn("overrideMethod(AppDisplay.AppDisplay.prototype, '_redisplay'",extension)
        self.assertIn("localeCompare",extension)
        self.assertIn("this._injectionManager.clear()",extension)
        self.assertNotIn("AppSearchProvider.prototype, '_compareItems'",extension)


if __name__ == "__main__":
    unittest.main()
