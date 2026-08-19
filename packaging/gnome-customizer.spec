Name:           gnome-customizer
Version:        1.05
Release:        12%{?dist}
Summary:        Native GNOME desktop and login-screen customizer
License:        GPL-3.0-or-later
URL:            https://github.com/uk2010/gnome-customizer
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  meson >= 1.3
BuildRequires:  ninja-build
BuildRequires:  python3-devel >= 3.12
BuildRequires:  python3-gobject
BuildRequires:  python3-pillow
BuildRequires:  gtk4-devel >= 4.14
BuildRequires:  libadwaita-devel >= 1.5
BuildRequires:  polkit-devel
BuildRequires:  glib2-devel
BuildRequires:  gsettings-desktop-schemas
BuildRequires:  gnome-shell
BuildRequires:  desktop-file-utils
BuildRequires:  systemd-rpm-macros

Requires:       python3 >= 3.12
Requires:       python3-gobject
Requires:       python3-pillow
Requires:       gtk4 >= 4.14
Requires:       libadwaita >= 1.5
Requires:       polkit
Requires:       gnome-shell >= 50.1
Requires:       gdm
Requires:       gsettings-desktop-schemas
Requires:       glib2
Requires:       glib2-devel
Requires:       dconf
Requires:       systemd
Requires:       (power-profiles-daemon or tuned-ppd)
Requires(post):  glib2
Requires(post):  systemd
Requires(preun): systemd
Requires(postun): systemd

%description
GNOME Customizer is a native GTK4 and Libadwaita application for changing
GNOME desktop, Shell, and GDM appearance settings. Changes are staged before
they are applied. Privileged operations are isolated in a PolicyKit-protected
system helper.

The package is architecture-independent. It is suitable for Fedora aarch64,
including Fedora Asahi Remix, because the application and helper contain only
Python, JavaScript, and data files; GTK, GNOME Shell, GDM, and Polkit remain
native Fedora dependencies supplied by the system.

%prep
%autosetup -n %{name}-%{version}

%build
%meson
%meson_build

%install
%meson_install

%check
GSETTINGS_BACKEND=memory %meson_test --print-errorlogs
desktop-file-validate %{buildroot}%{_datadir}/applications/io.github.gnomecustomizer.desktop

%post
install -d -o root -g root -m 0755 /usr/local/share/gnome-customizer
install -d -o root -g root -m 0755 /usr/local/share/gnome-customizer/assets
install -d -o root -g root -m 0700 /usr/local/share/gnome-customizer/state
if [ -x /usr/bin/glib-compile-schemas ]; then
    /usr/bin/glib-compile-schemas /usr/share/glib-2.0/schemas >/dev/null 2>&1 || :
fi
if [ -x /usr/bin/systemctl ]; then
    /usr/bin/systemctl daemon-reload >/dev/null 2>&1 || :
    if [ "$1" -eq 1 ]; then
        /usr/bin/systemctl preset gnome-customizer-system-helper.service >/dev/null 2>&1 || :
    fi
fi

%preun
if [ "$1" -eq 0 ] && [ -x /usr/bin/systemctl ]; then
    /usr/bin/systemctl disable --now gnome-customizer-system-helper.service >/dev/null 2>&1 || :
fi

%postun
if [ -x /usr/bin/glib-compile-schemas ]; then
    /usr/bin/glib-compile-schemas /usr/share/glib-2.0/schemas >/dev/null 2>&1 || :
fi
if [ -x /usr/bin/systemctl ]; then
    /usr/bin/systemctl daemon-reload >/dev/null 2>&1 || :
fi

%files
%license LICENSE
%doc README.md
%doc %{_docdir}/gnome-customizer/LICENSE
%doc %{_docdir}/gnome-customizer/README.md
%doc %{_docdir}/gnome-customizer/dash-to-dock.md
%{_bindir}/gnome-customizer
%{_libexecdir}/gnome-customizer-system-helper
%{_unitdir}/gnome-customizer-system-helper.service
%{python3_sitelib}/gnome_customizer/
%{_datadir}/applications/io.github.gnomecustomizer.desktop
%{_datadir}/autostart/io.github.gnomecustomizer-extensions.desktop
%{_datadir}/dbus-1/interfaces/io.github.gnomecustomizer.SystemHelper.xml
%{_datadir}/dbus-1/services/io.github.gnomecustomizer.service
%{_datadir}/dbus-1/system-services/io.github.gnomecustomizer.SystemHelper.service
%{_datadir}/dbus-1/system.d/io.github.gnomecustomizer.SystemHelper.conf
%{_datadir}/glib-2.0/schemas/io.github.gnomecustomizer.gschema.xml
%{_datadir}/glib-2.0/schemas/org.gnome.shell.extensions.blur-my-shell.gschema.xml
%{_datadir}/glib-2.0/schemas/org.gnome.shell.extensions.dash-to-dock.gschema.xml
%{_datadir}/gnome-customizer/
%{_datadir}/gnome-shell/extensions/gnome-customizer@io.github.gnomecustomizer/
%{_datadir}/gnome-shell/extensions/blur-my-shell@aunetx/
%{_datadir}/gnome-shell/extensions/dash-to-dock@micxgx.gmail.com/
%{_datadir}/icons/hicolor/scalable/apps/io.github.gnomecustomizer.svg
%{_datadir}/metainfo/io.github.gnomecustomizer.metainfo.xml
%{_datadir}/polkit-1/actions/io.github.gnomecustomizer.policy
