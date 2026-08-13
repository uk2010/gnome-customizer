import io, json, tempfile, unittest, zipfile
from pathlib import Path
from PIL import Image
from unittest.mock import patch
from gnome_customizer.backend import themes
from gnome_customizer.backend.themes import DESKTOP_THEME_SETTINGS, DOCK_THEME_SETTINGS, SHELL_SURFACE_SETTINGS, ThemeError, capture_current_theme, compatibility_warnings, delete_theme, export_theme, inspect_archive, validate_manifest, import_theme

BASE={"format_version":1,"name":"Safe Theme","author":"Tester","minimum_gnome":"50.1","desktop":{"accent":"blue"}}

def png():
    out=io.BytesIO();Image.new("RGB",(8,8),(20,40,80)).save(out,"PNG");return out.getvalue()

class ThemeTests(unittest.TestCase):
    def archive(self,entries):
        p=Path(tempfile.mkstemp(suffix=".gctheme")[1])
        with zipfile.ZipFile(p,"w") as z:
            for name,data in entries.items():z.writestr(name,data)
        self.addCleanup(p.unlink,missing_ok=True);return p
    def test_minimal_manifest(self):self.assertEqual(validate_manifest(BASE)["name"],"Safe Theme")
    def test_unknown_field_rejected(self):
        with self.assertRaises(ThemeError):validate_manifest({**BASE,"command":"rm"})
    def test_behavior_not_theme_property(self):
        bad={**BASE,"login":{"disable_user_list":True}}
        with self.assertRaises(ThemeError):validate_manifest(bad)
    def test_complete_settings_snapshots_accept_every_exposed_scope(self):
        manifest={**BASE,"desktop":{**BASE["desktop"],"settings":{"org.gnome.desktop.peripherals.keyboard":{"repeat":False},"org.gnome.settings-daemon.plugins.power":{"idle-brightness":42}}},"login":{"settings":{"org.gnome.login-screen":{"logo":"","disable-user-list":True},"org.gnome.desktop.peripherals.mouse":{"speed":.4}},"monitors":"<monitors version=\"2\"></monitors>"}}
        saved=validate_manifest(manifest);self.assertFalse(saved["desktop"]["settings"]["org.gnome.desktop.peripherals.keyboard"]["repeat"]);self.assertEqual(saved["login"]["settings"]["org.gnome.login-screen"]["logo"],"")
    def test_traversal_rejected(self):
        p=self.archive({"manifest.json":json.dumps(BASE),"../escape.png":png()})
        with self.assertRaises(ThemeError):inspect_archive(p)
    def test_fake_image_rejected(self):
        m={**BASE,"preview":"assets/a.png"};p=self.archive({"manifest.json":json.dumps(m),"assets/a.png":b"not png"})
        with self.assertRaises(ThemeError):inspect_archive(p)
    def test_missing_wallpaper_rejected(self):
        m={**BASE,"desktop":{"wallpaper":"assets/missing.png"}};p=self.archive({"manifest.json":json.dumps(m)})
        with self.assertRaisesRegex(ThemeError,"Missing theme assets"):inspect_archive(p)
    def test_invalid_json_rejected(self):
        p=self.archive({"manifest.json":b"{not-json"})
        with self.assertRaisesRegex(ThemeError,"invalid UTF-8 JSON"):inspect_archive(p)
    def test_unicode_metadata_round_trip(self):
        m={**BASE,"name":"Aurora ✨","author":"测试作者","id":"unicode-theme"};p=self.archive({"manifest.json":json.dumps(m,ensure_ascii=False)})
        manifest,archive=inspect_archive(p);archive.close();self.assertEqual(manifest["author"],"测试作者")
    def test_non_ascii_name_gets_safe_import_directory(self):
        m={**BASE,"name":"✨✨","author":"测试"};p=self.archive({"manifest.json":json.dumps(m,ensure_ascii=False)});dest=Path(tempfile.mkdtemp());self.addCleanup(__import__('shutil').rmtree,dest)
        imported=import_theme(p,dest);self.assertEqual(imported.parent,dest);self.assertNotEqual(imported,dest);self.assertTrue(imported.name.startswith("theme-"))
    def test_oversized_file_rejected_before_decode(self):
        p=self.archive({"manifest.json":json.dumps(BASE),"assets/a.png":png()})
        with patch.object(themes,"MAX_IMAGE",4),self.assertRaisesRegex(ThemeError,"size limit"):inspect_archive(p)
    def test_symlink_rejected(self):
        p=Path(tempfile.mkstemp(suffix=".gctheme")[1]);self.addCleanup(p.unlink,missing_ok=True)
        with zipfile.ZipFile(p,"w") as z:
            z.writestr("manifest.json",json.dumps(BASE));link=zipfile.ZipInfo("assets/link.png");link.create_system=3;link.external_attr=0o120777<<16;z.writestr(link,"target")
        with self.assertRaisesRegex(ThemeError,"Symbolic links"):inspect_archive(p)
    def test_import(self):
        m={**BASE,"id":"safe","preview":"assets/a.png"};p=self.archive({"manifest.json":json.dumps(m),"assets/a.png":png()});dest=Path(tempfile.mkdtemp());self.addCleanup(__import__('shutil').rmtree,dest)
        self.assertTrue((import_theme(p,dest)/"manifest.json").is_file())
    def test_delete_removes_only_an_imported_local_theme(self):
        p=self.archive({"manifest.json":json.dumps({**BASE,"id":"delete-me"})});dest=Path(tempfile.mkdtemp());self.addCleanup(__import__('shutil').rmtree,dest,ignore_errors=True);theme=import_theme(p,dest)
        delete_theme(theme,dest);self.assertFalse(theme.exists())
        outside=Path(tempfile.mkdtemp());self.addCleanup(__import__('shutil').rmtree,outside,ignore_errors=True);(outside/"manifest.json").write_text(json.dumps(BASE))
        with self.assertRaisesRegex(ThemeError,"Only an imported local theme"):delete_theme(outside,dest)
    def test_newer_gnome_rejected(self):
        with self.assertRaisesRegex(ThemeError,"requires GNOME 51.0"):validate_manifest({**BASE,"minimum_gnome":"51.0"})
    def test_untested_newer_gnome_warns(self):self.assertTrue(compatibility_warnings({**BASE,"maximum_tested_gnome":"50.3"},(50,4)))
    def test_duplicate_rejected(self):
        p=Path(tempfile.mkstemp(suffix=".gctheme")[1]);self.addCleanup(p.unlink,missing_ok=True)
        with zipfile.ZipFile(p,"w") as z:z.writestr("manifest.json",json.dumps(BASE));z.writestr("manifest.json",json.dumps(BASE))
        with self.assertRaises(ThemeError):inspect_archive(p)
    def test_application_palette_is_controlled_data(self):
        manifest={**BASE,"applications":{"window_color":"#112233","corner_radius":12,"shadow_strength":.4}}
        self.assertEqual(validate_manifest(manifest)["applications"]["window_color"],"#112233")
        with self.assertRaises(ThemeError):validate_manifest({**BASE,"applications":{"css":"* { color: red; }"}})
    def test_dock_theme_allows_full_transparency(self):
        manifest={**BASE,"shell":{"dock":{"opacity":0}}}
        self.assertEqual(validate_manifest(manifest)["shell"]["dock"]["opacity"],0)
    def test_dock_theme_allows_no_running_indicator(self):
        manifest={**BASE,"shell":{"dock":{"indicator_style":"none"}}}
        self.assertEqual(validate_manifest(manifest)["shell"]["dock"]["indicator_style"],"none")
    def test_current_wallpaper_colors_are_normalized_for_export(self):
        values={
            ("org.gnome.desktop.background","primary-color"):"rgb(44, 0, 30)",
            ("org.gnome.desktop.background","secondary-color"):"#111122223333",
        }
        class FakeSettings:
            def supports(self,schema,key):return (schema,key) in values
            def get(self,schema,key):return values[schema,key]
            def schema(self,schema):return None
        manifest,_=capture_current_theme(FakeSettings(),"Current","Tester")
        self.assertEqual(manifest["desktop"]["wallpaper_primary_color"],"#2C001E")
        self.assertEqual(manifest["desktop"]["wallpaper_secondary_color"],"#112233")
    def test_unparseable_current_wallpaper_color_does_not_block_export(self):
        class FakeSettings:
            def supports(self,schema,key):return (schema,key)==("org.gnome.desktop.background","primary-color")
            def get(self,schema,key):return "not a color"
            def schema(self,schema):return None
        manifest,_=capture_current_theme(FakeSettings(),"Current","Tester")
        self.assertNotIn("wallpaper_primary_color",manifest["desktop"])
    def test_current_applied_appearance_is_captured_and_round_trips(self):
        wallpaper=Path(tempfile.mkstemp(suffix=".png")[1]);wallpaper.write_bytes(png());self.addCleanup(wallpaper.unlink,missing_ok=True)
        values={
            ("org.gnome.desktop.interface","color-scheme"):"prefer-dark",("org.gnome.desktop.interface","accent-color"):"red",("org.gnome.desktop.interface","icon-theme"):"Yaru-red-dark",("org.gnome.desktop.interface","cursor-theme"):"Yaru",("org.gnome.desktop.interface","gtk-theme"):"Yaru-red-dark",
            ("org.gnome.desktop.interface","cursor-size"):32,("org.gnome.desktop.interface","text-scaling-factor"):1.25,("org.gnome.desktop.interface","font-name"):"Inter 11",("org.gnome.desktop.interface","font-antialiasing"):"rgba",("org.gnome.desktop.interface","font-hinting"):"slight",
            ("org.gnome.desktop.interface","clock-format"):"12h",("org.gnome.desktop.interface","clock-show-date"):False,("org.gnome.desktop.interface","clock-show-weekday"):True,("org.gnome.desktop.interface","clock-show-seconds"):True,("org.gnome.desktop.interface","show-battery-percentage"):False,
            ("org.gnome.desktop.sound","theme-name"):"Yaru",("org.gnome.desktop.background","picture-uri"):wallpaper.as_uri(),("org.gnome.desktop.background","picture-uri-dark"):wallpaper.as_uri(),("org.gnome.desktop.background","picture-options"):"spanned",("org.gnome.desktop.background","color-shading-type"):"horizontal",("org.gnome.desktop.background","primary-color"):"#102030",("org.gnome.desktop.background","secondary-color"):"#405060",
            ("io.github.gnomecustomizer.shell","panel-enabled"):True,("io.github.gnomecustomizer.shell","panel-color"):"#112233",("io.github.gnomecustomizer.shell","panel-color2"):"#334455",("io.github.gnomecustomizer.shell","panel-opacity"):0.0,("io.github.gnomecustomizer.shell","panel-blur"):20,("io.github.gnomecustomizer.shell","panel-text-color"):"#ffffff",("io.github.gnomecustomizer.shell","panel-radius"):8,("io.github.gnomecustomizer.shell","panel-gradient-enabled"):False,("io.github.gnomecustomizer.shell","panel-gradient-direction"):"horizontal",
            ("io.github.gnomecustomizer.shell","menu-enabled"):False,("io.github.gnomecustomizer.shell","menu-color"):"#202026",("io.github.gnomecustomizer.shell","menu-color2"):"#303044",("io.github.gnomecustomizer.shell","menu-opacity"):0.94,("io.github.gnomecustomizer.shell","menu-blur"):16,("io.github.gnomecustomizer.shell","menu-text-color"):"#FFFFFF",("io.github.gnomecustomizer.shell","menu-border-color"):"#444452",("io.github.gnomecustomizer.shell","menu-radius"):14,("io.github.gnomecustomizer.shell","menu-gradient-enabled"):True,("io.github.gnomecustomizer.shell","menu-gradient-direction"):"vertical",
            ("io.github.gnomecustomizer.shell","overview-enabled"):True,("io.github.gnomecustomizer.shell","overview-color"):"#18243A",("io.github.gnomecustomizer.shell","overview-opacity"):0.28,("io.github.gnomecustomizer.shell","overview-blur"):30,("io.github.gnomecustomizer.shell","overview-brightness"):0.75,("io.github.gnomecustomizer.shell","overview-saturation"):0.85,("io.github.gnomecustomizer.shell","overview-hover-color"):"#AABBCC",("io.github.gnomecustomizer.shell","overview-hover-opacity"):0.35,
            ("org.gnome.shell.extensions.dash-to-dock","dock-position"):"LEFT",("org.gnome.shell.extensions.dash-to-dock","extend-height"):True,("org.gnome.shell.extensions.dash-to-dock","dash-max-icon-size"):128,("org.gnome.shell.extensions.dash-to-dock","icon-size-fixed"):True,("org.gnome.shell.extensions.dash-to-dock","height-fraction"):0.65,("org.gnome.shell.extensions.dash-to-dock","multi-monitor"):True,
            ("org.gnome.shell.extensions.dash-to-dock","show-favorites"):False,("org.gnome.shell.extensions.dash-to-dock","show-running"):True,("org.gnome.shell.extensions.dash-to-dock","show-show-apps-button"):False,("org.gnome.shell.extensions.dash-to-dock","show-apps-at-top"):False,("org.gnome.shell.extensions.dash-to-dock","dock-fixed"):True,("org.gnome.shell.extensions.dash-to-dock","autohide"):False,("org.gnome.shell.extensions.dash-to-dock","intellihide"):False,
            ("org.gnome.shell.extensions.dash-to-dock","transparency-mode"):"DYNAMIC",("org.gnome.shell.extensions.dash-to-dock","background-opacity"):0.82,("org.gnome.shell.extensions.dash-to-dock","custom-background-color"):False,("org.gnome.shell.extensions.dash-to-dock","background-color"):"#202026",("org.gnome.shell.extensions.dash-to-dock","running-indicator-style"):"SQUARES",("org.gnome.shell.extensions.dash-to-dock","apply-custom-theme"):True,("org.gnome.shell.extensions.dash-to-dock","custom-theme-shrink"):True,("org.gnome.shell.extensions.dash-to-dock","force-straight-corner"):True,
        }
        class FakeSettings:
            def supports(self,schema,key):return (schema,key) in values
            def get(self,schema,key):return values[schema,key]
            def schema(self,schema):return object() if schema=="org.gnome.shell.extensions.dash-to-dock" else None
        manifest,assets=capture_current_theme(FakeSettings(),"My Current Theme","Tester")
        for (schema,key),value in values.items():
            if schema in themes.COMPLETE_DESKTOP_SETTINGS and key in themes.COMPLETE_DESKTOP_SETTINGS[schema] and key not in {"picture-uri","picture-uri-dark"}:self.assertEqual(manifest["desktop"]["settings"][schema][key],value)
        for field,(schema,key) in DESKTOP_THEME_SETTINGS.items():self.assertEqual(manifest["desktop"][field],values[schema,key],field)
        for field,key in DOCK_THEME_SETTINGS.items():self.assertEqual(manifest["shell"]["dock"][field],values["org.gnome.shell.extensions.dash-to-dock",key],field)
        for surface,fields in SHELL_SURFACE_SETTINGS.items():
            for field,key in fields.items():self.assertEqual(manifest["shell"][surface][field],values["io.github.gnomecustomizer.shell",key],f"{surface}.{field}")
        self.assertFalse(manifest["shell"]["menus"]["enabled"]);self.assertEqual(manifest["shell"]["menus"]["color"],"#202026")
        self.assertEqual(manifest["shell"]["overview"]["hover_color"],"#AABBCC");self.assertEqual(manifest["shell"]["overview"]["hover_opacity"],.35)
        target=Path(tempfile.mkstemp(suffix=".gctheme")[1]);target.unlink();self.addCleanup(target.unlink,missing_ok=True)
        export_theme(manifest,assets,target);saved,archive=inspect_archive(target);archive.close();self.assertEqual(saved["shell"]["panel"]["opacity"],0)
    def test_current_desktop_and_login_wallpapers_are_embedded(self):
        desktop=Path(tempfile.mkstemp(suffix=".png")[1]);desktop.write_bytes(png());self.addCleanup(desktop.unlink,missing_ok=True)
        login=Path(tempfile.mkstemp(suffix=".png")[1]);login.write_bytes(png());self.addCleanup(login.unlink,missing_ok=True)
        logo=Path(tempfile.mkstemp(suffix=".png")[1]);logo.write_bytes(png());self.addCleanup(logo.unlink,missing_ok=True)
        values={("org.gnome.desktop.background","picture-uri"):desktop.as_uri(),("org.gnome.desktop.background","picture-uri-dark"):desktop.as_uri()}
        class FakeSettings:
            def supports(self,schema,key):return (schema,key) in values
            def get(self,schema,key):return values[schema,key]
            def schema(self,schema):return None
        snapshot={"resource":{"wallpaper":True,"background_color":"#101820","panel_color":"#16161A","panel_color2":"#303044","panel_text_color":"#FFFFFF","panel_opacity":.8,"panel_radius":12,"panel_gradient_enabled":True,"panel_gradient_direction":"vertical"},"accent":"purple","assets":{"wallpaper":str(login),"logo":str(logo)},"settings":{"org.gnome.login-screen":{"logo":"/managed/logo.png","disable-user-list":True}},"monitors":"<monitors version=\"2\"></monitors>"}
        manifest,assets=capture_current_theme(FakeSettings(),"Portable","Tester",snapshot)
        self.assertEqual(set(assets),{"assets/wallpaper.png","assets/wallpaper-dark.png","assets/login-wallpaper.png","assets/login-logo.png"})
        self.assertEqual(manifest["login"]["wallpaper"],"assets/login-wallpaper.png");self.assertEqual(manifest["login"]["logo"],"assets/login-logo.png")
        self.assertEqual(manifest["login"]["accent"],"purple");self.assertEqual(manifest["login"]["panel"]["background_type"],"gradient");self.assertEqual(manifest["login"]["panel"]["gradient_angle"],90)
        self.assertTrue(manifest["login"]["settings"]["org.gnome.login-screen"]["disable-user-list"]);self.assertIn("<monitors",manifest["login"]["monitors"])
        target=Path(tempfile.mkstemp(suffix=".gctheme")[1]);target.unlink();self.addCleanup(target.unlink,missing_ok=True)
        export_theme(manifest,assets,target);saved,archive=inspect_archive(target)
        try:self.assertTrue(set(assets).issubset(archive.namelist()));self.assertEqual(saved["login"]["background_color"],"#101820")
        finally:archive.close()
    def test_themes_page_exposes_save_current_settings_action(self):
        source=(Path(__file__).parents[2]/"src/gnome_customizer/pages/themes.py").read_text()
        self.assertIn('title="Save Current Settings"',source);self.assertIn("capture_current_theme(self.settings",source);self.assertIn('label="Apply Theme"',source);self.assertIn('tooltip_text="Delete Theme"',source);self.assertNotIn('label="Stage Theme"',source)
    def test_window_keeps_saved_themes_but_removes_theme_builder(self):
        source=(Path(__file__).parents[2]/"src/gnome_customizer/window.py").read_text()
        self.assertIn('("themes","Themes"',source)
        self.assertNotIn('("builder","Theme Builder"',source)
        self.assertNotIn('ThemeBuilderPage(',source)

if __name__=="__main__":unittest.main()
