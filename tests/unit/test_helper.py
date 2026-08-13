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
        self.old={name:getattr(helper,name) for name in ("ROOT","STATE","ASSETS","RESOURCE","DCONF","GDM_DCONF_DIR","GDM_DCONF_DB","GDM_USER_DBS","GDM_STATE","RESOURCE_STATE","PROFILE","PROFILE_MARK","PREVIOUS","PREV_MON","MON_MARK","MONITORS","LINK","COMPILE_RESOURCES","run")}
        helper.ROOT=self.temp/"root";helper.STATE=helper.ROOT/"state";helper.ASSETS=helper.ROOT/"assets";helper.RESOURCE=helper.ROOT/"theme.gresource";helper.GDM_DCONF_DIR=self.temp/"etc/gdm.d";helper.DCONF=helper.GDM_DCONF_DIR/"99-customizer";helper.GDM_DCONF_DB=self.temp/"etc/gdm";helper.GDM_USER_DBS=(self.temp/"gdm3/user",self.temp/"gdm/user");helper.GDM_STATE=helper.STATE/"gdm-settings.json";helper.RESOURCE_STATE=helper.STATE/"resource-settings.json";helper.PROFILE=self.temp/"profile";helper.PROFILE_MARK=helper.STATE/"profile-created";helper.PREVIOUS=helper.STATE/"previous";helper.PREV_MON=helper.STATE/"monitors.previous";helper.MON_MARK=helper.STATE/"monitors-created";helper.MONITORS=self.temp/"monitors.xml";helper.LINK=self.temp/"gdm-theme.gresource";helper.COMPILE_RESOURCES=shutil.which("glib-compile-resources") or str(HERE/".build-tools/glib-dev-root/usr/bin/glib-compile-resources")
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
        self.assertEqual(set(appearance["assets"]),{"wallpaper","logo"});self.assertIn("settings",appearance);self.assertIn("monitors",appearance)
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
        xml="<monitors version=\"2\"></monitors>";result=self.service.monitors({"xml":xml})
        self.assertEqual(helper.MONITORS.read_text(),xml);self.assertEqual(helper.MONITORS.stat().st_mode&0o777,0o600)
        self.assertEqual(result["path"],str(helper.MONITORS));self.assertEqual(result["sha256"],__import__('hashlib').sha256(xml.encode()).hexdigest())
        if helper.os.geteuid()==0:
            account=helper.pwd.getpwnam(helper.gdm_user());info=helper.MONITORS.stat();directory=helper.MONITORS.parent.stat()
            self.assertEqual((info.st_uid,info.st_gid),(account.pw_uid,account.pw_gid));self.assertEqual((directory.st_uid,directory.st_gid),(account.pw_uid,account.pw_gid))
        self.service.restore_monitors({});self.assertFalse(helper.MONITORS.exists())
    def test_monitor_transaction_writes_and_verifies_exact_layout(self):
        xml='<monitors version="2"><configuration><logicalmonitor><x>1440</x></logicalmonitor></configuration></monitors>'
        with patch.object(helper,"gdm_user",return_value=None):result=self.service.transaction({"monitors":xml})
        self.assertEqual(helper.MONITORS.read_bytes(),xml.encode());self.assertEqual(result["sha256"],__import__('hashlib').sha256(xml.encode()).hexdigest())
    def test_production_monitor_path_uses_gdm_account_home(self):
        account=type("Account",(),{"pw_dir":"/srv/gdm-test","pw_uid":123,"pw_gid":456})()
        with patch.object(helper,"MONITORS",None),patch.object(helper,"gdm_user",return_value="gdm"),patch.object(helper.pwd,"getpwnam",return_value=account):
            self.assertEqual(helper.monitor_path(),Path("/srv/gdm-test/.config/monitors.xml"))
    def test_dconf_merges_managed_settings(self):
        class Result:stdout=""
        helper.run=lambda *a,**k:Result()
        self.service.dconf({"settings":{"org.gnome.desktop.interface":{"accent-color":"blue"}}});self.service.dconf({"settings":{"org.gnome.desktop.interface":{"clock-show-date":True}}})
        text=helper.DCONF.read_text();self.assertIn("accent-color='blue'",text);self.assertIn("clock-show-date=true",text)
    def test_complete_transaction_replaces_stale_login_settings(self):
        class Result:stdout=""
        helper.run=lambda *a,**k:Result();helper.GDM_STATE.parent.mkdir(parents=True);helper.GDM_STATE.write_text('{"org.gnome.login-screen":{"logo":"/old/logo.png","disable-user-list":true}}')
        self.service.transaction({"settings":{"org.gnome.login-screen":{"logo":"","disable-user-list":False}}})
        saved=__import__('json').loads(helper.GDM_STATE.read_text());self.assertEqual(saved,{"org.gnome.login-screen":{"logo":"","disable-user-list":False}})
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
    def test_restore_fails_if_custom_resource_remains_active(self):
        helper.RESOURCE.parent.mkdir(parents=True);helper.RESOURCE.write_bytes(b"custom")
        with patch.object(helper,"current",return_value=helper.RESOURCE),patch.object(helper.subprocess,"run") as command:
            command.return_value.returncode=0;command.return_value.stderr=""
            with self.assertRaisesRegex(RuntimeError,"stock GDM resource did not become active"):self.service.restore_resource({})
    def test_restore_switches_to_stock_and_removes_custom_resource(self):
        stock=self.temp/"stock.gresource";stock.write_bytes(b"stock");helper.RESOURCE.parent.mkdir(parents=True);helper.RESOURCE.write_bytes(b"custom");active=[helper.RESOURCE]
        def execute(argv,**_):
            class Result:returncode=0;stderr="";stdout=""
            if argv[:3]==["/usr/bin/update-alternatives","--set",helper.ALT]:active[0]=Path(argv[3])
            return Result()
        with patch.object(helper,"YARU",stock),patch.object(helper,"STOCK",stock),patch.object(helper,"current",side_effect=lambda:active[0]),patch.object(helper,"run",side_effect=execute),patch.object(helper.subprocess,"run",side_effect=execute):
            self.service.restore_resource({})
        self.assertEqual(active[0],stock);self.assertFalse(helper.RESOURCE.exists())
    def test_factory_reset_ignores_previous_resource_and_selects_yaru(self):
        yaru=self.temp/"yaru.gresource";yaru.write_bytes(b"yaru");previous=self.temp/"previous.gresource";previous.write_bytes(b"previous")
        helper.STATE.mkdir(parents=True);helper.RESOURCE.write_bytes(b"custom");helper.PREVIOUS.write_text(str(previous));active=[previous]
        def execute(argv,**_):
            class Result:returncode=0;stderr="";stdout=""
            if argv[:3]==["/usr/bin/update-alternatives","--set",helper.ALT]:active[0]=Path(argv[3])
            return Result()
        with patch.object(helper,"YARU",yaru),patch.object(helper,"STOCK",yaru),patch.object(helper,"current",side_effect=lambda:active[0]),patch.object(helper,"run",side_effect=execute),patch.object(helper.subprocess,"run",side_effect=execute):
            self.service.restore_resource({"factory":True})
        self.assertEqual(active[0],yaru);self.assertFalse(helper.RESOURCE.exists())
    def test_factory_reset_removes_all_local_gdm_state(self):
        class Result:stdout=""
        helper.run=lambda *a,**k:Result();helper.GDM_DCONF_DIR.mkdir(parents=True);(helper.GDM_DCONF_DIR/"95-other-customizer").write_text("custom")
        helper.GDM_DCONF_DB.write_bytes(b"compiled");helper.PROFILE.write_text("custom profile")
        for database in helper.GDM_USER_DBS:database.parent.mkdir(parents=True);database.write_bytes(b"user settings")
        helper.MONITORS.write_text("custom monitors");helper.PREV_MON.parent.mkdir(parents=True);helper.PREV_MON.write_text("previous monitors")
        self.service.restore_resource=lambda p:{};self.service.restore_all({"factory":True})
        self.assertFalse(helper.GDM_DCONF_DIR.exists());self.assertFalse(helper.GDM_DCONF_DB.exists());self.assertFalse(helper.PROFILE.exists())
        self.assertFalse(any(database.exists() for database in helper.GDM_USER_DBS));self.assertFalse(helper.MONITORS.exists());self.assertFalse(helper.PREV_MON.exists())

if __name__=="__main__":unittest.main()
