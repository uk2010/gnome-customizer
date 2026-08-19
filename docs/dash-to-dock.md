# Dash to Dock integration

GNOME Customizer uses the native `org.gnome.shell.extensions.dash-to-dock` GSettings schema exposed by Ubuntu Dock and Dash to Dock. This keeps the installed dock as the only dock actor and works with either extension UUID:

- `ubuntu-dock@ubuntu.com`
- `dash-to-dock@micxgx.gmail.com`

The Dock page is schema-gated, so controls appear only when the installed extension exposes them. The page covers layout, monitors, contents, visibility, transparency, indicators, interaction, previews, and shortcuts. Theme export/import uses the same allowlisted scalar settings.

The Fedora build can provide the upstream Dash to Dock payload. The Ubuntu/Debian build depends on the distribution's Ubuntu Dock or Dash to Dock package, because those packages already own the shared system schema filename.

The integration follows the upstream Dash to Dock schema and behavior. Upstream source: <https://github.com/micheleg/dash-to-dock>, revision `ef2e761a1a2da69400ec5202d1f383992a0d0404`. Dash to Dock is GPL-2.0-or-later; its source and license remain available from the upstream project.
