import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import St from 'gi://St';

import * as AppDisplay from 'resource:///org/gnome/shell/ui/appDisplay.js';
import * as Background from 'resource:///org/gnome/shell/ui/background.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension, InjectionManager} from 'resource:///org/gnome/shell/extensions/extension.js';

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
        this._settings = this.getSettings(); this._effects = []; this._menuActors = new Map(); this._overviewHoverActors = new Map(); this._overviewBackgrounds = []; this._panelRestoreSource = 0; this._overviewScanSource = 0; this._injectionManager = new InjectionManager(); this._alphabeticalGridEnabled = false; this._started = false;
        this._changed = this._settings.connect('changed', () => this._sync());
        this._startupComplete = 0;
        if (Main.layoutManager._startingUp)
            this._startupComplete = Main.layoutManager.connect('startup-complete', () => this._start());
        else
            this._start();
    }
    _start() {
        if (!this._settings || this._started) return;
        if (this._startupComplete) { Main.layoutManager.disconnect(this._startupComplete); this._startupComplete=0; }
        this._started=true;
        this._panelStyle = Main.panel.get_style(); this._overviewStyle = Main.layoutManager.overviewGroup.get_style();
        this._monitors = Main.layoutManager.connect('monitors-changed', () => this._rebuildOverviewBackgrounds());
        this._overviewShowing = Main.overview.connect('showing', () => { this._lowerOverviewBackground();this._queueOverviewHoverScan(); });
        this._overviewHidden = Main.overview.connect('hidden', () => this._queuePanelStyleRestore());
        this._overviewAdded = Main.layoutManager.overviewGroup.connect('child-added', () => this._queueOverviewHoverScan());
        this._uiAdded = Main.uiGroup.connect('child-added', () => GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => { if (this._settings) this._styleMenus(); return GLib.SOURCE_REMOVE; }));
        this._rebuildOverviewBackgrounds(); this._sync();
    }
    _queueOverviewHoverScan() {
        if (this._overviewScanSource || !this._settings) return;
        this._overviewScanSource=GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
            this._overviewScanSource=0;if (this._settings) this._styleOverviewHoverBackgrounds();return GLib.SOURCE_REMOVE;
        });
    }
    _styleOverviewHoverBackgrounds() {
        const visit=actor => {
            const classes=actor.get_style_class_name?.()?.split(' ') ?? [];
            if ((classes.includes('overview-tile') || classes.includes('grid-search-result')) && !this._overviewHoverActors.has(actor)) {
                const record={style:actor.get_style(),hoverId:0,destroyId:0};
                record.hoverId=actor.connect('notify::hover', () => this._syncOverviewHoverBackground(actor));
                record.destroyId=actor.connect('destroy', () => this._overviewHoverActors?.delete(actor));
                this._overviewHoverActors.set(actor,record);
            }
            for (const child of actor.get_children?.() ?? []) visit(child);
        };
        visit(Main.layoutManager.overviewGroup);
        for (const actor of this._overviewHoverActors.keys()) this._syncOverviewHoverBackground(actor);
        const count=this._overviewHoverActors.size;
        if (count !== this._overviewHoverDiagnostic) { this._overviewHoverDiagnostic=count;if (count) console.log(`GNOME Customizer: overview hover backgrounds tracked (${count})`); }
    }
    _syncOverviewHoverBackground(actor) {
        const record=this._overviewHoverActors.get(actor);if (!record) return;
        const hovered=actor.get_hover?.() ?? actor.hover;
        if (!hovered) { actor.set_style(record.style);return; }
        const opacity=this._settings.get_double('overview-hover-opacity');
        const color=colorWithOpacity(this._settings.get_string('overview-hover-color'),opacity);
        actor.set_style(`${record.style ?? ''} background-color: ${color};`);
    }
    _syncAlphabeticalAppGrid() {
        const enabled=this._settings.get_boolean('alphabetical-app-grid');
        if (enabled===this._alphabeticalGridEnabled) return;
        this._alphabeticalGridEnabled=enabled;
        this._injectionManager.clear();
        if (enabled) {
            this._injectionManager.overrideMethod(AppDisplay.AppDisplay.prototype, '_compareItems', () =>
                function alphabeticalCompare(a,b) {
                    return `${a.name ?? ''}`.localeCompare(`${b.name ?? ''}`, undefined, {sensitivity:'base'});
                });
            this._injectionManager.overrideMethod(AppDisplay.AppDisplay.prototype, '_redisplay', () =>
                function alphabeticalRedisplay() {
                    this._folderIcons.forEach(icon => icon.view._redisplay());
                    const currentApps=this._orderedItems.slice();
                    const currentIds=currentApps.map(icon => icon.id);
                    const newApps=this._loadApps().sort(this._compareItems.bind(this));
                    const newIds=newApps.map(icon => icon.id);
                    const addedApps=newApps.filter(icon => !currentIds.includes(icon.id));
                    currentApps.filter(icon => !newIds.includes(icon.id)).forEach(icon => { this._removeItem(icon);icon.destroy(); });
                    const {itemsPerPage}=this._grid;
                    newApps.forEach((icon,index) => {
                        const page=Math.floor(index/itemsPerPage), position=index%itemsPerPage;
                        if (addedApps.includes(icon)) this._addItem(icon,page,position);
                        else this._moveItem(icon,page,position);
                    });
                    this._orderedItems=newApps;
                    this.emit('view-loaded');
                });
            console.log('GNOME Customizer: alphabetical app grid enabled');
        }
        try { Main.overview._overview._controls._appDisplay._redisplay(); } catch (_) {}
    }
    _restoreOverviewHoverBackgrounds() {
        for (const [actor,record] of this._overviewHoverActors) {
            try { actor.disconnect(record.hoverId);actor.disconnect(record.destroyId);actor.set_style(record.style); } catch (_) {}
        }
        this._overviewHoverActors.clear();
    }
    _blur(actor, name, sigma, brightness=1.0) {
        actor.remove_effect_by_name(name);
        if (sigma > 0 && actor.width > 0 && actor.height > 0) {
            const effect = new Shell.BlurEffect({mode: Shell.BlurMode.BACKGROUND, brightness, radius: sigma});
            actor.add_effect_with_name(name, effect);
            if (!this._effects.some(([existing, effectName]) => existing === actor && effectName === name)) this._effects.push([actor,name]);
        }
    }
    _styleMenus() {
        if (!this._settings.get_boolean('menu-enabled')) { this._restoreMenus(); return; }
        const visit = actor => {
            if (actor.get_style_class_name?.()?.split(' ').includes('popup-menu-content')) {
                if (!this._menuActors.has(actor)) {
                    const record={style:actor.get_style(),mappedId:0,destroyId:0,source:0};
                    record.mappedId=actor.connect('notify::mapped', () => this._queueMenuStyle(actor));
                    record.destroyId=actor.connect('destroy', () => {
                        if (record.source) GLib.Source.remove(record.source);
                        this._menuActors?.delete(actor);
                        this._effects = this._effects?.filter(([item]) => item !== actor) ?? [];
                    });
                    this._menuActors.set(actor,record);
                }
                this._syncMenuActor(actor);
            }
            for (const child of actor.get_children?.() ?? []) visit(child);
        }; visit(Main.uiGroup);
    }
    _queueMenuStyle(actor) {
        const record=this._menuActors.get(actor);
        if (!record || record.source) return;
        record.source=GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
            record.source=0;if (this._settings?.get_boolean('menu-enabled')) this._syncMenuActor(actor);return GLib.SOURCE_REMOVE;
        });
    }
    _syncMenuActor(actor) {
        const opacity=this._settings.get_double('menu-opacity'), radius=this._settings.get_int('menu-radius'), sigma=this._settings.get_int('menu-blur'), text=this._settings.get_string('menu-text-color'), border=this._settings.get_string('menu-border-color');
        actor.set_style(`${backgroundStyle(this._settings, 'menu', opacity)} border-radius: ${radius}px; color: ${text}; border: 1px solid ${border}; box-shadow: none;`);
        this._blur(actor, 'gnome-customizer-menu-blur', sigma);
    }
    _restoreMenus() {
        for (const [actor,record] of this._menuActors) {
            try {
                if (record.source) GLib.Source.remove(record.source);
                actor.disconnect(record.mappedId);actor.disconnect(record.destroyId);
                actor.remove_effect_by_name('gnome-customizer-menu-blur');actor.set_style(record.style);
            } catch (_) {}
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
            // Keep the tint outside the actor effect. Shell.BlurEffect renders
            // its actor to an offscreen buffer, where a translucent child can
            // be flattened before it is composited into the overview.
            const wallpaper=new St.Widget({x:0,y:0,width:monitor.width,height:monitor.height});
            surface.add_child(wallpaper);
            const manager=new Background.BackgroundManager({container:wallpaper,monitorIndex:i,controlPosition:false});
            this._overviewBackgroundGroup.insert_child_at_index(surface,0);
            this._overviewBackgrounds.push({surface,wallpaper,tint:null,manager});
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
        // A zero tint is a neutral, transparent blur. Brightness and
        // desaturation otherwise leave the dark gray cast visible in the
        // overview even after the color overlay itself is removed.
        const effectiveBrightness=opacity<=0 ? 1 : brightness;
        const effectiveSaturation=opacity<=0 ? 1 : saturation;
        this._overviewBackgroundGroup.visible=enabled;
        for (const item of this._overviewBackgrounds) {
            const {surface,wallpaper} = item;
            wallpaper.remove_effect_by_name('gnome-customizer-overview-blur');
            wallpaper.remove_effect_by_name('gnome-customizer-overview-desaturate');
            const scale=St.ThemeContext.get_for_stage(global.stage).scale_factor;
            if (enabled && sigma>0) wallpaper.add_effect_with_name('gnome-customizer-overview-blur',new Shell.BlurEffect({mode:Shell.BlurMode.ACTOR,brightness:effectiveBrightness,radius:sigma*scale}));
            if (enabled && effectiveSaturation<1) wallpaper.add_effect_with_name('gnome-customizer-overview-desaturate',new Clutter.DesaturateEffect({factor:1-effectiveSaturation}));
            // At zero there is no tint actor in the scene graph. Destroying it
            // is stronger than transparent CSS or actor opacity and makes it
            // impossible for a stale themed paint node to tint the wallpaper.
            if (opacity <= 0) {
                item.tint?.destroy();
                item.tint=null;
            } else {
                if (!item.tint) {
                    item.tint=new St.Widget({x:0,y:0,width:surface.width,height:surface.height});
                    surface.add_child(item.tint);
                }
                item.tint.set_style(`background-color: ${colorWithOpacity(color, opacity)};`);
            }
        }
        Main.layoutManager.overviewGroup.set_style(enabled ? 'background-color: transparent;' : this._overviewStyle);
        const tintActors=this._overviewBackgrounds.filter(item => item.tint !== null).length;
        const desaturateActors=this._overviewBackgrounds.filter(item => item.wallpaper.get_effect('gnome-customizer-overview-desaturate') !== null).length;
        const diagnostic=`${enabled}:${sigma}:${opacity}:${effectiveBrightness}:${effectiveSaturation}:${tintActors}:${desaturateActors}:${this._overviewBackgrounds.length}`;
        if (diagnostic !== this._overviewDiagnostic) { this._overviewDiagnostic=diagnostic;if (enabled) console.log(`GNOME Customizer: overview applied (blur=${sigma}, tint=${opacity}, brightness=${effectiveBrightness}, saturation=${effectiveSaturation}, tintActors=${tintActors}, desaturateActors=${desaturateActors}, monitors=${this._overviewBackgrounds.length})`); }
    }
    _queuePanelStyleRestore() {
        if (this._panelRestoreSource || !this._settings) return;
        // GNOME Shell 50 clears Main.panel.style immediately after emitting
        // `hidden`, so restore our dynamic text style on the following idle.
        this._panelRestoreSource=GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
            this._panelRestoreSource=0;
            if (this._settings) this._syncPanel();
            return GLib.SOURCE_REMOVE;
        });
    }
    _syncPanel() {
        if (this._settings.get_boolean('panel-enabled')) {
            const opacity=this._settings.get_double('panel-opacity'), text=this._settings.get_string('panel-text-color');
            const style=`${backgroundStyle(this._settings, 'panel', opacity)} border-radius: ${this._settings.get_int('panel-radius')}px; color: ${text};`;
            Main.panel.set_style(style);
            this._blur(Main.panel, 'gnome-customizer-panel-blur', opacity>0 ? this._settings.get_int('panel-blur') : 0);
            const styleApplied=Main.panel.get_style()===style, effectApplied=Boolean(Main.panel.get_effect('gnome-customizer-panel-blur'));
            const diagnostic=`${opacity}:${this._settings.get_int('panel-blur')}:${styleApplied}:${effectApplied}`;
            if (diagnostic !== this._panelDiagnostic) { this._panelDiagnostic=diagnostic;console.log(`GNOME Customizer: panel applied (opacity=${opacity}, blur=${this._settings.get_int('panel-blur')}, style=${styleApplied}, effect=${effectApplied})`); }
        } else {
            Main.panel.remove_effect_by_name('gnome-customizer-panel-blur');
            Main.panel.set_style(this._panelStyle);
            this._panelDiagnostic='disabled';
        }
    }
    _sync() {
        if (!this._started) return;
        this._syncAlphabeticalAppGrid();
        this._syncPanel();
        this._syncOverviewBackgrounds();
        this._styleOverviewHoverBackgrounds();
        this._styleMenus();
    }
    disable() {
        if (this._startupComplete) { Main.layoutManager.disconnect(this._startupComplete); this._startupComplete=0; }
        if (this._panelRestoreSource) { GLib.Source.remove(this._panelRestoreSource); this._panelRestoreSource=0; }
        if (this._overviewScanSource) { GLib.Source.remove(this._overviewScanSource); this._overviewScanSource=0; }
        this._settings.disconnect(this._changed);
        if (!this._started) { this._settings=null; return; }
        this._injectionManager.clear();
        try { Main.overview._overview._controls._appDisplay._redisplay(); } catch (_) {}
        Main.layoutManager.disconnect(this._monitors); Main.overview.disconnect(this._overviewShowing); Main.overview.disconnect(this._overviewHidden); Main.layoutManager.overviewGroup.disconnect(this._overviewAdded); Main.uiGroup.disconnect(this._uiAdded);
        this._destroyOverviewBackgrounds();
        this._restoreOverviewHoverBackgrounds();
        Main.panel.remove_effect_by_name('gnome-customizer-panel-blur');
        Main.panel.set_style(this._panelStyle);
        Main.layoutManager.overviewGroup.set_style(this._overviewStyle);
        for (const [actor,name] of this._effects) { try { actor?.remove_effect_by_name(name); } catch (_) {} }
        this._restoreMenus();
        this._effects=[]; this._menuActors=new Map(); this._injectionManager=null; this._settings=null;
    }
}
