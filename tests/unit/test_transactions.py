import tempfile, unittest
from pathlib import Path
from gnome_customizer.backend.state import StateStore
from gnome_customizer.backend.transactions import Change, ChangeManager, TransactionError
from gnome_customizer.backend.wallpaper import wallpaper_keys

class FakeSettings:
    def __init__(self):self.values={('s','a'):'old',('s','b'):1,('org.gnome.shell','enabled-extensions'):['other@example'],('org.gnome.shell','disabled-extensions'):[],('org.gnome.shell','disable-user-extensions'):True,('org.gnome.shell.extensions.dash-to-dock','autohide'):False,('io.github.gnomecustomizer.shell','panel-enabled'):False,('org.gnome.desktop.interface','accent-color'):'blue',('org.gnome.desktop.interface','color-scheme'):'default',('org.gnome.desktop.interface','gtk-theme'):'Yaru-blue',('org.gnome.desktop.interface','icon-theme'):'Yaru-blue'};self.fail=None
    def supports(self,s,k):return (s,k) in self.values
    def get(self,s,k):return self.values[s,k]
    def set(self,s,k,v):
        if k==self.fail:raise RuntimeError('failure')
        self.values[s,k]=v
    def default(self,s,k):return {'a':'default-a','b':0}.get(k,[])
    def reset(self,s,k):
        if k==self.fail:raise RuntimeError('failure')
        self.values[s,k]=self.default(s,k)

