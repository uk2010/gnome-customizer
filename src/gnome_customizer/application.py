import gi
gi.require_version("Gtk","4.0");gi.require_version("Adw","1")
from gi.repository import Adw, Gio, Gtk
from .backend.constants import APP_ID
from .window import CustomizerWindow

class CustomizerApplication(Adw.Application):
    def __init__(self):super().__init__(application_id=APP_ID,flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
    def do_startup(self):
        Adw.Application.do_startup(self);action=Gio.SimpleAction.new("about",None);action.connect("activate",self._about);self.add_action(action)
    def do_activate(self):
        window=self.props.active_window or CustomizerWindow(self);window.present()
    def _about(self,*_):
        dialog=Adw.AboutDialog(application_name="GNOME Customizer",application_icon=APP_ID,developer_name="GNOME Customizer Contributors",version="0.3.28",website="https://github.com/uk2010/gnome-customizer",issue_url="https://github.com/uk2010/gnome-customizer/issues",license_type=Gtk.License.GPL_3_0);dialog.present(self.props.active_window)
