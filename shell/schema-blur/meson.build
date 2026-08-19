custom_target(
  'blur-my-shell-compiled-schemas',
  output: 'gschemas.compiled',
  command: [find_program('glib-compile-schemas'), '--targetdir', '@OUTDIR@', meson.project_source_root() / 'shell/vendor/blur-my-shell/schemas'],
  depend_files: meson.project_source_root() / 'shell/vendor/blur-my-shell/schemas/org.gnome.shell.extensions.blur-my-shell.gschema.xml',
  install: true,
  install_dir: blur_dir / 'schemas',
)
