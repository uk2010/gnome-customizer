helper = configure_file(input: 'gnome-customizer-system-helper.in', output: 'gnome-customizer-system-helper', configuration: {'PYTHON': python.full_path()})
install_data(helper, install_dir: get_option('libexecdir'), install_mode: 'rwxr-xr-x')
install_data('gnome-customizer-system-helper.service', install_dir: prefix / 'lib/systemd/system')
