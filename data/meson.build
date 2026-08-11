desktop_file = i18n.merge_file(
  input: 'desktop/io.github.gnomecustomizer.desktop.in',
  output: 'io.github.gnomecustomizer.desktop',
  type: 'desktop',
  po_dir: '../po',
  install: true,
  install_dir: datadir / 'applications',
)

appstream_file = i18n.merge_file(
  input: 'appstream/io.github.gnomecustomizer.metainfo.xml.in',
  output: 'io.github.gnomecustomizer.metainfo.xml',
  type: 'xml',
  po_dir: '../po',
  install: true,
  install_dir: datadir / 'metainfo',
)

install_data('icons/hicolor/scalable/apps/io.github.gnomecustomizer.svg', install_dir: datadir / 'icons/hicolor/scalable/apps')
install_data('schemas/io.github.gnomecustomizer.gschema.xml', install_dir: datadir / 'glib-2.0/schemas')
install_data('polkit/io.github.gnomecustomizer.policy', install_dir: datadir / 'polkit-1/actions')
install_data('dbus/io.github.gnomecustomizer.SystemHelper.xml', install_dir: datadir / 'dbus-1/interfaces')
install_data('dbus/io.github.gnomecustomizer.SystemHelper.service', install_dir: datadir / 'dbus-1/system-services')
install_data('dbus/io.github.gnomecustomizer.service', install_dir: datadir / 'dbus-1/services')
install_data('dbus/io.github.gnomecustomizer.SystemHelper.conf', install_dir: datadir / 'dbus-1/system.d')
install_data('themes/gnome-customizer-theme.schema.json', install_dir: datadir / 'gnome-customizer')
install_data('themes/Aurora.json', install_dir: datadir / 'gnome-customizer/themes')
install_data('themes/Aurora.gctheme', 'themes/Ember.gctheme', install_dir: datadir / 'gnome-customizer/sample-themes')
