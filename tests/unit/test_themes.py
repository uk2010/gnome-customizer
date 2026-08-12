import io, json, tempfile, unittest, zipfile
from pathlib import Path
from PIL import Image
from unittest.mock import patch
from gnome_customizer.backend import themes
from gnome_customizer.backend.themes import ThemeError, capture_current_theme, compatibility_warnings, export_theme, inspect_archive, validate_manifest, import_theme

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
    def test_current_applied_appearance_is_captured_and_round_trips(self):
        wallpaper=Path(tempfile.mkstemp(suffix=".png")[1]);wallpaper.write_bytes(png());self.addCleanup(wallpaper.unlink,missing_ok=True)
        values={
            ("org.gnome.desktop.interface","color-scheme"):"prefer-dark",("org.gnome.desktop.interface","accent-color"):"red",("org.gnome.desktop.interface","icon-theme"):"Yaru-red-dark",("org.gnome.desktop.interface","cursor-theme"):"Yaru",("org.gnome.desktop.interface","gtk-theme"):"Yaru-red-dark",
            ("org.gnome.desktop.background","picture-uri"):wallpaper.as_uri(),("org.gnome.desktop.background","picture-uri-dark"):wallpaper.as_uri(),
            ("io.github.gnomecustomizer.shell","panel-enabled"):True,("io.github.gnomecustomizer.shell","panel-color"):"#112233",("io.github.gnomecustomizer.shell","panel-color2"):"#334455",("io.github.gnomecustomizer.shell","panel-opacity"):0.0,("io.github.gnomecustomizer.shell","panel-blur"):20,("io.github.gnomecustomizer.shell","panel-text-color"):"#ffffff",("io.github.gnomecustomizer.shell","panel-radius"):8,("io.github.gnomecustomizer.shell","panel-gradient-enabled"):False,("io.github.gnomecustomizer.shell","menu-enabled"):False,
            ("io.github.gnomecustomizer.shell","overview-enabled"):True,("io.github.gnomecustomizer.shell","overview-color"):"#18243A",("io.github.gnomecustomizer.shell","overview-opacity"):0.28,("io.github.gnomecustomizer.shell","overview-blur"):30,("io.github.gnomecustomizer.shell","overview-brightness"):0.75,("io.github.gnomecustomizer.shell","overview-saturation"):0.85,("io.github.gnomecustomizer.shell","overview-hover-color"):"#AABBCC",("io.github.gnomecustomizer.shell","overview-hover-opacity"):0.35,
            ("org.gnome.shell.extensions.dash-to-dock","custom-background-color"):True,("org.gnome.shell.extensions.dash-to-dock","background-color"):"#202026",("org.gnome.shell.extensions.dash-to-dock","transparency-mode"):"FIXED",("org.gnome.shell.extensions.dash-to-dock","background-opacity"):0.82,("org.gnome.shell.extensions.dash-to-dock","dash-max-icon-size"):128,("org.gnome.shell.extensions.dash-to-dock","running-indicator-style"):"DOTS",
        }
        class FakeSettings:
            def supports(self,schema,key):return (schema,key) in values
            def get(self,schema,key):return values[schema,key]
            def schema(self,schema):return object() if schema=="org.gnome.shell.extensions.dash-to-dock" else None
        manifest,assets=capture_current_theme(FakeSettings(),"My Current Theme","Tester")
        self.assertEqual(manifest["desktop"]["accent"],"red");self.assertEqual(manifest["shell"]["menus"],{"enabled":False})
        self.assertEqual(manifest["shell"]["overview"]["hover_color"],"#AABBCC");self.assertEqual(manifest["shell"]["overview"]["hover_opacity"],.35);self.assertEqual(manifest["shell"]["dock"]["icon_size"],128)
        target=Path(tempfile.mkstemp(suffix=".gctheme")[1]);target.unlink();self.addCleanup(target.unlink,missing_ok=True)
        export_theme(manifest,assets,target);saved,archive=inspect_archive(target);archive.close();self.assertEqual(saved["shell"]["panel"]["opacity"],0)
    def test_themes_page_exposes_save_current_settings_action(self):
        source=(Path(__file__).parents[2]/"src/gnome_customizer/pages/theme_builder.py").read_text()
        self.assertIn('title="Save Current Settings"',source);self.assertIn("capture_current_theme(self.settings",source)

if __name__=="__main__":unittest.main()
