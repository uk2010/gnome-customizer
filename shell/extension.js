import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import St from 'gi://St';

import * as Background from 'resource:///org/gnome/shell/ui/background.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as OverviewControls from 'resource:///org/gnome/shell/ui/overviewControls.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

function colorWithOpacity(color, opacity) {
    const match = color.match(/^#([0-9a-f]{6})([0-9a-f]{2})?$/i);
    if (!match) return color;
    const rgb = match[1].match(/../g).map(value => Number.parseInt(value, 16));
    const sourceAlpha = match[2] ? Number.parseInt(match[2], 16) / 255 : 1;
    return `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${Math.max(0, Math.min(1, sourceAlpha * opacity)).toFixed(3)})`;
}

function backgroundStyle(settings, prefix, opacity=1) {
    if (opacity <= 0) return 'background-color: transparent;';
    const color = colorWithOpacity(settings.get_string(`${prefix}-color`), opacity);
    if (!settings.get_boolean(`${prefix}-gradient-enabled`)) return `background-color: ${color};`;
    const end = colorWithOpacity(settings.get_string(`${prefix}-color2`), opacity);
    return `background-gradient-direction: ${settings.get_string(`${prefix}-gradient-direction`)}; background-gradient-start: ${color}; background-gradient-end: ${end};`;
}

class Dock {
    constructor(settings, monitorIndex) {
        this._settings = settings;
        this._monitorIndex = monitorIndex;
        this._positionSource = 0;
        this.actor = new St.BoxLayout({style_class: 'gnome-customizer-dock', reactive: true, track_hover: true});
        Main.layoutManager.addChrome(this.actor);
        this._signals = [
            [settings, settings.connect('changed', () => this.sync())],
            [Shell.AppSystem.get_default(), Shell.AppSystem.get_default().connect('app-state-changed', () => this._populate())],
            [global.display, global.display.connect('restacked', () => this._conceal())],
            [global.display, global.display.connect('notify::focus-window', () => this._conceal())],
            [Main.overview, Main.overview.connect('hidden', () => {
                if (this._showAppsButton) this._showAppsButton.checked = false;
            })],
            [this.actor, this.actor.connect('notify::width', () => this._queuePosition())],
            [this.actor, this.actor.connect('notify::height', () => this._queuePosition())],
        ];
        this.actor.connect('enter-event', () => this._reveal());
        this.actor.connect('leave-event', () => this._conceal());
        this.sync();
    }

    _apps() {
        const apps = [];
        if (this._settings.get_boolean('dock-show-favorites'))
            apps.push(...global.settings.get_strv('favorite-apps').map(id => Shell.AppSystem.get_default().lookup_app(id)).filter(Boolean));
        if (this._settings.get_boolean('dock-show-running')) {
            for (const app of Shell.AppSystem.get_default().get_running())
                if (!apps.includes(app)) apps.push(app);
        }
        return apps;
    }

    _populate() {
        const showAppsChecked = this._showAppsButton?.checked ?? false;
        this._showAppsButton = null;
        this.actor.destroy_all_children();
        const size = this._settings.get_int('dock-icon-size');
        const indicatorStyle = this._settings.get_string('dock-indicator-style');
        const showAppsFirst = this._settings.get_string('dock-show-apps-position') === 'first';
        if (showAppsFirst) this._addShowAppsButton(size, showAppsChecked);
        for (const app of this._apps()) {
            const content = new St.BoxLayout({orientation: Clutter.Orientation.VERTICAL, x_align: Clutter.ActorAlign.CENTER});
            content.add_child(app.create_icon_texture(size));
            if (app.state === Shell.AppState.RUNNING) {
                const width = indicatorStyle === 'dot' ? 7 : indicatorStyle === 'dash' ? 14 : Math.max(18,size-8);
                const height = indicatorStyle === 'dot' ? 7 : indicatorStyle === 'dash' ? 5 : 4;
                content.add_child(new St.Widget({
                    style_class: `gnome-customizer-running-indicator ${indicatorStyle}`,
                    style: 'background-color: #ffffff; border: 1px solid rgba(0, 0, 0, 0.72);',
                    width, height, x_align: Clutter.ActorAlign.CENTER,
                }));
            }
            const button = new St.Button({style_class: 'gnome-customizer-dock-button', can_focus: true, accessible_name: app.get_name(), child: content});
            button.connect('clicked', () => app.activate());
            this.actor.add_child(button);
        }
        if (!showAppsFirst) this._addShowAppsButton(size, showAppsChecked);
        this._queuePosition();
    }

    _addShowAppsButton(size, checked) {
        if (!this._settings.get_boolean('dock-show-apps')) return;
        const icon = new St.Icon({
            icon_name: `view-app-grid-${Main.sessionMode.currentMode}-symbolic`,
            icon_size: size,
        });
        const button = new St.Button({
            style_class: 'gnome-customizer-dock-button gnome-customizer-show-apps show-apps',
            toggle_mode: true,
            can_focus: true,
            accessible_name: 'Show Applications',
            child: icon,
        });
        button.checked = checked && Main.overview.visible;
        button.connect('clicked', () => {
            if (button.checked) Main.overview.show(OverviewControls.ControlsState.APP_GRID);
            else Main.overview.hide();
        });
        this._showAppsButton = button;
        this.actor.add_child(button);
    }

    sync() {
        const monitor = Main.layoutManager.monitors[this._monitorIndex];
        if (!monitor) return;
        const position = this._settings.get_string('dock-position');
        const vertical = position !== 'bottom';
        this.actor.orientation = vertical ? Clutter.Orientation.VERTICAL : Clutter.Orientation.HORIZONTAL;
        const spacing = this._settings.get_int('dock-spacing');
        const floating = this._settings.get_boolean('dock-floating');
        const radius = this._settings.get_int('dock-radius');
        const opacity = this._settings.get_double('dock-opacity');
        this.actor.set_style(`spacing: ${spacing}px; border-radius: ${radius}px; ${backgroundStyle(this._settings, 'dock', opacity)}`);
        this._populate();
        const margin = floating ? 12 : 0; this._position=position; this._margin=margin;
        this._positionActor();
        this._queuePosition();
        this.actor.remove_effect_by_name('gnome-customizer-dock-blur');
        const sigma = this._settings.get_int('dock-blur');
        if (opacity > 0 && sigma > 0) this.actor.add_effect_with_name('gnome-customizer-dock-blur', new Shell.BlurEffect({mode: Shell.BlurMode.BACKGROUND, brightness: 1.0, radius: sigma}));
        this.actor.visible = this._settings.get_boolean('dock-enabled');
        this._conceal();
    }

    _positionActor() {
        const monitor = Main.layoutManager.monitors[this._monitorIndex];
        if (!monitor || !this.actor) return;
        const [, , naturalWidth, naturalHeight] = this.actor.get_preferred_size();
        const width = this.actor.width > 0 ? this.actor.width : naturalWidth;
        const height = this.actor.height > 0 ? this.actor.height : naturalHeight;
        let x, y;
        if (this._position === 'left') {
            x = monitor.x + this._margin;
            y = monitor.y + (monitor.height - height) / 2;
        } else if (this._position === 'right') {
            x = monitor.x + monitor.width - width - this._margin;
            y = monitor.y + (monitor.height - height) / 2;
        } else {
            x = monitor.x + (monitor.width - width) / 2;
            y = monitor.y + monitor.height - height - this._margin;
        }
        x = Math.max(monitor.x, Math.min(Math.round(x), monitor.x + monitor.width - width));
        y = Math.max(monitor.y, Math.min(Math.round(y), monitor.y + monitor.height - height));
        this.actor.set_position(x, y);
    }

    _queuePosition() {
        if (this._positionSource || !this.actor) return;
        this._positionSource = GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
            this._positionSource = 0;
            if (this.actor) { this._positionActor(); this._conceal(); }
            return GLib.SOURCE_REMOVE;
        });
    }

    _reveal() {
        if (!this.actor) return;
        this.actor.ease({opacity: 255, translation_x: 0, translation_y: 0, duration: 180, mode: Clutter.AnimationMode.EASE_OUT_QUAD});
    }
    _conceal() {
        if (!this.actor || !this._settings) return;
        const hide = this._settings.get_boolean('dock-autohide') || (this._settings.get_boolean('dock-intellihide') && this._overlapsWindow());
        let translation_x=0,translation_y=0;
        if (hide) {
            if (this._position==='left') translation_x=-(this.actor.width+this._margin-4);
            else if (this._position==='right') translation_x=this.actor.width+this._margin-4;
            else translation_y=this.actor.height+this._margin-4;
        }
        this.actor.ease({opacity: hide ? 80 : 255, translation_x, translation_y, duration: 220, mode: Clutter.AnimationMode.EASE_OUT_QUAD});
    }
    _overlapsWindow() {
        const [x, y] = this.actor.get_position(); const [w, h] = [this.actor.width,this.actor.height];
        return global.get_window_actors().some(a => {
            const win=a.metaWindow;
            if (!win || win.minimized || !win.showing_on_its_workspace() || win.get_monitor() !== this._monitorIndex) return false;
            const r=win.get_frame_rect(); return r.x < x+w && r.x+r.width > x && r.y < y+h && r.y+r.height > y;
        });
    }
    destroy() {
        if (this._positionSource) { GLib.Source.remove(this._positionSource); this._positionSource=0; }
        for (const [object,id] of this._signals) { try { object.disconnect(id); } catch (_) {} }
        this.actor.destroy(); this.actor=null;
    }
}

