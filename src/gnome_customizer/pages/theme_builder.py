from __future__ import annotations

import json, tempfile, threading
from pathlib import Path
import cairo
from gi.repository import Adw, Gdk, Gio, GLib, Gtk
from ..backend.themes import compatibility_warnings, export_theme, import_theme, ThemeError
from ..color import color_button, css_rgba, hex_color, rgba


class ThemeBuilderPage(Gtk.Box):
    def __init__(self, toast):
        super().__init__(orientation=Gtk.Orientation.VERTICAL,spacing=12);self.set_margin_top(12);self.set_margin_bottom(12);self.set_margin_start(12);self.set_margin_end(12);self._toast=toast;self.assets={};self._controls={};self._provider=Gtk.CssProvider()
        self.manifest={"format_version":1,"name":"My Theme","author":"","description":"","minimum_gnome":"50.1","maximum_tested_gnome":"50.x","desktop":{"color_scheme":"prefer-dark","accent":"blue"},"applications":{"window_color":"#18181C","view_color":"#111114","sidebar_color":"#202027","headerbar_color":"#24242C","card_color":"#292932","popover_color":"#2D2D37","dialog_color":"#24242C","text_color":"#F4F4F6","muted_text_color":"#B6B6C2","accent_color":"#3066D6","accent_text_color":"#FFFFFF","border_color":"#444451","corner_radius":12,"shadow_strength":.35},"shell":{"panel":{"color":"#16161A","opacity":.88,"blur":20,"text_color":"#FFFFFF"},"dock":{"color":"#202026","opacity":.82,"blur":24,"corner_radius":18,"icon_size":48,"spacing":8,"indicator_style":"dot"},"menus":{"color":"#202026","opacity":.94,"blur":16,"corner_radius":14,"text_color":"#FFFFFF"},"overview":{"color":"#18243A","opacity":.28,"blur":30,"brightness":.75,"saturation":.85}},"login":{"background_color":"#203050","accent":"blue"}}
        self._defaults=json.loads(json.dumps(self.manifest))
        toolbar=Gtk.Box(spacing=8);toolbar.append(Gtk.Label(label="Theme Builder",xalign=0,hexpand=True,css_classes=["title-1"]));
        for label,callback,style in (("Import for Editing",self._import,None),("Reset Preview",self._reset,None),("Save Draft",self._save,None),("Export Theme",self._export,"suggested-action")):
            button=Gtk.Button(label=label,css_classes=[style] if style else []);button.connect("clicked",callback);toolbar.append(button)
        self.append(toolbar);split=Gtk.Paned.new(Gtk.Orientation.HORIZONTAL);split.set_wide_handle(True);split.set_position(360);split.set_vexpand(True);self.append(split)
        editor=Adw.PreferencesPage();editor.set_size_request(330,-1);split.set_start_child(editor)
        details=self._group(editor,"Theme Details");self._entry(details,"Theme Name",("name",),"My Theme");self._entry(details,"Author",("author",),"");self._entry(details,"Description",("description",),"");self._entry(details,"Minimum GNOME",("minimum_gnome",),"50.1");self._entry(details,"Maximum Tested",("maximum_tested_gnome",),"50.x")
        general=self._group(editor,"General");self._combo(general,"Color Scheme",("desktop","color_scheme"),["default","prefer-light","prefer-dark"],"prefer-dark");self._combo(general,"Accent",("desktop","accent"),["blue","teal","green","yellow","orange","red","pink","purple","slate","brown"],"blue");self._entry(general,"GTK Theme",("desktop","gtk_theme"),"");self._entry(general,"Icon Theme",("desktop","icons"),"");self._entry(general,"Cursor Theme",("desktop","cursor"),"");self._asset(general,"Desktop Wallpaper",("desktop","wallpaper"),"desktop-wallpaper");self._asset(general,"Dark Wallpaper",("desktop","wallpaper_dark"),"desktop-wallpaper-dark")
        apps=self._group(editor,"Application Preview Metadata", "Preview/export data only; GNOME Settings controls installed applications")
        for title,key,default in (("Window","window_color","#18181C"),("Content View","view_color","#111114"),("Sidebar","sidebar_color","#202027"),("Header Bar","headerbar_color","#24242C"),("Cards","card_color","#292932"),("Popovers &amp; Menus","popover_color","#2D2D37"),("Dialogs","dialog_color","#24242C"),("Text","text_color","#F4F4F6"),("Muted Text","muted_text_color","#B6B6C2"),("Selection","accent_color","#3066D6"),("Selected Text","accent_text_color","#FFFFFF"),("Borders","border_color","#444451")):self._entry(apps,title,("applications",key),default)
        self._spin(apps,"Corner Radius",("applications","corner_radius"),0,32,1,12);self._spin(apps,"Shadow Strength",("applications","shadow_strength"),0,1,.05,.35)
        panel=self._group(editor,"Top Bar");self._combo(panel,"Background",("shell","panel","background_type"),["solid","gradient"],"solid");self._entry(panel,"Background Color",("shell","panel","color"),"#16161A");self._entry(panel,"Gradient End",("shell","panel","color2"),"#303044");self._spin(panel,"Gradient Angle",("shell","panel","gradient_angle"),0,360,1,90);self._entry(panel,"Text Color",("shell","panel","text_color"),"#FFFFFF");self._spin(panel,"Opacity",("shell","panel","opacity"),.1,1,.01,.88);self._spin(panel,"Blur",("shell","panel","blur"),0,100,1,20);self._spin(panel,"Corner Radius",("shell","panel","corner_radius"),0,32,1,0)
        dock=self._group(editor,"Dock");self._combo(dock,"Background",("shell","dock","background_type"),["solid","gradient"],"solid");self._entry(dock,"Background Color",("shell","dock","color"),"#202026");self._entry(dock,"Gradient End",("shell","dock","color2"),"#303044");self._spin(dock,"Gradient Angle",("shell","dock","gradient_angle"),0,360,1,90);self._spin(dock,"Opacity",("shell","dock","opacity"),0,1,.01,.82);self._spin(dock,"Blur",("shell","dock","blur"),0,100,1,24);self._spin(dock,"Corner Radius",("shell","dock","corner_radius"),0,32,1,18);self._spin(dock,"Icon Size",("shell","dock","icon_size"),24,96,1,48);self._spin(dock,"Spacing",("shell","dock","spacing"),0,24,1,8);self._combo(dock,"Indicator",("shell","dock","indicator_style"),["dot","dash","line"],"dot")
        menus=self._group(editor,"Menus &amp; Popovers");self._combo(menus,"Background",("shell","menus","background_type"),["solid","gradient"],"solid");self._entry(menus,"Surface Color",("shell","menus","color"),"#202026");self._entry(menus,"Gradient End",("shell","menus","color2"),"#303044");self._spin(menus,"Gradient Angle",("shell","menus","gradient_angle"),0,360,1,90);self._entry(menus,"Text Color",("shell","menus","text_color"),"#FFFFFF");self._entry(menus,"Border Color",("shell","menus","border_color"),"#444452");self._spin(menus,"Opacity",("shell","menus","opacity"),.2,1,.01,.94);self._spin(menus,"Blur",("shell","menus","blur"),0,100,1,16);self._spin(menus,"Corner Radius",("shell","menus","corner_radius"),0,32,1,14)
        overview=self._group(editor,"Overview &amp; Blur");self._entry(overview,"Backdrop Tint",("shell","overview","color"),"#18243A");self._spin(overview,"Tint Opacity",("shell","overview","opacity"),0,1,.01,.28);self._spin(overview,"Blur",("shell","overview","blur"),0,100,1,30);self._spin(overview,"Brightness",("shell","overview","brightness"),.2,1.5,.05,.75);self._spin(overview,"Saturation",("shell","overview","saturation"),0,1,.05,.85)
        login=self._group(editor,"Login Screen");self._entry(login,"Background Color",("login","background_color"),"#203050");self._combo(login,"Accent",("login","accent"),["blue","teal","green","yellow","orange","red","pink","purple","slate","brown"],"blue");self._asset(login,"Wallpaper",("login","wallpaper"),"login-wallpaper");self._asset(login,"Logo",("login","logo"),"login-logo")
        preview_box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8,hexpand=True,vexpand=True);split.set_end_child(preview_box);self.preview_stack=Adw.ViewStack();self._preview_pictures={};self._preview_logos={};switcher=Adw.ViewSwitcher(stack=self.preview_stack,halign=Gtk.Align.FILL,hexpand=True);preview_box.append(switcher);preview_box.append(self.preview_stack);preview_box.append(Gtk.Label(label="Blur and transparency are approximated in the preview.",wrap=True,xalign=0,css_classes=["dim-label"]))
        for name,title in (("desktop","Desktop"),("apps","App Preview"),("overview","Overview"),("menus","Menus"),("login","Login")):self.preview_stack.add_titled(self._preview(name),name,title)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(),self._provider,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION);self._sync()
    def _group(self,page,title,description=""):group=Adw.PreferencesGroup(title=title,description=description);page.add(group);return group
    def _get(self,path,default=None):
        value=self.manifest
        for key in path:
            if not isinstance(value,dict) or key not in value:return default
            value=value[key]
        return value
    def _set(self,path,value):
        obj=self.manifest
        for key in path[:-1]:obj=obj.setdefault(key,{})
        if value=="" and len(path)>1:obj.pop(path[-1],None)
        else:obj[path[-1]]=value
        self._sync()
    def _entry(self,group,title,path,default):
        if isinstance(default,str) and default.startswith("#"):return self._color(group,title,path,default)
        row=Adw.EntryRow(title=title,text=str(self._get(path,default)));row.connect("notify::text",lambda r,_:self._set(path,r.get_text()))
        group.add(row);self._controls[path]=(row,lambda v:row.set_text(str(v)));return row
    def _color(self,group,title,path,default):
        row=Adw.ActionRow(title=title);button=color_button(self._get(path,default),title);button.connect("notify::rgba",lambda b,_:self._set(path,hex_color(b.get_rgba())));row.add_suffix(button);row.set_activatable_widget(button);group.add(row);self._controls[path]=(button,lambda v:button.set_rgba(rgba(v)));return row
    def _spin(self,group,title,path,low,high,step,default):
        row=Adw.SpinRow.new_with_range(low,high,step);row.set_title(title);row.set_value(float(self._get(path,default)));row.connect("notify::value",lambda r,_:self._set(path,int(r.get_value()) if step>=1 else round(r.get_value(),3)));group.add(row);self._controls[path]=(row,lambda v:row.set_value(float(v)));return row
    def _combo(self,group,title,path,values,default):
        row=Adw.ComboRow(title=title,model=Gtk.StringList.new([x.replace("-"," ").title() for x in values]));current=self._get(path,default);row.set_selected(values.index(current) if current in values else 0);row.connect("notify::selected",lambda r,_:self._set(path,values[r.get_selected()]));group.add(row);self._controls[path]=(row,lambda v:row.set_selected(values.index(v) if v in values else 0));return row
    def _asset(self,group,title,path,role):
        row=Adw.ActionRow(title=title,subtitle="No image selected");button=Gtk.Button(label="Choose Image",valign=Gtk.Align.CENTER);button.connect("clicked",lambda *_:Gtk.FileDialog(title=title).open(self.get_root(),None,lambda d,res:self._asset_done(d,res,row,path,role)));row.add_suffix(button);group.add(row);self._controls[path]=(row,lambda value:row.set_subtitle(Path(value).name if value else "No image selected"));return row
    def _asset_done(self,dialog,result,row,path,role):
        try:
            source=Path(dialog.open_finish(result).get_path());from PIL import Image
            with Image.open(source) as image:
                if image.width>16384 or image.height>16384 or image.width*image.height>80_000_000:raise ThemeError("The image dimensions are too large")
                image.verify();fmt=image.format
            ext={"PNG":".png","JPEG":".jpg","WEBP":".webp"}.get(fmt)
            if not ext:raise ThemeError("Choose a PNG, JPEG, or WebP image")
            name=f"assets/{role}{ext}";self.assets[name]=source;self._set(path,name);row.set_subtitle(source.name)
            if role in {"desktop-wallpaper","desktop-wallpaper-dark"}:self._preview_pictures["desktop"].set_file(Gio.File.new_for_path(str(source)))
            elif role=="login-wallpaper":self._preview_pictures["login"].set_file(Gio.File.new_for_path(str(source)))
            elif role=="login-logo":self._preview_logos["login"].set_file(Gio.File.new_for_path(str(source)));self._preview_logos["login"].set_visible(True)
        except GLib.Error:pass
        except Exception as exc:self._toast(exc)
    def _preview(self,mode):
        scene=Gtk.Overlay(hexpand=True,vexpand=True,css_classes=["card"]);scene.set_name(f"builder-{mode}");picture=Gtk.Picture(can_shrink=True,content_fit=Gtk.ContentFit.COVER);scene.set_child(picture);self._preview_pictures[mode]=picture;layer=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,hexpand=True,vexpand=True);scene.add_overlay(layer);bar=Gtk.Label(label="Aug 11   10:30",height_request=36);bar.set_name(f"builder-{mode}-bar");layer.append(bar);center=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12,halign=Gtk.Align.CENTER,valign=Gtk.Align.CENTER,vexpand=True)
        if mode=="apps":window=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,width_request=390,height_request=230);window.set_name("builder-app-window");header=Gtk.Label(label="Files — Home",height_request=38,xalign=.05);header.set_name("builder-app-header");window.append(header);content=Gtk.Box(vexpand=True);sidebar=Gtk.Label(label="Home\nDocuments\nDownloads\nPictures",width_request=125,xalign=.1,yalign=.1);sidebar.set_name("builder-app-sidebar");content.append(sidebar);view=Gtk.FlowBox(hexpand=True,homogeneous=True);view.set_name("builder-app-view");[view.insert(Gtk.Button(label=x),-1) for x in ("Documents","Pictures","Music","Videos")];content.append(view);window.append(content);center.append(window)
        elif mode=="overview":center.append(Gtk.Label(label="Overview",css_classes=["title-1"]));grid=Gtk.Grid(column_spacing=12,row_spacing=12);[grid.attach(Gtk.Button(icon_name="application-x-executable-symbolic"),i%4,i//4,1,1) for i in range(8)];center.append(grid)
        elif mode=="menus":popup=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8,width_request=260,css_classes=["card"]);popup.set_name("builder-popup");popup.append(Gtk.Label(label="Quick Settings",xalign=0,css_classes=["title-2"]));popup.append(Gtk.Switch(active=True,halign=Gtk.Align.START));popup.append(Gtk.Label(label="Selected item",xalign=0,css_classes=["accent"]));center.append(popup)
        elif mode=="login":card=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8,width_request=280,css_classes=["card"]);logo=Gtk.Picture(width_request=72,height_request=48,can_shrink=True,content_fit=Gtk.ContentFit.CONTAIN);logo.set_visible(False);self._preview_logos[mode]=logo;card.append(logo);card.append(Gtk.Image.new_from_icon_name("avatar-default-symbolic"));card.append(Gtk.Label(label="Welcome",css_classes=["title-2"]));card.append(Gtk.Entry(placeholder_text="Password"));center.append(card)
        else:app=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8,width_request=300,height_request=180,css_classes=["card"]);app.append(Gtk.Label(label="Example Application",css_classes=["title-2"]));app.append(Gtk.Label(label="Focused and selected states"));center.append(app)
        layer.append(center)
        if mode!="apps":dock=Gtk.Box(halign=Gtk.Align.CENTER,spacing=10);dock.set_name(f"builder-{mode}-dock");[dock.append(Gtk.Image.new_from_icon_name(x)) for x in ("org.gnome.Settings-symbolic","system-file-manager-symbolic","utilities-terminal-symbolic","web-browser-symbolic")];layer.append(dock)
        return scene
    def _sync(self):
        panel=self._get(("shell","panel"),{});dock=self._get(("shell","dock"),{});menus=self._get(("shell","menus"),{});overview=self._get(("shell","overview"),{});login=self._get(("login",),{});apps=self._get(("applications",),{})
        bg=lambda s:f"linear-gradient({s.get('gradient_angle',90)}deg,{css_rgba(s.get('color','#202026'),s.get('opacity',1))},{css_rgba(s.get('color2','#303044'),s.get('opacity',1))})" if s.get("background_type")=="gradient" else css_rgba(s.get("color","#202026"),s.get("opacity",1))
        radius=apps.get('corner_radius',12);css=f"#builder-desktop,#builder-overview,#builder-menus{{background:{css_rgba(overview.get('color','#263850'),overview.get('opacity',.28))};}} #builder-login{{background:{login.get('background_color','#203050')};}} #builder-desktop-bar,#builder-overview-bar,#builder-menus-bar,#builder-login-bar{{background:{bg(panel)};color:{panel.get('text_color','#FFFFFF')};border-radius:{panel.get('corner_radius',0)}px;}} #builder-desktop-dock,#builder-overview-dock,#builder-menus-dock,#builder-login-dock{{background:{bg(dock)};border-radius:{dock.get('corner_radius',18)}px;padding:10px;}} #builder-popup{{background:{bg(menus)};color:{menus.get('text_color','#FFFFFF')};border:1px solid {menus.get('border_color','#444452')};border-radius:{menus.get('corner_radius',14)}px;padding:18px;}} #builder-app-window{{background:{apps.get('window_color','#18181C')};color:{apps.get('text_color','#F4F4F6')};border:1px solid {apps.get('border_color','#444451')};border-radius:{radius}px;}} #builder-app-header{{background:{apps.get('headerbar_color','#24242C')};color:{apps.get('text_color','#F4F4F6')};}} #builder-app-sidebar{{background:{apps.get('sidebar_color','#202027')};color:{apps.get('muted_text_color','#B6B6C2')};padding:12px;}} #builder-app-view{{background:{apps.get('view_color','#111114')};padding:12px;}} #builder-app-view button{{background:{apps.get('card_color','#292932')};color:{apps.get('text_color','#F4F4F6')};border-radius:{radius}px;}}"
        try:self._provider.load_from_string(css)
        except GLib.Error:pass
    def _reset(self,*_):
        self.manifest=json.loads(json.dumps(self._defaults));self.assets={};[picture.set_file(None) for picture in self._preview_pictures.values()];[logo.set_visible(False) for logo in self._preview_logos.values()];self._load_controls();self._sync();self._toast("Preview reset")
    def _load_controls(self):
        for path,(_,setter) in self._controls.items():setter(self._get(path,self._value_from(self._defaults,path,"")))
    @staticmethod
    def _value_from(obj,path,default=None):
        for key in path:
            if not isinstance(obj,dict) or key not in obj:return default
            obj=obj[key]
        return obj
    def _import(self,*_):Gtk.FileDialog(title="Import Theme for Editing").open(self.get_root(),None,self._import_done)
    def _import_done(self,dialog,result):
        try:
            source=Path(dialog.open_finish(result).get_path());threading.Thread(target=self._import_edit_worker,args=(source,),daemon=True).start()
        except GLib.Error:pass
        except Exception as exc:self._toast(exc)
    def _import_edit_worker(self,source):
        try:
            directory=import_theme(source);manifest=json.loads((directory/"manifest.json").read_text());assets={}
            for path in (("preview",),("desktop","wallpaper"),("desktop","wallpaper_dark"),("login","wallpaper"),("login","logo")):
                name=self._value_from(manifest,path)
                if name:assets[name]=directory/name
            GLib.idle_add(self._apply_imported,manifest,assets)
        except Exception as exc:GLib.idle_add(self._toast,str(exc))
    def _apply_imported(self,manifest,assets):
        self.manifest=manifest;self.assets=assets
        for manifest_path,mode in ((('desktop','wallpaper'),"desktop"),(('desktop','wallpaper_dark'),"desktop"),(('login','wallpaper'),"login")):
            source=assets.get(self._value_from(manifest,manifest_path,""))
            if source:self._preview_pictures[mode].set_file(Gio.File.new_for_path(str(source)))
        logo=assets.get(self._value_from(manifest,("login","logo"),""))
        if logo:self._preview_logos["login"].set_file(Gio.File.new_for_path(str(logo)));self._preview_logos["login"].set_visible(True)
        self._load_controls();self._sync();self._toast("Theme opened for editing");return GLib.SOURCE_REMOVE
    def _save(self,*_):
        path=Path.home()/".local/share/gnome-customizer/drafts";path.mkdir(parents=True,exist_ok=True);preview=self._generate_preview();manifest=json.loads(json.dumps(self.manifest));manifest["preview"]="assets/preview.png";assets=dict(self.assets);assets["assets/preview.png"]=preview;threading.Thread(target=self._save_worker,args=(manifest,assets,path/"draft.gctheme"),daemon=True).start()
    def _save_worker(self,manifest,assets,target):
        try:export_theme(manifest,assets,target);GLib.idle_add(self._toast,"Draft saved as drafts/draft.gctheme")
        except Exception as exc:GLib.idle_add(self._toast,str(exc))
    def _export(self,*_):
        dialog=Gtk.FileDialog(title="Export Theme",initial_name="MyTheme.gctheme")
        dialog.save(self.get_root(),None,self._export_done)
    def _export_done(self,dialog,result):
        try:
            target=Path(dialog.save_finish(result).get_path());preview=self._generate_preview();self.manifest["preview"]="assets/preview.png";self.assets["assets/preview.png"]=preview;manifest=json.loads(json.dumps(self.manifest));assets=dict(self.assets);threading.Thread(target=self._export_worker,args=(manifest,assets,target),daemon=True).start()
        except GLib.Error:pass
        except Exception as exc:self._toast(str(exc))
    def _export_worker(self,manifest,assets,target):
        try:export_theme(manifest,assets,target);GLib.idle_add(self._toast,"Theme exported")
        except Exception as exc:GLib.idle_add(self._toast,str(exc))
    def _generate_preview(self):
        directory=Path.home()/".local/share/gnome-customizer/drafts";directory.mkdir(parents=True,exist_ok=True);target=directory/"generated-preview.png";surface=cairo.ImageSurface(cairo.FORMAT_ARGB32,960,540);ctx=cairo.Context(surface)
        def rgb(value):
            value=value.lstrip("#");return tuple(int(value[i:i+2],16)/255 for i in (0,2,4))
        def rounded(x,y,w,h,r):ctx.new_sub_path();ctx.arc(x+w-r,y+r,r,-1.5708,0);ctx.arc(x+w-r,y+h-r,r,0,1.5708);ctx.arc(x+r,y+h-r,r,1.5708,3.1416);ctx.arc(x+r,y+r,r,3.1416,4.7124);ctx.close_path()
        ctx.set_source_rgb(*rgb(self._get(("shell","overview","color"),"#263850")));ctx.paint();ctx.set_source_rgb(*rgb(self._get(("shell","panel","color"),"#16161A")));ctx.rectangle(0,0,960,42);ctx.fill();ctx.set_source_rgb(*rgb(self._get(("applications","window_color"),"#18181C")));rounded(180,105,430,290,self._get(("applications","corner_radius"),12));ctx.fill();ctx.set_source_rgba(*rgb(self._get(("shell","menus","color"),"#202026")),.94);rounded(640,110,230,220,14);ctx.fill();ctx.set_source_rgba(*rgb(self._get(("shell","dock","color"),"#202026")),.86);rounded(330,445,300,70,self._get(("shell","dock","corner_radius"),18));ctx.fill();ctx.set_source_rgb(1,1,1);ctx.select_font_face("Sans",cairo.FONT_SLANT_NORMAL,cairo.FONT_WEIGHT_BOLD);ctx.set_font_size(18);ctx.move_to(28,28);ctx.show_text(self._get(("name",),"Theme Preview"));surface.write_to_png(target);return target


class ThemesPage(Adw.PreferencesPage):
    def __init__(self,toast,apply_theme=None):
        super().__init__(title="Themes",description="Import and share validated appearance-only themes");self.toast=toast;self.apply_theme=apply_theme;self.group=Adw.PreferencesGroup(title="Local Themes");self.add(self.group)
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
        row=Adw.ActionRow(title=manifest.get("name","Unnamed Theme"),subtitle=f"by {manifest.get('author','Unknown')}")
        if self.apply_theme:
            button=Gtk.Button(label="Stage Theme",valign=Gtk.Align.CENTER);button.connect("clicked",lambda *_:self.apply_theme(directory));row.add_suffix(button)
        (group or self.group).add(row)
        return GLib.SOURCE_REMOVE
