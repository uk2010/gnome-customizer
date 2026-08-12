# `.gctheme` format version 1

`manifest.json` requires `format_version`, `name`, and `author`. It may include `id`, `description`, `minimum_gnome`, `maximum_tested_gnome`, `preview`, `desktop`, `applications`, `shell`, and `login`. Unknown properties are rejected.

Assets use exactly `assets/<safe-name>.(png|jpg|jpeg|webp)`. References are copied into managed storage. The normative machine-readable definition is `data/themes/gnome-customizer-theme.schema.json`; the application additionally applies archive and decoded-image limits.

Surface objects can record whether customization is enabled and select controlled colors, gradient angle, opacity, blur, brightness, saturation, hover-background tint/opacity, text/border colors, radius, and shadow. Dock snapshots preserve the installed Ubuntu Dock/Dash-to-Dock extension's native position, Panel Mode, sizing, monitor, contents, visibility, transparency, color, indicator, theme, and corner values. Bounds in the JSON Schema are part of the format; no replacement dock is rendered.

The `applications` palette is retained as preview and interchange metadata. It is not injected into GTK3, GTK4, Libadwaita, or Files because persistent user CSS competes with GNOME Settings. Native GNOME color-scheme, accent, GTK-theme, icon-theme, and cursor-theme keys remain authoritative.

Behavioral options such as user-list visibility, authentication, restart buttons, power behavior, input settings, or display layout cannot appear in a theme. Raw CSS, selectors, arbitrary files, and executable files are never accepted.

To snapshot the applied appearance, open **Themes** and choose **Save as Theme**. The snapshot uses the same mapping when restored and includes every supported control on Appearance, Fonts/Icons/Cursor, Dock, Blur, and Top Bar, plus the selected sound theme. Hardware and behavioral pages such as input, power, Night Light, and displays are intentionally not appearance themes. To author one manually, use the in-app Theme Builder, preview each surface, enter metadata, and choose Export Theme. Imported version-1 themes can be opened for editing after validation. A newer `minimum_gnome` produces a blocking compatibility message; a newer runtime beyond `maximum_tested_gnome` produces a warning.
