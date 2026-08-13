from __future__ import annotations

import json, tempfile, threading
from pathlib import Path
from gi.repository import Adw, GLib, Gtk
from ..backend.themes import COMPLETE_LOGIN_SETTINGS, capture_current_theme, compatibility_warnings, delete_theme, export_theme, import_theme

class ThemesPage(Adw.PreferencesPage):
    def __init__(self,toast,apply_theme=None,settings=None,state=None,helper=None):
        super().__init__(title="Themes",description="Import, apply, delete, and share complete GNOME Customizer settings snapshots");self.toast=toast;self.apply_theme=apply_theme;self.settings=settings;self.state=state;self.helper=helper;self.group=Adw.PreferencesGroup(title="Local Themes");self.add(self.group);self._theme_rows={}
        if settings:
            save=Adw.ActionRow(title="Save Current Settings",subtitle="Save every setting exposed by the app, including login images and display resolution");save_button=Gtk.Button(label="Save as Theme",valign=Gtk.Align.CENTER,css_classes=["suggested-action"]);save_button.connect("clicked",self._save_current);save.add_suffix(save_button);self.group.add(save)
        row=Adw.ActionRow(title="Import .gctheme",subtitle="Archives are validated before extraction");button=Gtk.Button(label="Choose File",valign=Gtk.Align.CENTER);button.connect("clicked",self._choose);row.add_suffix(button);self.group.add(row)
        self.samples=Adw.PreferencesGroup(title="Included Samples",description="Safe themes shipped with GNOME Customizer");self.add(self.samples);self._sample_temp=tempfile.TemporaryDirectory(prefix="gnome-customizer-samples-")
        from ..backend.constants import THEMES_DIR
        threading.Thread(target=self._scan,args=(THEMES_DIR,),daemon=True).start();threading.Thread(target=self._scan_samples,daemon=True).start()
    def _scan(self,directory):
        if directory.is_dir():
            for theme in sorted(directory.iterdir()):
                if (theme/"manifest.json").is_file():GLib.idle_add(self._add_theme,theme)
    def _scan_samples(self):
        installed=Path("/usr/share/gnome-customizer/sample-themes");source=Path(__file__).resolve().parents[3]/"data/themes";root=installed if installed.is_dir() else source
        for archive in sorted(root.glob("*.gctheme")):
            try:GLib.idle_add(self._add_theme,import_theme(archive,Path(self._sample_temp.name)),self.samples)
            except Exception as exc:GLib.idle_add(self.toast,f"Sample theme error: {exc}")
    def _choose(self,*_):Gtk.FileDialog(title="Import Theme").open(self.get_root(),None,self._done)
    def _save_current(self,*_):Gtk.FileDialog(title="Save Current Settings as Theme",initial_name="Current Settings.gctheme").save(self.get_root(),None,self._save_current_done)
    def _save_current_done(self,dialog,result):
        try:
            target=Path(dialog.save_finish(result).get_path());name=target.stem.strip() or "Current Settings";author=GLib.get_real_name()
            if not author or author == "Unknown":author=GLib.get_user_name() or "GNOME User"
            login=self.helper.login_appearance() if self.helper else None
            if not login and self.state:login=self.state.data.get("login_theme")
            login=self._complete_login(login)
            manifest,assets=capture_current_theme(self.settings,name,author,login)
            threading.Thread(target=self._save_current_worker,args=(manifest,assets,target),daemon=True).start()
        except GLib.Error:pass
        except Exception as exc:self.toast(str(exc))
    def _complete_login(self,login):
        result=dict(login) if isinstance(login,dict) else {}
        saved=result.get("settings",{});complete={}
        for schema,keys in COMPLETE_LOGIN_SETTINGS.items():
            existing=saved.get(schema,{}) if isinstance(saved,dict) else {}
            values={}
            for key in sorted(keys):
                if isinstance(existing,dict) and key in existing:values[key]=existing[key]
                elif self.settings.supports(schema,key):values[key]=self.settings.default(schema,key)
            if values:complete[schema]=values
        result["settings"]=complete
        defaults={"wallpaper":False,"background_color":"#101820","panel_color":"#16161A","panel_color2":"#303044","panel_gradient_enabled":False,"panel_gradient_direction":"horizontal","panel_text_color":"#FFFFFF","panel_opacity":1.0,"panel_radius":0};existing=result.get("resource",{});result["resource"]={**defaults,**(existing if isinstance(existing,dict) else {})}
        try:result["monitors"]=(Path.home()/".config/monitors.xml").read_text()
        except OSError:result.setdefault("monitors","")
        return result
    def _save_current_worker(self,manifest,assets,target):
        try:
            archive=export_theme(manifest,assets,target);directory=import_theme(archive);GLib.idle_add(self._add_theme,directory);GLib.idle_add(self.toast,f"Saved {manifest['name']} as a reusable theme")
        except Exception as exc:GLib.idle_add(self.toast,str(exc))
    def _done(self,dialog,result):
        try:path=Path(dialog.open_finish(result).get_path());threading.Thread(target=self._import_worker,args=(path,),daemon=True).start()
        except GLib.Error:pass
        except Exception as exc:self.toast(str(exc))
    def _import_worker(self,path):
        try:
            directory=import_theme(path);manifest=json.loads((directory/"manifest.json").read_text(encoding="utf-8"));GLib.idle_add(self._add_theme,directory);GLib.idle_add(self.toast,"Theme imported")
            for warning in compatibility_warnings(manifest):GLib.idle_add(self.toast,warning)
        except Exception as exc:GLib.idle_add(self.toast,str(exc))
    def _add_theme(self,directory,group=None):
        try:manifest=json.loads((directory/"manifest.json").read_text())
        except Exception:return
        local=group is None;key=str(directory.resolve())
        if local and key in self._theme_rows:self.group.remove(self._theme_rows[key])
        row=Adw.ActionRow(title=manifest.get("name","Unnamed Theme"),subtitle=f"by {manifest.get('author','Unknown')}")
        if self.apply_theme:
            button=Gtk.Button(label="Apply Theme",valign=Gtk.Align.CENTER,css_classes=["suggested-action"]);button.connect("clicked",lambda *_:self.apply_theme(directory));row.add_suffix(button)
        if local:
            delete=Gtk.Button(icon_name="user-trash-symbolic",tooltip_text="Delete Theme",valign=Gtk.Align.CENTER,css_classes=["destructive-action"]);delete.connect("clicked",lambda *_:self._confirm_delete(directory,row,key));row.add_suffix(delete);self._theme_rows[key]=row
        (group or self.group).add(row)
        return GLib.SOURCE_REMOVE
    def _confirm_delete(self,directory,row,key):
        dialog=Adw.AlertDialog(heading=f"Delete {row.get_title()}?",body="This removes the imported local copy of the theme. A separately exported .gctheme file is not removed.");dialog.add_response("cancel","Cancel");dialog.add_response("delete","Delete");dialog.set_response_appearance("delete",Adw.ResponseAppearance.DESTRUCTIVE);dialog.set_default_response("cancel");dialog.set_close_response("cancel");dialog.connect("response",lambda _,response:self._delete(directory,row,key) if response=="delete" else None);dialog.present(self.get_root())
    def _delete(self,directory,row,key):threading.Thread(target=self._delete_worker,args=(directory,row,key),daemon=True).start()
    def _delete_worker(self,directory,row,key):
        try:delete_theme(directory);GLib.idle_add(self._deleted,row,key)
        except Exception as exc:GLib.idle_add(self.toast,str(exc))
    def _deleted(self,row,key):
        if self._theme_rows.get(key) is row:self._theme_rows.pop(key,None);self.group.remove(row)
        self.toast("Theme deleted");return GLib.SOURCE_REMOVE
