import base64, importlib.machinery, importlib.util, io, shutil, tempfile, unittest
from pathlib import Path
from PIL import Image
from unittest.mock import patch

HERE=Path(__file__).resolve().parents[2]
loader=importlib.machinery.SourceFileLoader("customizer_helper",str(HERE/"helper/gnome-customizer-system-helper.in"));spec=importlib.util.spec_from_loader(loader.name,loader);helper=importlib.util.module_from_spec(spec);loader.exec_module(helper)

def png():
    stream=io.BytesIO();Image.new("RGB",(10,10),(10,20,30)).save(stream,"PNG");return stream.getvalue()

class HelperTests(unittest.TestCase):
    def setUp(self):
        self.temp=Path(tempfile.mkdtemp());self.addCleanup(shutil.rmtree,self.temp)
        self.old={name:getattr(helper,name) for name in ("ROOT","STATE","ASSETS","RESOURCE","DCONF","GDM_STATE","RESOURCE_STATE","PROFILE","PROFILE_MARK","PREVIOUS","PREV_MON","MON_MARK","MONITORS","LINK","COMPILE_RESOURCES","run")}
        helper.ROOT=self.temp/"root";helper.STATE=helper.ROOT/"state";helper.ASSETS=helper.ROOT/"assets";helper.RESOURCE=helper.ROOT/"theme.gresource";helper.DCONF=self.temp/"etc/99-customizer";helper.GDM_STATE=helper.STATE/"gdm-settings.json";helper.RESOURCE_STATE=helper.STATE/"resource-settings.json";helper.PROFILE=self.temp/"profile";helper.PROFILE_MARK=helper.STATE/"profile-created";helper.PREVIOUS=helper.STATE/"previous";helper.PREV_MON=helper.STATE/"monitors.previous";helper.MON_MARK=helper.STATE/"monitors-created";helper.MONITORS=self.temp/"monitors.xml";helper.LINK=self.temp/"gdm-theme.gresource";helper.COMPILE_RESOURCES=shutil.which("glib-compile-resources") or str(HERE/".build-tools/glib-dev-root/usr/bin/glib-compile-resources")
        self.addCleanup(lambda:[setattr(helper,k,v) for k,v in self.old.items()])
        self.service=helper.Helper(None)
    def test_setting_enums_and_logo_path(self):
        with self.assertRaises(ValueError):helper.validate_setting("org.gnome.desktop.interface","accent-color","chartreuse")
        with self.assertRaises(ValueError):helper.validate_setting("org.gnome.login-screen","logo","/tmp/logo.png")
        with self.assertRaises(ValueError):helper.validate_setting("org.gnome.login-screen","logo",str(helper.ASSETS/".."/"logo.png"))
    def test_asset_magic_validation(self):
        with self.assertRaises(ValueError):self.service.assets({"assets":{"logo":{"mime":"image/png","data":base64.b64encode(b"fake").decode()}}})
    def test_fast_appearance_status_returns_existing_login_theme(self):
        helper.STATE.mkdir(parents=True);helper.ASSETS.mkdir(parents=True)
        (helper.ASSETS/"wallpaper.png").write_bytes(png());(helper.ASSETS/"logo.png").write_bytes(png())
        helper.RESOURCE_STATE.write_text('{"wallpaper": true, "background_color": "#123456", "unknown": true}')
        helper.GDM_STATE.write_text('{"org.gnome.desktop.interface": {"accent-color": "pink"}, "org.gnome.login-screen": {"logo": "/usr/local/share/gnome-customizer/assets/logo.png", "banner-message-text": "private"}}')
        status=self.service.status({"appearance_only":True});appearance=status["appearance"]
        self.assertEqual(appearance["accent"],"pink");self.assertEqual(appearance["resource"],{"wallpaper":True,"background_color":"#123456"})
        self.assertEqual(set(appearance["assets"]),{"wallpaper","logo"});self.assertNotIn("settings",appearance)
    def test_asset_and_resource_compile(self):
        self.service.assets({"assets":{"wallpaper":{"mime":"image/png","data":base64.b64encode(png()).decode()}}})
        result=self.service.resource({"wallpaper":True,"panel_color":"#111122","panel_opacity":.8});self.assertEqual(len(result["sha256"]),64);self.assertTrue(helper.RESOURCE.is_file());self.service.resource({"wallpaper":False,"panel_gradient_enabled":False,"panel_text_color":"#FFFFFF"})
        import subprocess
        listed=subprocess.run(["gresource","list",helper.RESOURCE],text=True,capture_output=True,check=True).stdout;self.assertIn("/org/gnome/shell/theme/gdm.css",listed)
        css=subprocess.run(["gresource","extract",helper.RESOURCE,"/org/gnome/shell/theme/gdm.css"],text=True,capture_output=True,check=True).stdout;controlled=css.rsplit("GNOME Customizer controlled appearance",1)[-1];self.assertNotIn("background-image",controlled);self.assertNotIn("background-gradient-start",controlled);self.assertIn("rgba(17, 17, 34, 0.800)",controlled);self.assertNotIn("opacity:",controlled)
        with self.assertRaises(ValueError):self.service.resource({"wallpaper":"yes"})
    def test_request_size_and_shape(self):
        with self.assertRaises(ValueError):helper.require_dict("[]")
        with self.assertRaises(ValueError):helper.require_dict("x"*(helper.MAX_PAYLOAD+1))
    def test_monitor_xml_validation_and_restore(self):
        with self.assertRaises(ValueError):self.service.monitors({"xml":"<monitors version=\"2\"><!DOCTYPE x></monitors>"})
        self.service.monitors({"xml":"<monitors version=\"2\"></monitors>"});self.assertTrue(helper.MONITORS.is_file());self.service.restore_monitors({});self.assertFalse(helper.MONITORS.exists())
    def test_dconf_merges_managed_settings(self):
        class Result:stdout=""
        helper.run=lambda *a,**k:Result()
        self.service.dconf({"settings":{"org.gnome.desktop.interface":{"accent-color":"blue"}}});self.service.dconf({"settings":{"org.gnome.desktop.interface":{"clock-show-date":True}}})
        text=helper.DCONF.read_text();self.assertIn("accent-color='blue'",text);self.assertIn("clock-show-date=true",text)
    def test_dconf_text_cannot_inject_keyfile_lines(self):
        class Result:stdout=""
        helper.run=lambda *a,**k:Result();self.service.dconf({"settings":{"org.gnome.login-screen":{"banner-message-text":"Hello\n[evil]\nkey=true"}}});text=helper.DCONF.read_text();self.assertIn("Hello\\n[evil]\\nkey=true",text);self.assertNotIn("\n[evil]\n",text)
    def test_restore_removes_only_unchanged_profile_it_created(self):
        class Result:stdout=""
        helper.run=lambda *a,**k:Result();self.service.dconf({"settings":{"org.gnome.desktop.interface":{"accent-color":"blue"}}});self.assertTrue(helper.PROFILE_MARK.exists());self.service.restore_resource=lambda p:{};self.service.restore_monitors=lambda p:{};self.service.restore_all({});self.assertFalse(helper.PROFILE.exists());self.assertFalse(helper.PROFILE_MARK.exists())
    def test_failed_first_activation_removes_new_alternative(self):
        def resource(_):helper.RESOURCE.parent.mkdir(parents=True,exist_ok=True);helper.RESOURCE.write_bytes(b"resource");return {}
        def activate(_):helper.LINK.symlink_to(helper.RESOURCE);raise RuntimeError("activation failed")
        self.service.resource=resource;self.service.activate=activate
        with patch.object(helper.subprocess,"run") as command,self.assertRaises(RuntimeError):self.service.transaction({"resource":{"background_color":"#112233"}})
        self.assertTrue(any(call.args[0][:3]==["/usr/bin/update-alternatives","--remove",helper.ALT] for call in command.call_args_list));self.assertFalse(helper.RESOURCE.exists())

if __name__=="__main__":unittest.main()
