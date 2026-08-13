from __future__ import annotations

import base64, re, threading
from copy import deepcopy
from pathlib import Path
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango
from PIL import Image
from .backend.constants import ASSETS_DIR
from .backend.assets import copy_managed_image, remove_managed_images
from .backend.app_theme import ApplicationThemeManager
from .backend.login_theme import clear_login_theme_snapshot, remember_applied_login_theme
from .backend.transactions import Change
from .backend.settings import SettingsBackend, yaru_theme_for_accent
from .backend.state import StateStore
from .backend.transactions import ChangeManager, TransactionError
from .backend.system_proxy import SystemHelperProxy
from .backend.themes import DESKTOP_THEME_SETTINGS, DOCK_THEME_SETTINGS, SHELL_SURFACE_SETTINGS, validate_manifest
from .backend.wallpaper import wallpaper_keys
from .pages.preferences import PreferencesFactory
from .pages.themes import ThemesPage
from .pages.status import StatusPage
from .color import color_button, css_rgba, hex_color

class CustomizerWindow(Adw.ApplicationWindow):
    def __init__(self,app):
        super().__init__(application=app,title="GNOME Customizer",default_width=950,default_height=700,width_request=720,height_request=520)
        self.add_css_class("gnome-customizer-window")
        self.settings=SettingsBackend();self.state=StateStore();self._migrate_native_theme_ownership();self._migrate_shell_surface_ownership();self.changes=ChangeManager(self.settings,self.state);self.app_theme=ApplicationThemeManager(self.state);self.helper=SystemHelperProxy();self.gdm_pending={};self.gdm_resource={};self.gdm_assets={}
        self._theme_cache={}
        self.toast_overlay=Adw.ToastOverlay();self.set_content(self.toast_overlay);root=Gtk.Box(orientation=Gtk.Orientation.VERTICAL);self.toast_overlay.set_child(root)
        header=Adw.HeaderBar();root.append(header);self.mode=Adw.ViewSwitcher();self.mode_stack=Adw.ViewStack();self.mode.set_stack(self.mode_stack);header.set_title_widget(self.mode);menu=Gio.Menu();menu.append("About GNOME Customizer","app.about");header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic",menu_model=menu,tooltip_text="Main Menu"))
        self.mode_stack.add_titled_with_icon(Gtk.Box(),"desktop","Desktop","video-display-symbolic");self.mode_stack.add_titled_with_icon(Gtk.Box(),"login","Login Screen","system-lock-screen-symbolic")
        body=Adw.OverlaySplitView(vexpand=True);self.body=body;body.set_min_sidebar_width(190);body.set_max_sidebar_width(240);body.set_sidebar_width_fraction(.23);root.append(body);sidebar_toggle=Gtk.Button(icon_name="sidebar-show-symbolic",tooltip_text="Show Navigation");sidebar_toggle.connect("clicked",lambda *_:body.set_show_sidebar(not body.get_show_sidebar()));header.pack_start(sidebar_toggle)
        breakpoint=Adw.Breakpoint.new(Adw.BreakpointCondition.new_length(Adw.BreakpointConditionLengthType.MAX_WIDTH,800,Adw.LengthUnit.PX));breakpoint.add_setter(body,"collapsed",True);breakpoint.add_setter(body,"show-sidebar",False);self.add_breakpoint(breakpoint)
        sidebar=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=6);sidebar.set_margin_top(12);sidebar.set_margin_bottom(12);sidebar.set_margin_start(12);sidebar.set_margin_end(12);body.set_sidebar(sidebar)
        self.nav=Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE,css_classes=["navigation-sidebar"]);self.nav.connect("row-selected",self._navigate);sidebar.append(Gtk.ScrolledWindow(child=self.nav,vexpand=True,hscrollbar_policy=Gtk.PolicyType.NEVER))
        self.content=Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE);body.set_content(self.content)
        self.factory=PreferencesFactory(self.settings,self.changes,self._stage_gdm);self._build_pages();self.mode_stack.connect("notify::visible-child-name",lambda *_:self._fill_nav())
        action=Gtk.Box(spacing=10,halign=Gtk.Align.END);self.action_box=action;action.set_margin_top(9);action.set_margin_bottom(9);action.set_margin_end(12);self.pending_label=Gtk.Label();discard=Gtk.Button(label="Discard");self.discard_button=discard;discard.connect("clicked",lambda *_:self._discard());self.apply=Gtk.Button(label="Apply",css_classes=["suggested-action"]);self.apply.connect("clicked",self._apply);action.append(self.pending_label);action.append(discard);action.append(self.apply);root.append(action)
        self.changes.listeners.append(self._pending);self._fill_nav();self._pending()
    def _migrate_shell_surface_ownership(self):
        """Turn off the old implicitly-enabled overview once; surfaces now require opt-in."""
        marker="shell_surface_opt_in_v1"
        if self.state.data.get(marker):return
        schema="io.github.gnomecustomizer.shell"
        if self.settings.supports(schema,"overview-enabled"):self.settings.set(schema,"overview-enabled",False)
        token=f"{schema}:overview-enabled"
        self.state.data.get("original",{}).get("shell",{}).pop(token,None)
        managed=self.state.data.get("managed",{}).get("shell",[])
        if token in managed:managed.remove(token)
        self.state.data[marker]=True;self.state.save()
    def _migrate_native_theme_ownership(self):
        """Repair the neutral-theme regression from 0.3.15 using GNOME's mapping."""
        marker="native_accent_ownership_v3"
        if self.state.data.get(marker):return
        schema="org.gnome.desktop.interface"
        dark=self.settings.get(schema,"color-scheme")=="prefer-dark"
        target=yaru_theme_for_accent(self.settings.get(schema,"accent-color"),dark)
        roots={"gtk-theme":Path("/usr/share/themes"),"icon-theme":Path("/usr/share/icons")}
        for key,root in roots.items():
            current=self.settings.get(schema,key)
            if current.startswith("Yaru") and target!=current and (root/target).is_dir():self.settings.set(schema,key,target)
        self.state.data[marker]=True;self.state.save()
    def toast(self,text):self.toast_overlay.add_toast(Adw.Toast(title=str(text),timeout=4))
    def _add(self,name,widget):self.content.add_named(widget,name)
    def _build_pages(self):
        self.desktop_pages=[("appearance","Appearance","preferences-desktop-wallpaper-symbolic"),("fonts","Fonts, Icons & Cursor","preferences-desktop-font-symbolic"),("themes","Themes","applications-graphics-symbolic"),("dock","Dock","view-app-grid-symbolic"),("blur","Blur","weather-fog-symbolic"),("topbar","Top Bar","preferences-system-time-symbolic"),("placement","Placement","view-grid-symbolic"),("input","Mouse & Touchpad","input-mouse-symbolic"),("keyboard","Keyboard","input-keyboard-symbolic"),("power","Power","battery-symbolic"),("night","Night Light","weather-clear-night-symbolic"),("desktop_displays","Displays","video-display-symbolic"),("sound","Sound","audio-volume-high-symbolic"),("system","Apply & Restore","edit-undo-symbolic"),("status","Status","dialog-information-symbolic")]
        self.login_pages=[("login","Appearance & Options","system-lock-screen-symbolic"),("login_top","Top Bar & Clock","preferences-system-time-symbolic"),("login_input","Mouse, Touchpad & Sound","input-mouse-symbolic"),("login_power","Power & Night Light","battery-symbolic"),("displays","Displays","video-display-symbolic"),("system","Apply & Restore","edit-undo-symbolic"),("status","Status","dialog-information-symbolic")]
        appearance=self.factory.desktop_appearance();self._extend_appearance(appearance);self._add("appearance",appearance);self._add("fonts",self._fonts_icons());self._add("themes",ThemesPage(self.toast,self._apply_theme,self.settings,self.state,self.helper));self._add("dock",self.factory.native_dock());self._add("blur",self.factory.shell("Blur","Blur"));topbar=self.factory.topbar();self._extend_topbar(topbar);self._add("topbar",topbar);self._add("placement",self.factory.placement());self._add("input",self.factory.mouse_touchpad());self._add("keyboard",self.factory.keyboard());self._add("power",self.factory.power());self._add("night",self.factory.night_light());self._add("desktop_displays",self._desktop_displays());sound=self.factory.sound();self._extend_sound(sound);self._add("sound",sound);login=self.factory.login();self._extend_login(login);self._add("login",login);self._add("login_top",self._login_top());login_input=self.factory.login_input();self._extend_sound(login_input,True);self._add("login_input",login_input);self._add("login_power",self.factory.login_power());self._add("displays",self._displays());self._add("system",self._restore_page());self._add("status",StatusPage(self.settings,self.helper,self._count))
    def _apply_theme(self,directory):
        if self._stage_theme(directory):self._apply()
    def _stage_theme(self,directory):
        try:
            import json
            files=set()
            for candidate in directory.rglob("*"):
                if candidate.is_symlink():raise ValueError("Theme files changed after import; symbolic links are not allowed")
                if candidate.is_file():files.add(candidate.relative_to(directory).as_posix())
            manifest=validate_manifest(json.loads((directory/"manifest.json").read_text(encoding="utf-8")),files);desktop=manifest.get("desktop",{})
            for key,(schema,setting) in DESKTOP_THEME_SETTINGS.items():
                if key in desktop and self.settings.supports(schema,setting):self.changes.stage(Change("desktop",schema,setting,desktop[key],f"Theme {key}"))
            if "color_scheme" in desktop and self.settings.supports("org.gnome.shell.ubuntu","color-scheme"):
                self.changes.stage(Change("desktop","org.gnome.shell.ubuntu","color-scheme",desktop["color_scheme"],"Theme Ubuntu color scheme"))
            for field,key in (("wallpaper","picture-uri"),("wallpaper_dark","picture-uri-dark")):
                if field in desktop:
                    source=self._theme_asset(directory,desktop[field]);mime=self._validate_image(source);dest=copy_managed_image(source,ASSETS_DIR,"theme-"+field,mime)
                    keys=(key,)
                    if field=="wallpaper" and "wallpaper_dark" not in desktop:
                        keys=wallpaper_keys(dark_override=False,supports_dark=self.settings.supports("org.gnome.desktop.background","picture-uri-dark"))
                    for target in keys:self.changes.stage(Change("desktop","org.gnome.desktop.background",target,dest.as_uri(),f"Theme {field}"))
            shell=manifest.get("shell",{});schema="io.github.gnomecustomizer.shell"
            if any(shell.get(surface,{}).get("enabled",True) for surface in ("panel","menus","overview") if shell.get(surface)):self._stage_extension(True,"gnome-customizer@io.github.gnomecustomizer")
            for surface,fields in SHELL_SURFACE_SETTINGS.items():
                for prop,key in fields.items():
                    if prop in shell.get(surface,{}) and self.settings.supports(schema,key):self.changes.stage(Change("shell",schema,key,shell[surface][prop],f"Theme {surface} {prop}"))
                legacy_color=shell.get(surface,{}).get("color1")
                if legacy_color and "color" not in shell[surface] and self.settings.supports(schema,fields["color"]):self.changes.stage(Change("shell",schema,fields["color"],legacy_color,f"Theme {surface} color"))
                if surface in {"panel","menus"} and shell.get(surface):
                    prefix="menu" if surface=="menus" else surface;gradient=shell[surface].get("background_type")=="gradient";self.changes.stage(Change("shell",schema,f"{prefix}-gradient-enabled",gradient,f"Theme {surface} gradient"))
                    if "gradient_angle" in shell[surface]:self.changes.stage(Change("shell",schema,f"{prefix}-gradient-direction","vertical" if 45<=shell[surface]["gradient_angle"]<=135 else "horizontal",f"Theme {surface} gradient direction"))
            dock=shell.get("dock",{});dock_schema="org.gnome.shell.extensions.dash-to-dock"
            if dock and self.settings.schema(dock_schema):
                for prop,key in DOCK_THEME_SETTINGS.items():
                    if prop in dock and not (prop == "indicator_style" and dock[prop] in {"none","dot","dash","line"}) and self.settings.supports(dock_schema,key):self.changes.stage(Change("shell",dock_schema,key,dock[prop],f"Theme dock {prop}"))
                # Version-1 themes exported before complete native Dock snapshots used these lossy aliases.
                if "color1" in dock and "color" not in dock and self.settings.supports(dock_schema,"background-color"):self.changes.stage(Change("shell",dock_schema,"background-color",dock["color1"],"Theme dock color"))
                if ("color" in dock or "color1" in dock) and "custom_color" not in dock and self.settings.supports(dock_schema,"custom-background-color"):self.changes.stage(Change("shell",dock_schema,"custom-background-color",True,"Theme dock color"))
                if "opacity" in dock and "transparency" not in dock and self.settings.supports(dock_schema,"transparency-mode"):self.changes.stage(Change("shell",dock_schema,"transparency-mode","FIXED","Theme dock transparency"))
                indicator={"dot":"DOTS","dash":"DASHES","line":"SOLID"}.get(dock.get("indicator_style"))
                if indicator and self.settings.supports(dock_schema,"running-indicator-style"):self.changes.stage(Change("shell",dock_schema,"running-indicator-style",indicator,"Theme dock indicator"))
            login=manifest.get("login",{})
            for role in ("wallpaper","logo"):
                if role in login:
                    path=self._theme_asset(directory,login[role]);mime=self._validate_image(path);self.gdm_assets[role]={"mime":mime,"data":base64.b64encode(path.read_bytes()).decode("ascii")}
                    if role=="wallpaper":self.gdm_resource["wallpaper"]=True;self.login_preview_picture.set_file(Gio.File.new_for_path(str(path)))
                    else:self._stage_gdm("org.gnome.login-screen","logo",f"/usr/local/share/gnome-customizer/assets/logo.{ {'image/png':'png','image/jpeg':'jpg','image/webp':'webp'}[mime] }");self.login_preview_logo.set_file(Gio.File.new_for_path(str(path)));self.login_preview_logo.set_visible(True)
            if "background_color" in login:
                self.gdm_resource["background_color"]=login["background_color"]
                if "wallpaper" not in login:self.gdm_resource["wallpaper"]=False
            for prop,key in (("color","panel_color"),("color1","panel_color"),("color2","panel_color2"),("text_color","panel_text_color"),("opacity","panel_opacity"),("corner_radius","panel_radius")):
                if prop in login.get("panel",{}):self.gdm_resource[key]=login["panel"][prop]
            if "gradient_angle" in login.get("panel",{}):self.gdm_resource["panel_gradient_direction"]="vertical" if 45<=login["panel"]["gradient_angle"]<=135 else "horizontal"
            if login.get("panel"):self.gdm_resource["panel_gradient_enabled"]=login["panel"].get("background_type")=="gradient"
            if "accent" in login:self._stage_gdm("org.gnome.desktop.interface","accent-color",login["accent"])
            self._update_login_preview();self._pending();return True
        except Exception as exc:self.toast(exc);return False
    @staticmethod
    def _theme_asset(directory,relative):
        path=directory/relative
        if path.is_symlink() or not path.is_file() or directory.resolve() not in path.resolve().parents:raise ValueError("Theme asset is missing or unsafe")
        return path
    def _themes(self,kind):
        if kind=="sound":roots=[Path.home()/".local/share/sounds",Path("/usr/local/share/sounds"),Path("/usr/share/sounds")]
        elif kind=="gtk":roots=[Path.home()/".local/share/themes",Path.home()/".themes",Path("/usr/local/share/themes"),Path("/usr/share/themes")]
        else:roots=[Path.home()/".local/share/icons",Path("/usr/local/share/icons"),Path("/usr/share/icons")]
        names=set()
        for root in roots:
            if root.is_dir():
                for child in root.iterdir():
                    if child.is_dir() and ((kind=="cursor" and (child/"cursors").is_dir()) or (kind=="gtk" and ((child/"gtk-3.0").is_dir() or (child/"gtk-4.0").is_dir())) or (kind in {"icon","sound"} and (child/"index.theme").is_file())):names.add(child.name)
        return sorted(names,key=str.casefold)
    def _theme_combo_async(self,group,title,kind,schema,key,gdm=False):
        if not gdm:self.changes.register_factory("desktop",schema,key)
        current=self.settings.default(schema,key) if gdm else self.settings.get(schema,key);model=Gtk.StringList.new([current]);row=Adw.ComboRow(title=title,model=model,selected=0);row._theme_values=[current];row._loading=True
        def selected(r,_):
            if r._loading:return
            index=r.get_selected()
            if index>=len(r._theme_values):return
            if gdm:self._stage_gdm(schema,key,r._theme_values[index])
            else:self.changes.stage(Change("desktop",schema,key,r._theme_values[index],title))
        row.connect("notify::selected",selected);group.add(row)
        def loaded(values):row._theme_values=values or [current];model.splice(0,model.get_n_items(),row._theme_values);row.set_selected(row._theme_values.index(current) if current in row._theme_values else 0);row._loading=False;return GLib.SOURCE_REMOVE
        if kind in self._theme_cache:loaded(self._theme_cache[kind])
        else:
            def worker():values=self._themes(kind);self._theme_cache[kind]=values;GLib.idle_add(loaded,values)
            threading.Thread(target=worker,daemon=True).start()
        return row
    def _extend_appearance(self,page):
        g=Adw.PreferencesGroup(title="Wallpaper",description="PNG, JPEG, or WebP files are copied into managed storage");page.add(g)
        self.desktop_preview=Gtk.Picture(height_request=180,can_shrink=True,content_fit=Gtk.ContentFit.COVER,css_classes=["card"]);g.add(self.desktop_preview)
        try:
            dark=self.settings.supports("org.gnome.desktop.background","picture-uri-dark") and self.settings.get("org.gnome.desktop.interface","color-scheme")=="prefer-dark"
            uri=self.settings.get("org.gnome.desktop.background","picture-uri-dark" if dark else "picture-uri")
            if uri:self.desktop_preview.set_file(Gio.File.new_for_uri(uri))
        except Exception:pass
        self.factory.combo(g,"Placement","org.gnome.desktop.background","picture-options");self.factory.combo(g,"Color Fill","org.gnome.desktop.background","color-shading-type");self.factory.color(g,"Primary Color","org.gnome.desktop.background","primary-color");self.factory.color(g,"Secondary Color","org.gnome.desktop.background","secondary-color")
        for title,key,dark in (("Wallpaper (Light and Dark)","picture-uri",False),("Dark Wallpaper Override","picture-uri-dark",True)):
            if not self.settings.supports("org.gnome.desktop.background",key):continue
            self.changes.register_factory("desktop","org.gnome.desktop.background",key)
            row=Adw.ActionRow(title=title,subtitle="Choose an image");default=Gtk.Button(icon_name="edit-undo-symbolic",tooltip_text="Use GNOME default",valign=Gtk.Align.CENTER);default.connect("clicked",lambda _,r=row,k=key,t=title:self._default_desktop_wallpaper(r,k,t));b=Gtk.Button(label="Choose Image",valign=Gtk.Align.CENTER);b.connect("clicked",lambda _,r=row,k=key,d=dark:self._choose_desktop_wallpaper(r,k,d));row.add_suffix(default);row.add_suffix(b);g.add(row)
    def _default_desktop_wallpaper(self,row,key,title):
        supports_dark=self.settings.supports("org.gnome.desktop.background","picture-uri-dark")
        keys=wallpaper_keys(dark_override=key=="picture-uri-dark",supports_dark=supports_dark)
        for target in keys:
            value=self.settings.reset_value("org.gnome.desktop.background",target);self.changes.stage(Change("desktop","org.gnome.desktop.background",target,value,title))
        row.set_subtitle("GNOME default")
        if key=="picture-uri":
            preview_key="picture-uri-dark" if supports_dark and self.settings.get("org.gnome.desktop.interface","color-scheme")=="prefer-dark" else "picture-uri"
            value=self.settings.reset_value("org.gnome.desktop.background",preview_key);self.desktop_preview.set_file(Gio.File.new_for_uri(value) if value else None)
    def _choose_desktop_wallpaper(self,row,key,dark):
        dialog=Gtk.FileDialog(title="Choose Wallpaper");dialog.open(self,None,lambda d,res:self._desktop_wallpaper_done(d,res,row,key,dark))
    def _desktop_wallpaper_done(self,dialog,result,row,key,dark):
        try:
            source=Path(dialog.open_finish(result).get_path());mime=self._validate_image(source);dest=copy_managed_image(source,ASSETS_DIR,"desktop-wallpaper-dark" if dark else "desktop-wallpaper",mime);row.set_subtitle(source.name)
            supports_dark=self.settings.supports("org.gnome.desktop.background","picture-uri-dark")
            for target in wallpaper_keys(dark_override=dark,supports_dark=supports_dark):self.changes.stage(Change("desktop","org.gnome.desktop.background",target,dest.as_uri(),row.get_title()))
            if not dark or self.settings.get("org.gnome.desktop.interface","color-scheme")=="prefer-dark":self.desktop_preview.set_file(Gio.File.new_for_path(str(dest)))
        except GLib.Error:pass
        except Exception as exc:self.toast(exc)
    def _validate_image(self,path):
        with Image.open(path) as image:
            if image.width>16384 or image.height>16384 or image.width*image.height>80_000_000:raise ValueError("The image dimensions are too large")
            image.verify();fmt=image.format
        mime={"PNG":"image/png","JPEG":"image/jpeg","WEBP":"image/webp"}.get(fmt)
        if not mime:raise ValueError("Choose a PNG, JPEG, or WebP image")
        return mime
    def _fonts_icons(self):
        p=Adw.PreferencesPage(title="Fonts, Icons & Cursor");g=Adw.PreferencesGroup(title="Installed Themes");p.add(g)
        for title,key,kind in (("GTK Theme (legacy applications)","gtk-theme","gtk"),("Icon Theme","icon-theme","icon"),("Cursor Theme","cursor-theme","cursor")):
            if self.settings.supports("org.gnome.desktop.interface",key):self._theme_combo_async(g,title,kind,"org.gnome.desktop.interface",key)
        g=Adw.PreferencesGroup(title="Typography");p.add(g)
        if self.settings.supports("org.gnome.desktop.interface","font-name"):
            self.changes.register_factory("desktop","org.gnome.desktop.interface","font-name")
            row=Adw.ActionRow(title="Interface Font");button=Gtk.FontDialogButton.new(Gtk.FontDialog());button.set_font_desc(Pango.FontDescription.from_string(self.settings.get("org.gnome.desktop.interface","font-name")));button.connect("notify::font-desc",lambda b,_:self.changes.stage(Change("desktop","org.gnome.desktop.interface","font-name",b.get_font_desc().to_string(),"Interface Font")));row.add_suffix(button);g.add(row)
        for title,key in (("Antialiasing","font-antialiasing"),("Hinting","font-hinting")):self.factory.combo(g,title,"org.gnome.desktop.interface",key)
        return p
    def _extend_sound(self,page,gdm=False):
        if not self.settings.supports("org.gnome.desktop.sound","theme-name"):return
        g=Adw.PreferencesGroup(title="Installed Sound Theme");page.add(g);self._theme_combo_async(g,"Sound Theme","sound","org.gnome.desktop.sound","theme-name",gdm)
    def _extend_topbar(self,page):
        g=Adw.PreferencesGroup(title="Panel Appearance",description="Off leaves GNOME Shell fully in control of light and dark appearance");page.add(g);schema="io.github.gnomecustomizer.shell";self.factory.switch(g,"Enable Custom Panel Appearance",schema,"panel-enabled",domain="shell");self.factory.color(g,"Background Color",schema,"panel-color");self.factory.switch(g,"Gradient",schema,"panel-gradient-enabled",domain="shell");self.factory.color(g,"Gradient End Color",schema,"panel-color2");self.factory.combo(g,"Gradient Direction",schema,"panel-gradient-direction",domain="shell");self.factory.spin(g,"Opacity",schema,"panel-opacity",0,1,.01,domain="shell");self.factory.spin(g,"Corner Radius",schema,"panel-radius",0,32,domain="shell");self.factory.color(g,"Text Color",schema,"panel-text-color")
    def _stage_extension(self,on,uuid):
        enabled=list(self.settings.get("org.gnome.shell","enabled-extensions"));
        if on and uuid not in enabled:enabled.append(uuid)
        if not on and uuid in enabled:enabled.remove(uuid)
        self.changes.stage(Change("shell","org.gnome.shell","enabled-extensions",enabled,"Shell Companion"))
        if on and self.settings.supports("org.gnome.shell","disable-user-extensions"):
            self.changes.stage(Change("shell","org.gnome.shell","disable-user-extensions",False,"Shell Extensions"))
        if on and self.settings.supports("org.gnome.shell","disabled-extensions"):
            disabled=[item for item in self.settings.get("org.gnome.shell","disabled-extensions") if item!=uuid]
            self.changes.stage(Change("shell","org.gnome.shell","disabled-extensions",disabled,"Shell Companion"))
    def _extend_login(self,page):
        preview=Adw.PreferencesGroup(title="Login Screen Preview",description="A safe approximation; log out to see the compositor-rendered result");page.add(preview);self.login_preview=Gtk.Overlay(height_request=240,css_classes=["card"]);self.login_preview.set_name("login-live-preview");self.login_preview_picture=Gtk.Picture(can_shrink=True,content_fit=Gtk.ContentFit.COVER);self.login_preview.set_child(self.login_preview_picture);bar=Gtk.Label(label="Aug 11   10:30",height_request=38,halign=Gtk.Align.FILL,valign=Gtk.Align.START);bar.set_name("login-live-bar");self.login_preview.add_overlay(bar);card=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8,halign=Gtk.Align.CENTER,valign=Gtk.Align.CENTER,width_request=260,css_classes=["card"]);self.login_preview_logo=Gtk.Picture(width_request=72,height_request=48,can_shrink=True,content_fit=Gtk.ContentFit.CONTAIN);self.login_preview_logo.set_visible(False);card.append(self.login_preview_logo);card.append(Gtk.Image.new_from_icon_name("avatar-default-symbolic"));self.login_preview_banner=Gtk.Label(label="Welcome",css_classes=["title-2"]);card.append(self.login_preview_banner);card.append(Gtk.Entry(placeholder_text="Password",sensitive=False));self.login_preview.add_overlay(card);preview.add(self.login_preview);self._login_preview_provider=Gtk.CssProvider();Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(),self._login_preview_provider,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION);self._update_login_preview()
        options=Adw.PreferencesGroup(title="Login Options",description="Behavioral options are never stored in themes");page.add(options);self.factory.gdm_switch(options,"Welcome Message","org.gnome.login-screen","banner-message-enable");self.factory.gdm_switch(options,"Hide User List","org.gnome.login-screen","disable-user-list");self.factory.gdm_switch(options,"Hide Restart and Shutdown","org.gnome.login-screen","disable-restart-buttons");self.factory.gdm_switch(options,"Fingerprint Authentication","org.gnome.login-screen","enable-fingerprint-authentication")
        accessibility=Adw.PreferencesGroup(title="Accessibility");page.add(accessibility);self.factory.gdm_switch(accessibility,"Always Show Accessibility Menu","org.gnome.desktop.a11y","always-show-universal-access-status")
        style=Adw.PreferencesGroup(title="Style and Typography");page.add(style);self.factory.gdm_combo(style,"Accent Color","org.gnome.desktop.interface","accent-color");self.factory.gdm_entry(style,"Interface Font","org.gnome.desktop.interface","font-name");self.factory.gdm_spin(style,"Text Scaling","org.gnome.desktop.interface","text-scaling-factor",.5,3,.05);self.factory.gdm_spin(style,"Cursor Size","org.gnome.desktop.interface","cursor-size",8,128)
        for title,key,kind in (("Icon Theme","icon-theme","icon"),("Cursor Theme","cursor-theme","cursor")):
            if self.settings.supports("org.gnome.desktop.interface",key):self._theme_combo_async(style,title,kind,"org.gnome.desktop.interface",key,True)
        g=Adw.PreferencesGroup(title="Wallpaper and Logo");page.add(g)
        for title,role in (("Login Wallpaper","wallpaper"),("Login Logo","logo")):
            row=Adw.ActionRow(title=title,subtitle="No image selected");default=Gtk.Button(icon_name="edit-undo-symbolic",tooltip_text="Use GNOME default",valign=Gtk.Align.CENTER);default.connect("clicked",lambda _,r=row,role=role:self._default_gdm_image(r,role));b=Gtk.Button(label="Choose Image",valign=Gtk.Align.CENTER);b.connect("clicked",lambda _,r=row,role=role:self._choose_gdm_image(r,role));row.add_suffix(default);row.add_suffix(b);g.add(row)
        banner=Adw.EntryRow(title="Welcome Message");banner.connect("notify::text",lambda r,_:self._stage_gdm("org.gnome.login-screen","banner-message-text",r.get_text()));g.add(banner)
        colors=Adw.PreferencesGroup(title="Controlled Appearance");page.add(colors)
        gradient=Adw.SwitchRow(title="Top Bar Gradient");gradient.connect("notify::active",lambda r,_:self._stage_resource("panel_gradient_enabled",r.get_active()));colors.add(gradient)
        for title,key,initial in (("Background Color","background_color","#101820"),("Top Bar Color","panel_color","#16161A"),("Top Bar Gradient End","panel_color2","#303044"),("Top Bar Text","panel_text_color","#FFFFFF")):
            row=Adw.ActionRow(title=title);button=color_button(initial,title);button.connect("notify::rgba",lambda b,_,k=key:self._stage_resource(k,hex_color(b.get_rgba())));row.add_suffix(button);row.set_activatable_widget(button);colors.add(row)
        direction=Adw.ComboRow(title="Top Bar Gradient Direction",model=Gtk.StringList.new(["Horizontal","Vertical"]));direction.connect("notify::selected",lambda r,_:self._stage_resource("panel_gradient_direction",("horizontal","vertical")[r.get_selected()]));colors.add(direction)
        opacity=Adw.SpinRow.new_with_range(0,1,.01);opacity.set_title("Top Bar Opacity");opacity.set_value(1);opacity.connect("notify::value",lambda r,_:self._stage_resource("panel_opacity",r.get_value()));colors.add(opacity)
        radius=Adw.SpinRow.new_with_range(0,32,1);radius.set_title("Top Bar Corner Radius");radius.connect("notify::value",lambda r,_:self._stage_resource("panel_radius",int(r.get_value())));colors.add(radius)
    def _choose_gdm_image(self,row,role):Gtk.FileDialog(title=row.get_title()).open(self,None,lambda d,res:self._gdm_image_done(d,res,row,role))
    def _default_gdm_image(self,row,role):
        self.gdm_assets.pop(role,None);row.set_subtitle("GNOME default")
        if role=="wallpaper":self.gdm_resource["wallpaper"]=False;self.login_preview_picture.set_file(None)
        else:self._stage_gdm("org.gnome.login-screen","logo","");self.login_preview_logo.set_visible(False);self.login_preview_logo.set_file(None)
        self._pending()
    def _gdm_image_done(self,dialog,result,row,role):
        try:
            path=Path(dialog.open_finish(result).get_path());mime=self._validate_image(path);self.gdm_assets[role]={"mime":mime,"data":base64.b64encode(path.read_bytes()).decode("ascii")};row.set_subtitle(path.name)
            if role=="wallpaper":self.gdm_resource["wallpaper"]=True
            else:self._stage_gdm("org.gnome.login-screen","logo",f"/usr/local/share/gnome-customizer/assets/logo.{ {'image/png':'png','image/jpeg':'jpg','image/webp':'webp'}[mime] }")
            (self.login_preview_picture if role=="wallpaper" else self.login_preview_logo).set_file(Gio.File.new_for_path(str(path)))
            if role=="logo":self.login_preview_logo.set_visible(True)
            self._pending()
        except GLib.Error:pass
        except Exception as exc:self.toast(exc)
    def _stage_resource(self,key,value):
        self.gdm_resource[key]=value
        if key=="background_color":self.gdm_resource["wallpaper"]=False;self.login_preview_picture.set_file(None)
        self._update_login_preview();self._pending()
    def _stage_resource_color(self,row,key):
        if re.fullmatch(r"#[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?",row.get_text()):row.remove_css_class("error");self._stage_resource(key,row.get_text())
        else:row.add_css_class("error")
    def _update_login_preview(self):
        if not hasattr(self,"_login_preview_provider"):return
        background=self.gdm_resource.get("background_color","#101820");panel=self.gdm_resource.get("panel_color","#16161A");end=self.gdm_resource.get("panel_color2","#303044");text=self.gdm_resource.get("panel_text_color","#FFFFFF");opacity=self.gdm_resource.get("panel_opacity",1);radius=self.gdm_resource.get("panel_radius",0)
        panel_bg=f"linear-gradient(to right,{css_rgba(panel,opacity)},{css_rgba(end,opacity)})" if self.gdm_resource.get("panel_gradient_enabled",False) else css_rgba(panel,opacity)
        try:self._login_preview_provider.load_from_string(f"#login-live-preview{{background:{background};}} #login-live-bar{{background:{panel_bg};color:{text};border-radius:{radius}px;}}")
        except GLib.Error:pass
    def _login_top(self):
        p=Adw.PreferencesPage(title="Login Screen Top Bar");g=Adw.PreferencesGroup(title="Clock");p.add(g)
        self.factory.gdm_combo(g,"Clock Format","org.gnome.desktop.interface","clock-format",{"12h":"12-hour","24h":"24-hour"})
        for title,key in (("Show Date","clock-show-date"),("Show Weekday","clock-show-weekday"),("Show Seconds","clock-show-seconds"),("Battery Percentage","show-battery-percentage")):
            r=Adw.SwitchRow(title=title);r.connect("notify::active",lambda row,_,k=key:self._stage_gdm("org.gnome.desktop.interface",k,row.get_active()));g.add(r)
        return p
    def _displays(self):
        p=Adw.PreferencesPage(title="Displays");g=Adw.PreferencesGroup(title="Login Screen Layout",description="Copies the current user layout without changing the active session");p.add(g);r=Adw.ActionRow(title="Apply My Current Display Layout",subtitle="Source: ~/.config/monitors.xml");b=Gtk.Button(label="Stage",valign=Gtk.Align.CENTER);b.connect("clicked",lambda *_:self._stage_monitors());r.add_suffix(b);g.add(r);r=Adw.ActionRow(title="Restore Previous Login Screen Layout",subtitle="Restores the configuration captured before the first Customizer change");b=Gtk.Button(label="Restore",valign=Gtk.Align.CENTER);b.connect("clicked",lambda *_:self._restore_monitors());r.add_suffix(b);g.add(r);return p
    def _restore_monitors(self):
        try:self.helper.call("RestoreMonitorConfiguration");self.toast("Previous login-screen display layout restored")
        except Exception as exc:self.toast(exc)
    def _desktop_displays(self):
        p=Adw.PreferencesPage(title="Displays",description="Monitor arrangement remains owned by GNOME's display service");g=Adw.PreferencesGroup(title="Connected Displays");p.add(g)
        monitors=Gdk.Display.get_default().get_monitors()
        for i in range(monitors.get_n_items()):
            monitor=monitors.get_item(i);geometry=monitor.get_geometry();g.add(Adw.ActionRow(title=monitor.get_description() or f"Display {i+1}",subtitle=f"{geometry.width} × {geometry.height} at {round(monitor.get_scale_factor()*100)}%"))
        actions=Adw.PreferencesGroup(title="Arrangement and Resolution",description="GNOME Settings provides the compositor-owned confirmation and rollback flow");p.add(actions);row=Adw.ActionRow(title="Open GNOME Display Settings",subtitle="Arrange monitors, choose resolution, refresh rate, scaling, and orientation");button=Gtk.Button(label="Open Displays",valign=Gtk.Align.CENTER);button.connect("clicked",lambda *_:self._open_display_settings());row.add_suffix(button);actions.add(row);return p
    def _open_display_settings(self):
        try:Gio.Subprocess.new(["gnome-control-center","display"],Gio.SubprocessFlags.NONE)
        except GLib.Error as exc:self.toast(exc.message)
    def _restore_page(self):
        p=Adw.PreferencesPage(title="Apply & Restore",description="Restoration only touches values and files managed by GNOME Customizer");g=Adw.PreferencesGroup(title="Restore Pre-Customizer State");p.add(g)
        for title,subtitle,callback in (("Restore Desktop Appearance","Returns settings captured before their first change",lambda:self._restore_domain("desktop")),("Restore Application Theme","Removes only the managed GTK3/GTK4 CSS block",self._restore_application_theme),("Restore Shell Appearance","Restores companion settings without touching other extensions",lambda:self._restore_domain("shell")),("Restore Login Screen Appearance","Removes the owned dconf, resource, assets, and display state",self._restore_login),("Restore All GNOME Customizer Changes","Restores all four scopes",self._restore_all)):
            row=Adw.ActionRow(title=title,subtitle=subtitle);button=Gtk.Button(label="Restore",valign=Gtk.Align.CENTER,css_classes=["destructive-action"]);button.connect("clicked",lambda _,cb=callback,t=title:self._confirm_restore(t,cb));row.add_suffix(button);g.add(row)
        g=Adw.PreferencesGroup(title="Ubuntu Factory Defaults",description="Resets every setting exposed by this app, including changes made by other customization tools");p.add(g);row=Adw.ActionRow(title="Reset Everything to Ubuntu Defaults",subtitle="Restores Yaru, stock wallpapers and GDM, and removes user GTK CSS");button=Gtk.Button(label="Factory Reset",valign=Gtk.Align.CENTER,css_classes=["destructive-action"]);button.connect("clicked",lambda *_:self._confirm_defaults());row.add_suffix(button);g.add(row);return p
    def _confirm_restore(self,title,callback):
        dialog=Adw.AlertDialog(heading=title,body="Only GNOME Customizer-owned changes in this scope will be restored.");dialog.add_response("cancel","Cancel");dialog.add_response("restore","Restore");dialog.set_response_appearance("restore",Adw.ResponseAppearance.DESTRUCTIVE);dialog.set_default_response("cancel");dialog.set_close_response("cancel");dialog.connect("response",lambda _,response:callback() if response=="restore" else None);dialog.present(self)
    def _restore_domain(self,domain):
        try:self.toast(f"Restored {self.changes.restore(domain)} {domain} settings")
        except Exception as exc:self.toast(exc)
    def _restore_login(self):
        try:self.helper.call("RestoreGdmDefaults");clear_login_theme_snapshot(self.state);self.gdm_pending.clear();self.gdm_resource.clear();self.gdm_assets.clear();self.__dict__.pop("monitor_xml",None);self._pending();self.toast("Login screen restored. Reboot before checking the login screen.")
        except Exception as exc:self.toast(exc)
    def _restore_application_theme(self):
        try:self.toast(f"Removed application theme from {self.app_theme.restore()} GTK configuration files. Reopen applications to see the change.")
        except Exception as exc:self.toast(exc)
    def _restore_all(self):self._restore_domain("desktop");self._restore_application_theme();self._restore_domain("shell");self._restore_login()
    def _confirm_defaults(self):
        dialog=Adw.AlertDialog(heading="Reset Everything to Ubuntu Defaults",body="Every desktop, Shell, dock, application, wallpaper, display, and login-screen setting exposed here will be reset, even if another program changed it. User GTK CSS and local GDM overrides will be removed. Unrelated files and settings outside this app's scope are preserved.");dialog.add_response("cancel","Cancel");dialog.add_response("reset","Factory Reset");dialog.set_response_appearance("reset",Adw.ResponseAppearance.DESTRUCTIVE);dialog.set_default_response("cancel");dialog.set_close_response("cancel");dialog.connect("response",lambda _,response:self._reset_defaults() if response=="reset" else None);dialog.present(self)
    def _reset_defaults(self):
        try:
            self.helper.call("RestoreGdmDefaults",{"factory":True})
            clear_login_theme_snapshot(self.state)
            count=self.changes.reset_factory(("desktop","shell"));files=self.app_theme.reset_factory();images=remove_managed_images(ASSETS_DIR)
            self.changes.discard();self.gdm_pending.clear();self.gdm_resource.clear();self.gdm_assets.clear();self.__dict__.pop("monitor_xml",None);self._pending()
            self.toast(f"Reset {count} settings, {files} application theme files, and {images} managed wallpapers. Reboot before checking the login screen.")
        except Exception as exc:self.toast(f"Could not reset all customizations: {exc}")
    def _fill_nav(self):
        while child:=self.nav.get_first_child():self.nav.remove(child)
        pages=self.desktop_pages if self.mode_stack.get_visible_child_name()=="desktop" else self.login_pages
        for name,title,icon in pages:
            row=Gtk.ListBoxRow();row.page_name=name;box=Gtk.Box(spacing=10);box.append(Gtk.Image.new_from_icon_name(icon));box.append(Gtk.Label(label=title,xalign=0));row.set_child(box);self.nav.append(row)
        self.nav.select_row(self.nav.get_row_at_index(0))
    def _navigate(self,box,row):
        if row:
            self.content.set_visible_child_name(row.page_name)
            if self.body.get_collapsed():self.body.set_show_sidebar(False)
    def _stage_gdm(self,schema,key,value):
        self.gdm_pending.setdefault(schema,{})[key]=value
        if key=="banner-message-text" and hasattr(self,"login_preview_banner"):self.login_preview_banner.set_label(value or "Welcome")
        self._pending()
    def _stage_monitors(self):
        try:self.monitor_xml=(Path.home()/".config/monitors.xml").read_text();self.toast("Display layout staged");self._pending()
        except OSError:self.toast("The current display configuration could not be read")
    def _count(self):return len(self.changes.pending)+sum(len(v) for v in self.gdm_pending.values())+(1 if hasattr(self,"monitor_xml") else 0)+len(self.gdm_resource)+len(self.gdm_assets)
    def _pending(self):
        count=self._count();self.pending_label.set_label(f"{count} pending change{'s' if count!=1 else ''}");self.apply.set_sensitive(count>0)
    def _discard(self):self.changes.discard();self.gdm_pending.clear();self.gdm_resource.clear();self.gdm_assets.clear();self.__dict__.pop("monitor_xml",None);self._pending();self.toast("Pending changes discarded")
    def _apply(self,*_):
        pending_before=dict(self.changes.pending);state_before=deepcopy(self.state.data);old_values={};desktop_applied=False
        try:
            for change in pending_before.values():old_values[(change.schema,change.key)]=self.settings.get(change.schema,change.key)
            desktop=self.changes.apply() if self.changes.pending else 0;desktop_applied=desktop>0
            transaction={}
            if self.gdm_assets:transaction["assets"]=self.gdm_assets
            if self.gdm_resource:transaction["resource"]=self.gdm_resource
            if self.gdm_pending:transaction["settings"]=self.gdm_pending
            if hasattr(self,"monitor_xml"):transaction["monitors"]=self.monitor_xml
            context=(pending_before,state_before,old_values,desktop_applied,desktop,transaction)
            if transaction:
                self.body.set_sensitive(False);self.apply.set_sensitive(False);self.discard_button.set_sensitive(False);self.apply.set_label("Applying…");threading.Thread(target=self._apply_worker,args=(transaction,context),daemon=True).start();return
            self._apply_success(context)
        except Exception as exc:
            self._apply_failure((pending_before,state_before,old_values,desktop_applied,0,{}),exc)
    def _apply_worker(self,transaction,context):
        try:self.helper.call("ApplyTransaction",transaction);GLib.idle_add(self._apply_success,context)
        except Exception as exc:GLib.idle_add(self._apply_failure,context,exc)
    def _apply_success(self,context):
        pending,_,_,_,desktop,transaction=context;privileged=bool(transaction);shell_changed=any(change.domain=="shell" for change in pending.values())
        try:remember_applied_login_theme(self.state,transaction)
        except Exception as exc:self.toast(f"Changes applied, but the login theme snapshot could not be saved: {exc}")
        self.gdm_pending.clear();self.gdm_resource.clear();self.gdm_assets.clear();self.__dict__.pop("monitor_xml",None);self._finish_apply();message="Changes applied. Log out or reboot to see login-screen changes." if privileged else ("Shell changes applied. Log out and back in if the companion was just installed." if shell_changed else f"Desktop appearance applied ({desktop} changes)");self.toast(message);return GLib.SOURCE_REMOVE
    def _apply_failure(self,context,exc):
        pending_before,state_before,old_values,desktop_applied,_,_=context
        if desktop_applied:
            for (schema,key),value in old_values.items():
                try:self.settings.set(schema,key,value)
                except Exception:pass
        if desktop_applied:
            self.state.data=state_before;self.state.save();self.changes.pending=pending_before;self.changes._notify()
        self._finish_apply();message=str(exc);self.toast(message)
        dialog=Adw.AlertDialog(heading="Changes could not be applied",body=message);dialog.add_response("close","Close");dialog.set_default_response("close");dialog.set_close_response("close");dialog.present(self);return GLib.SOURCE_REMOVE
    def _finish_apply(self):self.body.set_sensitive(True);self.discard_button.set_sensitive(True);self.apply.set_label("Apply");self._pending()
