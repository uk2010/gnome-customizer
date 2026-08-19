shell_uuid = 'gnome-customizer@io.github.gnomecustomizer'
shell_dir = datadir / 'gnome-shell/extensions' / shell_uuid
install_data('metadata.json', 'extension.js', 'stylesheet.css', install_dir: shell_dir)
install_data('schemas/io.github.gnomecustomizer.shell.gschema.xml', install_dir: shell_dir / 'schemas')
install_data('blur-my-shell/native-dynamic-blur.js', 'blur-my-shell/NOTICE.md', install_dir: shell_dir / 'blur-my-shell')
subdir('schema-companion')

# Bundle the complete upstream extensions.  The application owns their
# schemas and controls, but the Shell code remains the upstream code so the
# dock and blur features do not depend on a separately installed extension.
blur_uuid = 'blur-my-shell@aunetx'
blur_dir = datadir / 'gnome-shell/extensions' / blur_uuid
blur_vendor = 'vendor/blur-my-shell'
install_data(
  blur_vendor / 'metadata.json',
  blur_vendor / 'LICENSE',
  blur_vendor / 'src/extension.js',
  blur_vendor / 'src/prefs.js',
  blur_vendor / 'src/stylesheet.css',
  install_dir: blur_dir,
)
foreach subdir : ['components', 'conveniences', 'effects', 'preferences', 'dbus', 'styles']
  # install_subdir preserves the source directory name.  Installing to the
  # extension root therefore produces blur_dir/<subdir>, while installing to
  # blur_dir/<subdir> would incorrectly produce blur_dir/<subdir>/<subdir>.
  install_subdir(blur_vendor / 'src' / subdir, install_dir: blur_dir)
endforeach
install_subdir(blur_vendor / 'resources/ui', install_dir: blur_dir)
install_subdir(blur_vendor / 'resources/icons', install_dir: blur_dir)
install_data(blur_vendor / 'schemas/org.gnome.shell.extensions.blur-my-shell.gschema.xml', install_dir: blur_dir / 'schemas')
install_data(blur_vendor / 'schemas/org.gnome.shell.extensions.blur-my-shell.gschema.xml', install_dir: datadir / 'glib-2.0/schemas')
subdir('schema-blur')

if get_option('bundle-dock')
  dock_uuid = 'dash-to-dock@micxgx.gmail.com'
  dock_dir = datadir / 'gnome-shell/extensions' / dock_uuid
  dock_vendor = 'vendor/dash-to-dock'
  install_data(
    dock_vendor / 'extension.js', dock_vendor / 'metadata.json', dock_vendor / 'COPYING',
    dock_vendor / 'README.md', dock_vendor / 'appIconIndicators.js', dock_vendor / 'appIcons.js',
    dock_vendor / 'appIconsDecorator.js', dock_vendor / 'appSpread.js', dock_vendor / 'dash.js',
    dock_vendor / 'dbusmenuUtils.js', dock_vendor / 'desktopIconsIntegration.js', dock_vendor / 'docking.js',
    dock_vendor / 'fileManager1API.js', dock_vendor / 'imports.js', dock_vendor / 'intellihide.js',
    dock_vendor / 'launcherAPI.js', dock_vendor / 'locations.js', dock_vendor / 'locationsWorker.js',
    dock_vendor / 'notificationsMonitor.js', dock_vendor / 'prefs.js', dock_vendor / 'theming.js',
    dock_vendor / 'utils.js', dock_vendor / 'windowPreview.js', install_dir: dock_dir,
  )
  install_subdir(dock_vendor / 'dependencies', install_dir: dock_dir)
  install_subdir(dock_vendor / 'media', install_dir: dock_dir)
  install_data(dock_vendor / 'Settings.ui', install_dir: dock_dir)
  install_data(dock_vendor / 'schemas/org.gnome.shell.extensions.dash-to-dock.gschema.xml', install_dir: dock_dir / 'schemas')
  install_data(dock_vendor / 'schemas/org.gnome.shell.extensions.dash-to-dock.gschema.xml', install_dir: datadir / 'glib-2.0/schemas')
  subdir('schema-dock')
endif
