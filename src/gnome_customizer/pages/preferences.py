from __future__ import annotations

from gi.repository import Adw, Gtk
from ..backend.transactions import Change
from ..color import color_button, hex_color


def _clock_text(value, twelve_hour):
    hours=int(value)%24;minutes=round((value-int(value))*60)%60
    if not twelve_hour:return f"{hours:02d}:{minutes:02d}"
    return f"{hours%12 or 12}:{minutes:02d} {'AM' if hours<12 else 'PM'}"


def _clock_value(text, twelve_hour):
    parts=text.strip().upper().split()
    if twelve_hour:
        if len(parts)!=2 or parts[1] not in {"AM","PM"}:raise ValueError
        h,m=(int(x) for x in parts[0].split(":"));
        if not 1<=h<=12 or not 0<=m<60:raise ValueError
        h=(h%12)+(12 if parts[1]=="PM" else 0)
    else:
        if len(parts)!=1:raise ValueError
        h,m=(int(x) for x in parts[0].split(":"));
        if not 0<=h<24 or not 0<=m<60:raise ValueError
    return h+m/60


class PreferencesFactory:
    def __init__(self, backend, manager, gdm_stage): self.backend=backend; self.manager=manager; self.gdm_stage=gdm_stage

    def page(self, title, description=""):
        page=Adw.PreferencesPage(title=title); page.set_description(description); return page
    def group(self,page,title,description=""):
        group=Adw.PreferencesGroup(title=title,description=description);page.add(group);return group
    def switch(self,group,title,schema,key,domain=None,subtitle=""):
        if not self.backend.supports(schema,key): return None
        domain=domain or ("shell" if schema=="io.github.gnomecustomizer.shell" else "desktop")
        row=Adw.SwitchRow(title=title,subtitle=subtitle); row.set_active(bool(self.backend.get(schema,key)))
        row.connect("notify::active",lambda r,_:self.manager.stage(Change(domain,schema,key,r.get_active(),title)));group.add(row);return row
    def combo(self,group,title,schema,key,labels=None,domain=None):
        choices=self.backend.choices(schema,key)
        if not choices:return None
        domain=domain or ("shell" if schema=="io.github.gnomecustomizer.shell" else "desktop");labels=labels or {x:x.replace("-"," ").title() for x in choices}; model=Gtk.StringList.new([labels.get(x,x) for x in choices]);row=Adw.ComboRow(title=title,model=model)
        current=self.backend.get(schema,key);row.set_selected(choices.index(current) if current in choices else 0)
        row.connect("notify::selected",lambda r,_:self.manager.stage(Change(domain,schema,key,choices[r.get_selected()],title)));group.add(row);return row
    def spin(self,group,title,schema,key,low,high,step=1,domain=None):
        if not self.backend.supports(schema,key):return None
        domain=domain or ("shell" if schema=="io.github.gnomecustomizer.shell" else "desktop")
        row=Adw.SpinRow.new_with_range(low,high,step);row.set_title(title);row.set_value(float(self.backend.get(schema,key)))
        row.connect("notify::value",lambda r,_:self.manager.stage(Change(domain,schema,key,int(r.get_value()) if step>=1 else r.get_value(),title)));group.add(row);return row
    def entry(self,group,title,schema,key,domain=None):
        if not self.backend.supports(schema,key):return None
        domain=domain or ("shell" if schema=="io.github.gnomecustomizer.shell" else "desktop")
        row=Adw.EntryRow(title=title,text=str(self.backend.get(schema,key)));row.connect("notify::text",lambda r,_:self.manager.stage(Change(domain,schema,key,r.get_text(),title)));group.add(row);return row
    def color(self,group,title,schema,key,domain=None):
        if not self.backend.supports(schema,key):return None
        domain=domain or ("shell" if schema=="io.github.gnomecustomizer.shell" else "desktop");row=Adw.ActionRow(title=title);button=color_button(self.backend.get(schema,key),title);button.connect("notify::rgba",lambda b,_:self.manager.stage(Change(domain,schema,key,hex_color(b.get_rgba()),title)));row.add_suffix(button);row.set_activatable_widget(button);group.add(row);return row
    def duration(self,group,title,schema,key,domain="desktop",gdm=False):
        if not self.backend.supports(schema,key):return None
        row=Adw.SpinRow.new_with_range(0,1440,1);row.set_title(title);value=self.backend.default(schema,key) if gdm else self.backend.get(schema,key);row.set_value(value/60)
        if gdm:row.connect("notify::value",lambda r,_:self.gdm_stage(schema,key,int(r.get_value()*60)))
        else:row.connect("notify::value",lambda r,_:self.manager.stage(Change(domain,schema,key,int(r.get_value()*60),title)))
        group.add(row);return row
    def time(self,group,title,schema,key,gdm=False):
        if not self.backend.supports(schema,key):return None
        value=float(self.backend.default(schema,key) if gdm else self.backend.get(schema,key));twelve_hour=self.backend.supports("org.gnome.desktop.interface","clock-format") and self.backend.get("org.gnome.desktop.interface","clock-format")=="12h";row=Adw.EntryRow(title=title,text=_clock_text(value,twelve_hour));row.set_tooltip_text("Use h:mm AM/PM" if twelve_hour else "Use HH:MM (24-hour time)")
        def changed(r,_):
            try:
                decimal=_clock_value(r.get_text(),twelve_hour);r.remove_css_class("error")
                if gdm:self.gdm_stage(schema,key,decimal)
                else:self.manager.stage(Change("desktop",schema,key,decimal,title))
            except ValueError:r.add_css_class("error")
        row.connect("notify::text",changed);group.add(row);return row
    def gdm_switch(self,group,title,schema,key,default=False,subtitle=""):
        if not self.backend.supports(schema,key):return None
        row=Adw.SwitchRow(title=title,subtitle=subtitle);row.set_active(default);row.connect("notify::active",lambda r,_:self.gdm_stage(schema,key,r.get_active()));group.add(row);return row
    def gdm_combo(self,group,title,schema,key,labels=None):
        choices=self.backend.choices(schema,key)
        if not choices:return None
        labels=labels or {x:x.replace("-"," ").title() for x in choices};row=Adw.ComboRow(title=title,model=Gtk.StringList.new([labels.get(x,x) for x in choices]));default=self.backend.default(schema,key);row.set_selected(choices.index(default) if default in choices else 0);row.connect("notify::selected",lambda r,_:self.gdm_stage(schema,key,choices[r.get_selected()]));group.add(row);return row
    def gdm_spin(self,group,title,schema,key,low,high,step=1):
        if not self.backend.supports(schema,key):return None
        row=Adw.SpinRow.new_with_range(low,high,step);row.set_title(title);row.set_value(float(self.backend.default(schema,key)));row.connect("notify::value",lambda r,_:self.gdm_stage(schema,key,int(r.get_value()) if step>=1 else r.get_value()));group.add(row);return row
    def gdm_entry(self,group,title,schema,key):
        if not self.backend.supports(schema,key):return None
        row=Adw.EntryRow(title=title,text=str(self.backend.default(schema,key)));row.connect("notify::text",lambda r,_:self.gdm_stage(schema,key,r.get_text()));group.add(row);return row

    def desktop_appearance(self):
        p=self.page("Appearance","Desktop colors, wallpaper, icons, cursor, and typography")
        g=self.group(p,"Style")
        color_scheme=self.combo(g,"Color Scheme","org.gnome.desktop.interface","color-scheme")
        if color_scheme and self.backend.supports("org.gnome.shell.ubuntu","color-scheme"):
            choices=self.backend.choices("org.gnome.desktop.interface","color-scheme")
            color_scheme.connect("notify::selected",lambda r,_:self.manager.stage(Change("desktop","org.gnome.shell.ubuntu","color-scheme",choices[r.get_selected()],"Ubuntu Color Scheme")))
        self.combo(g,"Accent Color","org.gnome.desktop.interface","accent-color")
        g=self.group(p,"Pointer and Text");self.spin(g,"Cursor Size","org.gnome.desktop.interface","cursor-size",8,128);self.spin(g,"Text Scaling","org.gnome.desktop.interface","text-scaling-factor",.5,3,.05)
        return p
    def topbar(self):
        p=self.page("Top Bar");g=self.group(p,"Clock")
        self.combo(g,"Clock Format","org.gnome.desktop.interface","clock-format",{"12h":"12-hour","24h":"24-hour"})
        self.switch(g,"Show Date","org.gnome.desktop.interface","clock-show-date");self.switch(g,"Show Weekday","org.gnome.desktop.interface","clock-show-weekday");self.switch(g,"Show Seconds","org.gnome.desktop.interface","clock-show-seconds");self.switch(g,"Battery Percentage","org.gnome.desktop.interface","show-battery-percentage")
        return p
    def mouse_touchpad(self):
        p=self.page("Mouse & Touchpad","Changes are staged until Apply, then written and verified through GNOME settings")
        mouse="org.gnome.desktop.peripherals.mouse";g=self.group(p,"Mouse")
        self.combo(g,"Acceleration",mouse,"accel-profile");self.switch(g,"Left-handed Primary Button",mouse,"left-handed");self.switch(g,"Natural Scrolling",mouse,"natural-scroll");self.spin(g,"Pointer Speed",mouse,"speed",-1,1,.05);self.switch(g,"Middle-click Emulation",mouse,"middle-click-emulation");self.spin(g,"Double-click Interval (ms)",mouse,"double-click",100,5000,10);self.spin(g,"Drag Threshold (px)",mouse,"drag-threshold",1,100)
        touchpad="org.gnome.desktop.peripherals.touchpad";g=self.group(p,"Touchpad")
        self.combo(g,"Touchpad Mode",touchpad,"send-events");self.combo(g,"Acceleration",touchpad,"accel-profile");self.spin(g,"Pointer Speed",touchpad,"speed",-1,1,.05);self.switch(g,"Tap to Click",touchpad,"tap-to-click");self.switch(g,"Tap and Drag",touchpad,"tap-and-drag");self.switch(g,"Tap and Drag Lock",touchpad,"tap-and-drag-lock");self.switch(g,"Natural Scrolling",touchpad,"natural-scroll");self.switch(g,"Two-finger Scrolling",touchpad,"two-finger-scrolling-enabled");self.switch(g,"Edge Scrolling",touchpad,"edge-scrolling-enabled");self.combo(g,"Click Method",touchpad,"click-method");self.combo(g,"Primary Button",touchpad,"left-handed");self.switch(g,"Middle-click Emulation",touchpad,"middle-click-emulation");self.switch(g,"Disable While Typing",touchpad,"disable-while-typing");self.spin(g,"Typing Guard Timeout (ms)",touchpad,"disable-while-typing-timeout",100,5000,10)
        return p
    def keyboard(self):
        p=self.page("Keyboard","Supported system-wide typing behavior")
        g=self.group(p,"Key Repeat")
        self.switch(g,"Repeat Keys","org.gnome.desktop.peripherals.keyboard","repeat")
        self.spin(g,"Repeat Delay (milliseconds)","org.gnome.desktop.peripherals.keyboard","delay",100,2000,10)
        self.spin(g,"Repeat Interval (milliseconds)","org.gnome.desktop.peripherals.keyboard","repeat-interval",10,2000,10)
        g=self.group(p,"Numeric Keypad")
        self.switch(g,"Remember Num Lock State","org.gnome.desktop.peripherals.keyboard","remember-numlock-state")
        return p
    def power(self):
        p=self.page("Power");g=self.group(p,"Energy")
        self.combo(g,"Power Button Action","org.gnome.settings-daemon.plugins.power","power-button-action");self.switch(g,"Power Saver on Low Battery","org.gnome.settings-daemon.plugins.power","power-saver-profile-on-low-battery");self.switch(g,"Dim Screen","org.gnome.settings-daemon.plugins.power","idle-dim");self.spin(g,"Dimmed Brightness","org.gnome.settings-daemon.plugins.power","idle-brightness",0,100);self.switch(g,"Ambient Light Sensor","org.gnome.settings-daemon.plugins.power","ambient-enabled");self.duration(g,"Blank Screen Delay (minutes)","org.gnome.desktop.session","idle-delay");self.combo(g,"AC Inactive Action","org.gnome.settings-daemon.plugins.power","sleep-inactive-ac-type");self.duration(g,"AC Inactive Timeout (minutes)","org.gnome.settings-daemon.plugins.power","sleep-inactive-ac-timeout");self.combo(g,"Battery Inactive Action","org.gnome.settings-daemon.plugins.power","sleep-inactive-battery-type");self.duration(g,"Battery Inactive Timeout (minutes)","org.gnome.settings-daemon.plugins.power","sleep-inactive-battery-timeout")
        return p
    def night_light(self):
        p=self.page("Night Light");g=self.group(p,"Schedule")
        self.switch(g,"Night Light","org.gnome.settings-daemon.plugins.color","night-light-enabled");self.spin(g,"Color Temperature","org.gnome.settings-daemon.plugins.color","night-light-temperature",1000,10000,100);self.switch(g,"Sunset to Sunrise","org.gnome.settings-daemon.plugins.color","night-light-schedule-automatic");self.time(g,"Custom Start","org.gnome.settings-daemon.plugins.color","night-light-schedule-from");self.time(g,"Custom End","org.gnome.settings-daemon.plugins.color","night-light-schedule-to")
        return p
    def sound(self):
        p=self.page("Sound");g=self.group(p,"Event Sounds")
        self.switch(g,"Event Sounds","org.gnome.desktop.sound","event-sounds");self.switch(g,"Input Feedback","org.gnome.desktop.sound","input-feedback-sounds");self.switch(g,"Allow Above 100%","org.gnome.desktop.sound","allow-volume-above-100-percent")
        return p
    def login(self):
        return self.page("Login Screen","Changes are staged and request administrator authentication only when applied")
    def login_input(self):
        p=self.page("Login Input & Sound");mouse="org.gnome.desktop.peripherals.mouse";g=self.group(p,"Mouse");self.gdm_combo(g,"Acceleration",mouse,"accel-profile");self.gdm_switch(g,"Left-handed Primary Button",mouse,"left-handed");self.gdm_switch(g,"Natural Scrolling",mouse,"natural-scroll");self.gdm_spin(g,"Pointer Speed",mouse,"speed",-1,1,.05);self.gdm_switch(g,"Middle-click Emulation",mouse,"middle-click-emulation");self.gdm_spin(g,"Double-click Interval (ms)",mouse,"double-click",100,5000,10);self.gdm_spin(g,"Drag Threshold (px)",mouse,"drag-threshold",1,100)
        touchpad="org.gnome.desktop.peripherals.touchpad";g=self.group(p,"Touchpad");self.gdm_combo(g,"Touchpad Mode",touchpad,"send-events");self.gdm_combo(g,"Acceleration",touchpad,"accel-profile");self.gdm_spin(g,"Pointer Speed",touchpad,"speed",-1,1,.05);self.gdm_switch(g,"Tap to Click",touchpad,"tap-to-click");self.gdm_switch(g,"Tap and Drag",touchpad,"tap-and-drag");self.gdm_switch(g,"Tap and Drag Lock",touchpad,"tap-and-drag-lock");self.gdm_switch(g,"Natural Scrolling",touchpad,"natural-scroll");self.gdm_switch(g,"Two-finger Scrolling",touchpad,"two-finger-scrolling-enabled");self.gdm_switch(g,"Edge Scrolling",touchpad,"edge-scrolling-enabled");self.gdm_combo(g,"Click Method",touchpad,"click-method");self.gdm_combo(g,"Primary Button",touchpad,"left-handed");self.gdm_switch(g,"Middle-click Emulation",touchpad,"middle-click-emulation");self.gdm_switch(g,"Disable While Typing",touchpad,"disable-while-typing");self.gdm_spin(g,"Typing Guard Timeout (ms)",touchpad,"disable-while-typing-timeout",100,5000,10)
        g=self.group(p,"Sound");self.gdm_switch(g,"Event Sounds","org.gnome.desktop.sound","event-sounds");self.gdm_switch(g,"Input Feedback","org.gnome.desktop.sound","input-feedback-sounds");self.gdm_switch(g,"Allow Above 100%","org.gnome.desktop.sound","allow-volume-above-100-percent");return p
    def login_power(self):
        p=self.page("Login Power & Night Light");g=self.group(p,"Power");self.gdm_combo(g,"Power Button Action","org.gnome.settings-daemon.plugins.power","power-button-action");self.gdm_switch(g,"Power Saver on Low Battery","org.gnome.settings-daemon.plugins.power","power-saver-profile-on-low-battery");self.gdm_switch(g,"Dim Screen","org.gnome.settings-daemon.plugins.power","idle-dim");self.gdm_spin(g,"Dimmed Brightness","org.gnome.settings-daemon.plugins.power","idle-brightness",0,100);self.gdm_switch(g,"Ambient Light Sensor","org.gnome.settings-daemon.plugins.power","ambient-enabled");self.duration(g,"Blank Screen Delay (minutes)","org.gnome.desktop.session","idle-delay",gdm=True);self.gdm_combo(g,"AC Inactive Action","org.gnome.settings-daemon.plugins.power","sleep-inactive-ac-type");self.duration(g,"AC Inactive Timeout (minutes)","org.gnome.settings-daemon.plugins.power","sleep-inactive-ac-timeout",gdm=True);self.gdm_combo(g,"Battery Inactive Action","org.gnome.settings-daemon.plugins.power","sleep-inactive-battery-type");self.duration(g,"Battery Inactive Timeout (minutes)","org.gnome.settings-daemon.plugins.power","sleep-inactive-battery-timeout",gdm=True)
        g=self.group(p,"Night Light");self.gdm_switch(g,"Night Light","org.gnome.settings-daemon.plugins.color","night-light-enabled");self.gdm_spin(g,"Color Temperature","org.gnome.settings-daemon.plugins.color","night-light-temperature",1000,10000,100);self.gdm_switch(g,"Sunset to Sunrise","org.gnome.settings-daemon.plugins.color","night-light-schedule-automatic");self.time(g,"Custom Start","org.gnome.settings-daemon.plugins.color","night-light-schedule-from",gdm=True);self.time(g,"Custom End","org.gnome.settings-daemon.plugins.color","night-light-schedule-to",gdm=True);return p
    def shell(self,title,section):
        p=self.page(title);g=self.group(p,section)
        schema="io.github.gnomecustomizer.shell"
        if section=="Dock":
            self.switch(g,"Enable Custom Dock",schema,"dock-enabled");self.combo(g,"Position",schema,"dock-position");self.switch(g,"Floating",schema,"dock-floating");self.color(g,"Background Color",schema,"dock-color");self.switch(g,"Gradient",schema,"dock-gradient-enabled");self.color(g,"Gradient End Color",schema,"dock-color2");self.combo(g,"Gradient Direction",schema,"dock-gradient-direction");self.spin(g,"Opacity",schema,"dock-opacity",0,1,.01);self.spin(g,"Corner Radius",schema,"dock-radius",0,32);self.spin(g,"Icon Size",schema,"dock-icon-size",24,96);self.spin(g,"Spacing",schema,"dock-spacing",0,24);self.combo(g,"Running Indicator",schema,"dock-indicator-style");self.switch(g,"Show Favorites",schema,"dock-show-favorites");self.switch(g,"Show Running Apps",schema,"dock-show-running");self.switch(g,"Show Applications",schema,"dock-show-apps");self.combo(g,"Show Applications Position",schema,"dock-show-apps-position");self.switch(g,"Auto-hide",schema,"dock-autohide");self.switch(g,"Intelligent Hide",schema,"dock-intellihide")
        else:
            for label,key in (("Panel Blur","panel-blur"),("Dock Blur","dock-blur"),("Menu Blur","menu-blur")):self.spin(g,label,schema,key,0,100)
            overview=self.group(p,"Overview &amp; App Grid","Blurred wallpaper treatment behind workspaces, search, and applications");self.switch(overview,"Enable Overview Blur",schema,"overview-enabled");self.color(overview,"Backdrop Tint",schema,"overview-color");self.spin(overview,"Tint Opacity",schema,"overview-opacity",0,1,.01);self.spin(overview,"Blur Strength",schema,"overview-blur",0,100);self.spin(overview,"Brightness",schema,"overview-brightness",.2,1.5,.05);self.spin(overview,"Saturation",schema,"overview-saturation",0,1,.05)
            menus=self.group(p,"Menus &amp; Popovers");self.switch(menus,"Enable Custom Menu Appearance",schema,"menu-enabled");self.color(menus,"Surface Color",schema,"menu-color");self.switch(menus,"Gradient",schema,"menu-gradient-enabled");self.color(menus,"Gradient End Color",schema,"menu-color2");self.combo(menus,"Gradient Direction",schema,"menu-gradient-direction");self.spin(menus,"Opacity",schema,"menu-opacity",.2,1,.01);self.spin(menus,"Corner Radius",schema,"menu-radius",0,32);self.color(menus,"Text Color",schema,"menu-text-color");self.color(menus,"Border Color",schema,"menu-border-color")
        return p
