project('gnome-customizer', version: '0.3.30', meson_version: '>=1.3.0', default_options: ['prefix=/usr'])

gnome = import('gnome')
i18n = import('i18n')
python = import('python').find_installation('python3')
prefix = get_option('prefix')
datadir = prefix / get_option('datadir')
libdir = prefix / get_option('libdir')

subdir('data')
subdir('src')
subdir('helper')
subdir('shell')

install_data('README.md', 'LICENSE', install_dir: datadir / 'doc/gnome-customizer')

gnome.post_install(
  glib_compile_schemas: true,
  gtk_update_icon_cache: true,
  update_desktop_database: true,
)

test_env = environment()
test_env.set('PYTHONPATH', meson.project_source_root() / 'src')
test('unit', python, args: ['-m', 'unittest', 'discover', '-s', meson.project_source_root() / 'tests/unit', '-v'], env: test_env)
