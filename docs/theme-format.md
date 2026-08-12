# `.gctheme` format version 1

`manifest.json` requires `format_version`, `name`, and `author`. It may include `id`, `description`, `minimum_gnome`, `maximum_tested_gnome`, `preview`, `desktop`, `applications`, `shell`, and `login`. Unknown properties are rejected.

Assets use exactly `assets/<safe-name>.(png|jpg|jpeg|webp)`. References are copied into managed storage. The normative machine-readable definition is `data/themes/gnome-customizer-theme.schema.json`; the application additionally applies archive and decoded-image limits.

Surface objects can select controlled colors, gradient angle, opacity, blur, brightness, saturation, text/border colors, radius, shadow, dock size/spacing, and a fixed indicator enum. Bounds in the JSON Schema are part of the format. The renderer—not the theme—translates these values to GNOME 50 behavior. Dock themes are applied through the installed Ubuntu Dock/Dash-to-Dock settings; unsupported legacy dock fields are ignored rather than rendered by a replacement dock.

The `applications` palette is retained as preview and interchange metadata. It is not injected into GTK3, GTK4, Libadwaita, or Files because persistent user CSS competes with GNOME Settings. Native GNOME color-scheme, accent, GTK-theme, icon-theme, and cursor-theme keys remain authoritative.

Behavioral options such as user-list visibility, authentication, restart buttons, power behavior, input settings, or display layout cannot appear in a theme. Raw CSS, selectors, arbitrary files, and executable files are never accepted.

To author a theme, use the in-app Theme Builder, preview each surface, enter metadata, and choose Export Theme. Imported version-1 themes can be opened for editing after validation. A newer `minimum_gnome` produces a blocking compatibility message; a newer runtime beyond `maximum_tested_gnome` produces a warning.
