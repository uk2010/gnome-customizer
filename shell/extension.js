import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import St from 'gi://St';

import * as Background from 'resource:///org/gnome/shell/ui/background.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
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

export default class CustomizerExtension extends Extension {
    enable() {
        this._settings = this.getSettings(); this._effects = []; this._menuActors = new Map(); this._overviewBackgrounds = []; this._panelRestoreSource = 0;
        this._panelStyle = Main.panel.get_style(); this._overviewStyle = Main.layoutManager.overviewGroup.get_style();
        this._changed = this._settings.connect('changed', () => this._sync());
        this._monitors = Main.layoutManager.connect('monitors-changed', () => this._rebuildOverviewBackgrounds());
        this._overviewShowing = Main.overview.connect('showing', () => this._lowerOverviewBackground());
        this._overviewHidden = Main.overview.connect('hidden', () => this._queuePanelStyleRestore());
        this._uiAdded = Main.uiGroup.connect('child-added', () => GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => { if (this._settings) this._styleMenus(); return GLib.SOURCE_REMOVE; }));
        this._panelBackground=new St.Widget({name:'gnome-customizer-panel-background',reactive:false});
        this._panelBackground.add_constraint(new Clutter.BindConstraint({source:Main.panel,coordinate:Clutter.BindCoordinate.SIZE}));
        // Keep the background inside the panel. Adding it to panelBox makes it
        // a layout sibling of the real panel and pushes the top bar downward.
        Main.panel.insert_child_at_index(this._panelBackground,0);
        this._rebuildOverviewBackgrounds(); this._sync();
    }
    _blur(actor, name, sigma, brightness=1.0) {
        actor.remove_effect_by_name(name);
        if (sigma > 0) {
            const effect = new Shell.BlurEffect({mode: Shell.BlurMode.BACKGROUND, brightness, radius: sigma});
            actor.add_effect_with_name(name, effect);
            if (!this._effects.some(([existing, effectName]) => existing === actor && effectName === name)) this._effects.push([actor,name]);
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
    _queuePanelStyleRestore() {
        if (this._panelRestoreSource || !this._settings) return;
        // GNOME Shell 50 clears Main.panel.style immediately after emitting
        // `hidden`, so restore our dynamic text style on the following idle.
        this._panelRestoreSource=GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
            this._panelRestoreSource=0;
            if (this._settings?.get_boolean('panel-enabled')) {
                const text=this._settings.get_string('panel-text-color');
                Main.panel.set_style(`background-color: transparent; color: ${text};`);
            }
            return GLib.SOURCE_REMOVE;
        });
    }
    _sync() {
        if (this._settings.get_boolean('panel-enabled')) {
            const opacity=this._settings.get_double('panel-opacity'), text=this._settings.get_string('panel-text-color');
            Main.panel.add_style_class_name('gnome-customizer-panel');
            this._panelBackground.visible=true;
            this._panelBackground.set_style(`${backgroundStyle(this._settings, 'panel', opacity)} border-radius: ${this._settings.get_int('panel-radius')}px;`);
            Main.panel.set_style(`background-color: transparent; color: ${text};`);
            this._blur(this._panelBackground, 'gnome-customizer-panel-blur', opacity>0 ? this._settings.get_int('panel-blur') : 0);
        } else {
            Main.panel.remove_style_class_name('gnome-customizer-panel');
            this._panelBackground.remove_effect_by_name('gnome-customizer-panel-blur');
            this._panelBackground.visible=false;
            Main.panel.set_style(this._panelStyle);
        }
        this._syncOverviewBackgrounds();
        this._styleMenus();
    }
    disable() {
        if (this._panelRestoreSource) { GLib.Source.remove(this._panelRestoreSource); this._panelRestoreSource=0; }
        this._settings.disconnect(this._changed); Main.layoutManager.disconnect(this._monitors); Main.overview.disconnect(this._overviewShowing); Main.overview.disconnect(this._overviewHidden); Main.uiGroup.disconnect(this._uiAdded);
        this._destroyOverviewBackgrounds();
        this._panelBackground.destroy(); this._panelBackground=null;
        Main.panel.remove_style_class_name('gnome-customizer-panel');
        Main.panel.set_style(this._panelStyle);
        Main.layoutManager.overviewGroup.set_style(this._overviewStyle);
        for (const [actor,name] of this._effects) { try { actor?.remove_effect_by_name(name); } catch (_) {} }
        this._restoreMenus();
        this._effects=[]; this._menuActors=new Map(); this._settings=null;
    }
}
