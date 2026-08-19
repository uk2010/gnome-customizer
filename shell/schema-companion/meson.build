custom_target(
  'gnome-customizer-shell-compiled-schemas',
  output: 'gschemas.compiled',
  command: [find_program('glib-compile-schemas'), '--targetdir', '@OUTDIR@', meson.project_source_root() / 'shell/schemas'],
  depend_files: meson.project_source_root() / 'shell/schemas/io.github.gnomecustomizer.shell.gschema.xml',
  install: true,
  install_dir: shell_dir / 'schemas',
)
