import threading
from gi.repository import Adw, Gdk, GLib, Gtk
from ..backend.diagnostics import collect, safe_report

class StatusPage(Adw.PreferencesPage):
    def __init__(self,settings,helper,pending):
        super().__init__(title="Status");self._settings=settings;self._helper=helper;self._pending=pending;self._loaded=False;self.group=Adw.PreferencesGroup(title="System Status");self.add(self.group);self.placeholder=Adw.ActionRow(title="Open this page to collect diagnostic information");self.group.add(self.placeholder);self.connect("map",self._mapped)
    def _mapped(self,*_):
        if not self._loaded:self._loaded=True;self.placeholder.set_title("Collecting diagnostic information…");self.refresh()
    def _build(self):
        values=collect(self._settings,self._helper,self._pending());GLib.idle_add(self._display,values)
    def refresh(self):threading.Thread(target=self._build,daemon=True).start()
    def _display(self,values):
        if self.placeholder:self.group.remove(self.placeholder);self.placeholder=None
        for key,value in values.items(): row=Adw.ActionRow(title=key,subtitle=value);self.group.add(row)
        b=Gtk.Button(label="Copy Diagnostic Information",halign=Gtk.Align.CENTER);b.connect("clicked",lambda *_:Gdk.Display.get_default().get_clipboard().set(safe_report(values)));self.group.add(b);return GLib.SOURCE_REMOVE