export default class CustomizerExtension extends Extension {
    enable() {
        this._settings = this.getSettings(); this._docks = []; this._effects = []; this._menuActors = new Map(); this._suppressedDocks = new Map(); this._overviewBackgrounds = [];
        this._panelStyle = Main.panel.get_style(); this._overviewStyle = Main.layoutManager.overviewGroup.get_style();
        this._changed = this._settings.connect('changed', () => this._sync());
        this._monitors = Main.layoutManager.connect('monitors-changed', () => { this._rebuildDocks(); this._rebuildOverviewBackgrounds(); });
        this._overviewShowing = Main.overview.connect('showing', () => this._lowerOverviewBackground());
        this._uiAdded = Main.uiGroup.connect('child-added', () => GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => { if (this._settings) { this._styleMenus(); this._syncExternalDocks(); } return GLib.SOURCE_REMOVE; }));
        this._rebuildDocks(); this._rebuildOverviewBackgrounds(); this._sync();
    }
    _rebuildDocks() { this._docks?.forEach(d => d.destroy()); this._docks = Main.layoutManager.monitors.map((_, i) => new Dock(this._settings, i)); }
    _blur(actor, name, sigma, brightness=1.0) {
        actor.remove_effect_by_name(name);
        if (sigma > 0) {
            const effect = new Shell.BlurEffect({mode: Shell.BlurMode.BACKGROUND, brightness, radius: sigma});
            actor.add_effect_with_name(name, effect);
            if (!this._effects.some(([existing, effectName]) => existing === actor && effectName === name)) this._effects.push([actor,name]);
        }
    }
    _externalDockActors() {
        const actors=[];
        const visit=actor => {
            if (actor?.get_name?.() === 'dashtodockContainer') actors.push(actor);
            for (const child of actor?.get_children?.() ?? []) visit(child);
        };
        visit(Main.uiGroup);return actors;
    }
    _restoreExternalDocks() {
        for (const [actor,record] of this._suppressedDocks) {
            try { actor.disconnect(record.visibleId); actor.disconnect(record.destroyId); actor.reactive=record.reactive; actor.visible=record.visible; } catch (_) {}
        }
        this._suppressedDocks.clear();
    }
    _syncExternalDocks() {
        if (!this._settings.get_boolean('dock-enabled')) { this._restoreExternalDocks(); return; }
        for (const actor of this._externalDockActors()) {
            if (this._suppressedDocks.has(actor)) continue;
            const record={visible:actor.visible,reactive:actor.reactive,visibleId:0,destroyId:0};
            record.visibleId=actor.connect('notify::visible', () => { if (this._settings?.get_boolean('dock-enabled') && actor.visible) actor.hide(); });
            record.destroyId=actor.connect('destroy', () => this._suppressedDocks?.delete(actor));
            this._suppressedDocks.set(actor,record);actor.reactive=false;actor.hide();console.log('GNOME Customizer: suppressed an existing dock while the custom dock is enabled');
        }
    }
    _styleMenus() {
        if (!this._settings.get_boolean('menu-enabled')) { this._restoreMenus(); return; }
        const opacity=this._settings.get_double('menu-opacity'), radius=this._settings.get_int('menu-radius'), sigma=this._settings.get_int('menu-blur'), text=this._settings.get_string('menu-text-color'), border=this._settings.get_string('menu-border-color');
        const visit = actor => {
            if (actor.get_style_class_name?.()?.split(' ').includes('popup-menu-content')) {
                if (!this._menuActors.has(actor)) {
                    this._menuActors.set(actor,actor.get_style());
                    actor.connect('destroy', () => {
                        this._menuActors?.delete(actor);
                        this._effects = this._effects?.filter(([item]) => item !== actor) ?? [];
                    });
                }
                actor.set_style(`${backgroundStyle(this._settings, 'menu', opacity)} border-radius: ${radius}px; color: ${text}; border: 1px solid ${border};`);
                this._blur(actor, 'gnome-customizer-menu-blur', sigma);
            }
            for (const child of actor.get_children?.() ?? []) visit(child);
        }; visit(Main.uiGroup);
    }
    _restoreMenus() {
        for (const [actor,style] of this._menuActors) {
            try { actor?.remove_effect_by_name('gnome-customizer-menu-blur'); actor?.set_style(style); } catch (_) {}
        }
        this._menuActors.clear();
    }
    _destroyOverviewBackgrounds() {
        for (const item of this._overviewBackgrounds ?? []) {
            try { item.manager.destroy(); } catch (_) {}
        }
        this._overviewBackgrounds=[];
        try { this._overviewBackgroundGroup?.destroy(); } catch (_) {}
        this._overviewBackgroundGroup=null;
    }
    _lowerOverviewBackground() {
        const group=this._overviewBackgroundGroup;
        const parent=group?.get_parent();
        if (parent !== Main.layoutManager.overviewGroup) return;
        const children=parent.get_children();
        if (children[0] !== group) {
            parent.remove_child(group);
            parent.insert_child_at_index(group,0);
        }
    }
    _rebuildOverviewBackgrounds() {
        this._destroyOverviewBackgrounds();
        this._overviewBackgroundGroup=new Meta.BackgroundGroup({name:'gnome-customizer-overview-background'});
        for (let i=0;i<Main.layoutManager.monitors.length;i++) {
            const monitor=Main.layoutManager.monitors[i];
            // The half-pixel offset and positive z position are required by
            // Mutter for reliable background painting across monitor layouts.
            const surface=new St.Widget({x:monitor.x,y:monitor.y+0.5,z_position:1,width:monitor.width,height:monitor.height});
            const manager=new Background.BackgroundManager({container:surface,monitorIndex:i,controlPosition:false});
            const tint=new St.Widget({x:0,y:0,width:monitor.width,height:monitor.height});
            surface.add_child(tint);this._overviewBackgroundGroup.insert_child_at_index(surface,0);
            this._overviewBackgrounds.push({surface,tint,manager});
        }
        Main.layoutManager.overviewGroup.insert_child_at_index(this._overviewBackgroundGroup,0);
        this._syncOverviewBackgrounds();
    }
    _syncOverviewBackgrounds() {
        if (!this._overviewBackgroundGroup) return;
        const enabled=this._settings.get_boolean('overview-enabled');
        const sigma=this._settings.get_int('overview-blur');
        const brightness=this._settings.get_double('overview-brightness');
        const saturation=this._settings.get_double('overview-saturation');
        const opacity=this._settings.get_double('overview-opacity');
        const color=this._settings.get_string('overview-color');
        this._overviewBackgroundGroup.visible=enabled;
        for (const {surface,tint} of this._overviewBackgrounds) {
            surface.remove_effect_by_name('gnome-customizer-overview-blur');
            surface.remove_effect_by_name('gnome-customizer-overview-desaturate');
            const scale=St.ThemeContext.get_for_stage(global.stage).scale_factor;
            if (enabled && sigma>0) surface.add_effect_with_name('gnome-customizer-overview-blur',new Shell.BlurEffect({mode:Shell.BlurMode.ACTOR,brightness,radius:sigma*scale}));
            if (enabled && saturation<1) surface.add_effect_with_name('gnome-customizer-overview-desaturate',new Clutter.DesaturateEffect({factor:1-saturation}));
            tint.set_style(`background-color: ${colorWithOpacity(color, opacity)};`);
        }
        Main.layoutManager.overviewGroup.set_style(enabled ? 'background-color: transparent;' : this._overviewStyle);
    }
    _sync() {
        if (this._settings.get_boolean('panel-enabled')) {
            const opacity=this._settings.get_double('panel-opacity'), text=this._settings.get_string('panel-text-color');
            Main.panel.set_style(`${backgroundStyle(this._settings, 'panel', opacity)} color: ${text}; border-radius: ${this._settings.get_int('panel-radius')}px;`);
            this._blur(Main.panel, 'gnome-customizer-panel-blur', this._settings.get_int('panel-blur'));
        } else {
            Main.panel.remove_effect_by_name('gnome-customizer-panel-blur');
            Main.panel.set_style(this._panelStyle);
        }
        this._syncOverviewBackgrounds();
        this._styleMenus(); this._docks.forEach(d => d.sync()); this._syncExternalDocks();
    }
    disable() {
        this._settings.disconnect(this._changed); Main.layoutManager.disconnect(this._monitors); Main.overview.disconnect(this._overviewShowing); Main.uiGroup.disconnect(this._uiAdded);
        this._docks.forEach(d => d.destroy()); this._docks=[]; this._restoreExternalDocks(); this._destroyOverviewBackgrounds();
        Main.panel.set_style(this._panelStyle);
        Main.layoutManager.overviewGroup.set_style(this._overviewStyle);
        for (const [actor,name] of this._effects) { try { actor?.remove_effect_by_name(name); } catch (_) {} }
        this._restoreMenus();
        this._effects=[]; this._menuActors=new Map(); this._suppressedDocks=new Map(); this._settings=null;
    }
}
