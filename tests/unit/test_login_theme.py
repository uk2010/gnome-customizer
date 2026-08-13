import base64, io, tempfile, unittest
from pathlib import Path
from PIL import Image

from gnome_customizer.backend.login_theme import clear_login_theme_snapshot, remember_applied_login_theme
from gnome_customizer.backend.state import StateStore

def png():
    output=io.BytesIO();Image.new("RGB",(8,8),(20,40,80)).save(output,"PNG");return output.getvalue()


class LoginThemeStateTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(tempfile.mkdtemp());self.addCleanup(__import__('shutil').rmtree,self.root,ignore_errors=True)
        self.state=StateStore(self.root/"state.json");self.assets=self.root/"assets"

    def test_successful_transaction_is_merged_and_images_are_durable(self):
        image={"mime":"image/png","data":base64.b64encode(png()).decode("ascii")}
        remember_applied_login_theme(self.state,{"resource":{"wallpaper":True,"background_color":"#123456"},"settings":{"org.gnome.desktop.interface":{"accent-color":"orange"}},"assets":{"wallpaper":image,"logo":image}},self.assets)
        snapshot=self.state.data["login_theme"]
        self.assertEqual(snapshot["accent"],"orange");self.assertEqual(snapshot["resource"]["background_color"],"#123456")
        self.assertTrue(Path(snapshot["assets"]["wallpaper"]).is_file());self.assertTrue(Path(snapshot["assets"]["logo"]).is_file())
        remember_applied_login_theme(self.state,{"resource":{"wallpaper":False},"settings":{"org.gnome.login-screen":{"logo":""}}},self.assets)
        self.assertEqual(self.state.data["login_theme"]["assets"],{})

    def test_clear_removes_snapshot_and_owned_images(self):
        image={"mime":"image/png","data":base64.b64encode(png()).decode("ascii")}
        remember_applied_login_theme(self.state,{"assets":{"wallpaper":image}},self.assets)
        clear_login_theme_snapshot(self.state,self.assets)
        self.assertNotIn("login_theme",self.state.data);self.assertEqual(list(self.assets.iterdir()),[])


if __name__=="__main__":unittest.main()
