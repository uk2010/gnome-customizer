# `.gctheme` format version 1

`manifest.json` requires `format_version`, `name`, and `author`. It may include `id`, `description`, `minimum_gnome`, `maximum_tested_gnome`, `preview`, `desktop`, `applications`, `shell`, and `login`. Unknown properties are rejected.

Assets use exactly `assets/<safe-name>.(png|jpg|jpeg|webp)`. References are copied into managed storage. The normative machine-readable definition is `data/themes/gnome-customizer-theme.schema.json`; the application additionally applies archive and decoded-image limits.

Surface objects can record whether customization is enabled and select controlled colors, gradient angle, opacity, blur, brightness, saturation, hover-background tint/opacity, app-folder tile/dialog transparency, text/border colors, radius, and shadow. Dock snapshots preserve the installed Ubuntu Dock/Dash-to-Dock extension's native position, Panel Mode, sizing, monitor, contents, visibility, transparency, color, indicator, theme, and corner values. Bounds in the JSON Schema are part of the format; no replacement dock is rendered.

The `applications` palette is retained as preview and interchange metadata. It is not injected into GTK3, GTK4, Libadwaita, or Files because persistent user CSS competes with GNOME Settings. Native GNOME color-scheme, accent, GTK-theme, icon-theme, and cursor-theme keys remain authoritative.

The `desktop.settings` and `login.settings` objects store a complete allowlisted snapshot of every setting exposed by GNOME Customizer, including explicit default, false, and empty values. Login snapshots also store the monitor XML used by GDM, so resolution, scale, orientation, and layout round-trip with the theme. Unknown schemas and keys are rejected. Raw CSS, selectors, arbitrary files, and executable files are never accepted.

To snapshot every setting, open **Themes** and choose **Save as Theme**. The archive includes desktop and login wallpapers, logo state, every supported Desktop and Login Screen control, Shell and dock settings, input, keyboard, power, Night Light, sound, and the login display configuration. Applying it writes the complete snapshot rather than only values that differ from defaults. A newer `minimum_gnome` produces a blocking compatibility message; a newer runtime beyond `maximum_tested_gnome` produces a warning.
