python.install_sources(
  'gnome_customizer/__init__.py',
  'gnome_customizer/__main__.py',
  'gnome_customizer/application.py',
  'gnome_customizer/color.py',
  'gnome_customizer/window.py',
  subdir: 'gnome_customizer',
)
python.install_sources(
  'gnome_customizer/backend/__init__.py',
  'gnome_customizer/backend/assets.py',
  'gnome_customizer/backend/app_theme.py',
  'gnome_customizer/backend/constants.py',
  'gnome_customizer/backend/login_theme.py',
  'gnome_customizer/backend/settings.py',
  'gnome_customizer/backend/state.py',
  'gnome_customizer/backend/transactions.py',
  'gnome_customizer/backend/themes.py',
  'gnome_customizer/backend/diagnostics.py',
  'gnome_customizer/backend/system_proxy.py',
  'gnome_customizer/backend/wallpaper.py',
  subdir: 'gnome_customizer/backend',
)
python.install_sources(
  'gnome_customizer/pages/__init__.py',
  'gnome_customizer/pages/preferences.py',
  'gnome_customizer/pages/preview.py',
  'gnome_customizer/pages/themes.py',
  'gnome_customizer/pages/status.py',
  subdir: 'gnome_customizer/pages',
)

launcher = configure_file(input: 'gnome-customizer.in', output: 'gnome-customizer', configuration: {'PYTHON': '/usr/bin/python3'})
install_data(launcher, install_dir: get_option('bindir'), install_mode: 'rwxr-xr-x')
