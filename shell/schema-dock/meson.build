custom_target(
  'dash-to-dock-compiled-schemas',
  output: 'gschemas.compiled',
  command: [find_program('glib-compile-schemas'), '--targetdir', '@OUTDIR@', meson.project_source_root() / 'shell/vendor/dash-to-dock/schemas'],
  depend_files: meson.project_source_root() / 'shell/vendor/dash-to-dock/schemas/org.gnome.shell.extensions.dash-to-dock.gschema.xml',
  install: true,
  install_dir: dock_dir / 'schemas',
)
