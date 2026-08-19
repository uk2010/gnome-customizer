/*
 * Native dynamic blur renderer adapted from Blur My Shell.
 * Upstream: https://github.com/aunetx/blur-my-shell
 * Source revision: 9129ba71aff425176b34ec3dce65ad21de4ba6f5
 *
 * Blur My Shell is licensed under the GNU General Public License, version 3
 * or later.  This file is kept separate so the attribution and adaptation
 * boundary remain clear.
 */

import GObject from 'gi://GObject';
import St from 'gi://St';
import Shell from 'gi://Shell';

let BlurOrShell = Shell;
try {
    const blurModule = await import('gi://Blur');
    if (blurModule?.BlurEffect?.$gtype)
        BlurOrShell = blurModule;
} catch (_) {
    // GNOME Customizer works with the stock Shell.BlurEffect. The optional
    // Blur module only adds native rounded-corner properties when present.
}

const supportsCornerRadius = Boolean(
    BlurOrShell?.BlurEffect?.list_properties?.()
        ?.some(property => property.name === 'corner-radius')
);

const DEFAULT_PARAMS = {
    unscaled_radius: 30,
    brightness: 0.6,
    unscaled_corner_radius: 0,
};

function setParams(effect, params) {
    for (const name of Object.keys(DEFAULT_PARAMS))
        effect[`_${name}`] = null;
    for (const [name, defaultValue] of Object.entries(DEFAULT_PARAMS))
        effect[name] = name in params ? params[name] : defaultValue;
}

export const NativeDynamicBlurEffect = GObject.registerClass({
    GTypeName: 'GnomeCustomizerNativeDynamicBlurEffect',
}, class NativeDynamicBlurEffect extends BlurOrShell.BlurEffect {
    constructor(params = {}) {
        const normalized = {...params};
        if (!('unscaled_radius' in normalized) && 'radius' in normalized)
            normalized.unscaled_radius = normalized.radius;
        delete normalized.radius;
        if (!('unscaled_corner_radius' in normalized) && 'corner_radius' in normalized)
            normalized.unscaled_corner_radius = normalized.corner_radius;
        delete normalized.corner_radius;

        const parentParams = {...normalized};
        delete parentParams.unscaled_radius;
        delete parentParams.brightness;
        delete parentParams.unscaled_corner_radius;
        super({...parentParams, mode: BlurOrShell.BlurMode.BACKGROUND});

        this._themeContext = St.ThemeContext.get_for_stage(global.stage);
        this._scaleChanged = this._themeContext.connect('notify::scale-factor', () => this._syncScale());
        setParams(this, normalized);
    }

    static get default_params() {
        return DEFAULT_PARAMS;
    }

    get unscaled_radius() {
        return this._unscaled_radius;
    }

    set unscaled_radius(value) {
        this._unscaled_radius = value;
        this._syncScale();
    }

    get unscaled_corner_radius() {
        return this._unscaled_corner_radius;
    }

    set unscaled_corner_radius(value) {
        this._unscaled_corner_radius = value;
        if (supportsCornerRadius)
            this.corner_radius = value * this._themeContext.scale_factor;
    }

    _syncScale() {
        if (!this._themeContext)
            return;
        this.radius = Math.max(0, this._unscaled_radius * this._themeContext.scale_factor);
        if (supportsCornerRadius)
            this.corner_radius = this._unscaled_corner_radius * this._themeContext.scale_factor;
    }

    vfunc_dispose() {
        if (this._themeContext && this._scaleChanged) {
            this._themeContext.disconnect(this._scaleChanged);
            this._scaleChanged = 0;
        }
        if (super.vfunc_dispose)
            super.vfunc_dispose();
    }
});