class TransactionTests(unittest.TestCase):
    def setUp(self):self.backend=FakeSettings();self.store=StateStore(Path(tempfile.mkdtemp())/'state.json');self.manager=ChangeManager(self.backend,self.store)
    def test_apply_and_restore(self):
        self.manager.stage(Change('desktop','s','a','new','A'));self.assertEqual(self.manager.apply(),1);self.assertEqual(self.backend.values['s','a'],'new');self.assertEqual(self.manager.restore(),1);self.assertEqual(self.backend.values['s','a'],'old')
    def test_rollback(self):
        self.manager.stage(Change('desktop','s','a','new','A'));self.manager.stage(Change('desktop','s','b',2,'B'));self.backend.fail='b'
        with self.assertRaises(TransactionError):self.manager.apply()
        self.assertEqual(self.backend.values['s','a'],'old');self.assertEqual(self.store.original('desktop'),{})
    def test_extension_delta_preserves_unrelated_extensions(self):
        uuid='gnome-customizer@io.github.gnomecustomizer';self.manager.stage(Change('shell','org.gnome.shell','enabled-extensions',[uuid],'Companion'));self.backend.values['org.gnome.shell','enabled-extensions'].append('added-later@example');self.manager.apply();self.assertEqual(set(self.backend.values['org.gnome.shell','enabled-extensions']),{'other@example','added-later@example',uuid});self.manager.restore('shell');self.assertEqual(set(self.backend.values['org.gnome.shell','enabled-extensions']),{'other@example','added-later@example'})
    def test_native_dock_setting_does_not_enable_companion(self):
        self.manager.stage(Change('shell','org.gnome.shell.extensions.dash-to-dock','autohide',True,'Auto-hide'))
        self.assertEqual(set(self.manager.pending),{('org.gnome.shell.extensions.dash-to-dock','autohide')})
        self.assertEqual(self.manager.apply(),1);self.assertTrue(self.backend.values['org.gnome.shell.extensions.dash-to-dock','autohide'])
    def test_native_accent_updates_yaru_gtk_and_folder_icons(self):
        self.manager.stage(Change('desktop','org.gnome.desktop.interface','accent-color','red','Accent Color'))
        self.assertEqual(self.manager.pending[('org.gnome.desktop.interface','gtk-theme')].value,'Yaru-red')
        self.assertEqual(self.manager.pending[('org.gnome.desktop.interface','icon-theme')].value,'Yaru-red')
        self.assertEqual(self.manager.apply(),3)
    def test_dark_and_light_modes_remap_the_current_accent(self):
        self.manager.stage(Change('desktop','org.gnome.desktop.interface','accent-color','pink','Accent Color'))
        self.manager.stage(Change('desktop','org.gnome.desktop.interface','color-scheme','prefer-dark','Color Scheme'))
        self.assertEqual(self.manager.pending[('org.gnome.desktop.interface','gtk-theme')].value,'Yaru-magenta-dark')
        self.assertEqual(self.manager.pending[('org.gnome.desktop.interface','icon-theme')].value,'Yaru-magenta-dark')
        self.manager.stage(Change('desktop','org.gnome.desktop.interface','color-scheme','default','Color Scheme'))
        self.assertEqual(self.manager.pending[('org.gnome.desktop.interface','gtk-theme')].value,'Yaru-magenta')
        self.assertEqual(self.manager.pending[('org.gnome.desktop.interface','icon-theme')].value,'Yaru-magenta')
    def test_native_accent_preserves_non_yaru_icon_theme_like_gnome_settings(self):
        self.backend.values[('org.gnome.desktop.interface','icon-theme')]='Papirus'
        self.manager.stage(Change('desktop','org.gnome.desktop.interface','accent-color','green','Accent Color'))
        self.assertNotIn(('org.gnome.desktop.interface','icon-theme'),self.manager.pending)
        self.assertEqual(self.manager.pending[('org.gnome.desktop.interface','gtk-theme')].value,'Yaru-olive')
    def test_shell_surface_setting_enables_companion(self):
        uuid='gnome-customizer@io.github.gnomecustomizer';self.backend.values['org.gnome.shell','disabled-extensions']=[uuid,'disabled@example']
        self.manager.stage(Change('shell','io.github.gnomecustomizer.shell','panel-enabled',True,'Panel'))
        self.assertEqual(self.manager.apply(),4);self.assertIn(uuid,self.backend.values['org.gnome.shell','enabled-extensions']);self.assertNotIn(uuid,self.backend.values['org.gnome.shell','disabled-extensions']);self.assertFalse(self.backend.values['org.gnome.shell','disable-user-extensions']);self.assertTrue(self.backend.values['io.github.gnomecustomizer.shell','panel-enabled'])
    def test_restore_rolls_back_and_keeps_restore_state_on_failure(self):
        self.store.remember_original('desktop','s:a','old');self.store.remember_original('desktop','s:b',1);self.store.save();self.backend.values['s','a']='changed';self.backend.values['s','b']=2;self.backend.fail='b'
        with self.assertRaises(TransactionError):self.manager.restore('desktop')
        self.assertEqual(self.backend.values['s','a'],'changed');self.assertTrue(self.store.original('desktop'))
    def test_primary_wallpaper_targets_light_and_dark_modes(self):
        self.assertEqual(wallpaper_keys(dark_override=False,supports_dark=True),('picture-uri','picture-uri-dark'))
        self.assertEqual(wallpaper_keys(dark_override=True,supports_dark=True),('picture-uri-dark',))
        self.assertEqual(wallpaper_keys(dark_override=False,supports_dark=False),('picture-uri',))
    def test_reset_managed_covers_desktop_and_shell_but_preserves_other_extensions(self):
        uuid='gnome-customizer@io.github.gnomecustomizer';self.backend.values['org.gnome.shell','enabled-extensions']=[uuid,'other@example']
        self.store.data['managed']={'desktop':['s:a'],'shell':['org.gnome.shell:enabled-extensions']};self.store.save()
        self.assertEqual(self.manager.reset_managed(),2);self.assertEqual(self.backend.values['s','a'],'default-a');self.assertEqual(self.backend.values['org.gnome.shell','enabled-extensions'],['other@example']);self.assertEqual(self.store.data['managed'],{})
    def test_factory_reset_includes_exposed_settings_changed_before_customizer(self):
        self.backend.values['s','b']=99;self.manager.register_factory('desktop','s','b')
        self.assertGreaterEqual(self.manager.reset_factory(),1);self.assertEqual(self.backend.values['s','b'],0)

if __name__=="__main__":unittest.main()
