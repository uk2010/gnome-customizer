# GNOME Customizer

GNOME Customizer is a native GTK4/Libadwaita customization application for Fedora Linux Asahi Remix 44, GNOME Shell 50.1+, GDM 50.1+, and Wayland. It keeps desktop, Shell, and login-screen operations in separate security domains and stages changes before applying them. The Fedora package is architecture-independent and is intended to run natively on aarch64 Apple Silicon systems.

![GNOME Customizer](Screenshots/Screenshot%20From%202026-08-22%2002-51-01.png)

It uses native GNOME settings as the source of truth. The optional Files transparency control writes one marked, Nautilus-only block to the user's GTK 4 stylesheet and removes that block exactly when disabled. Fedora packages include the complete upstream Blur My Shell and Dash to Dock extension payloads; Ubuntu/Debian packages use the distro's Ubuntu Dock or Dash to Dock package to avoid conflicting with its shared schema file. The GUI remains unprivileged and themes cannot execute code.

## Architecture

- `src/gnome_customizer`: unprivileged Python/PyGObject application, dynamic GSettings backend, transactions, immutable wallpaper staging, themes, and diagnostics.
- `shell`: GNOME Customizer's companion plus the complete upstream `blur-my-shell@aunetx` and optional `dash-to-dock@micxgx.gmail.com` extensions. Their schemas and controls are integrated into the application. Ubuntu Dock is preferred when it is already present; otherwise the bundled Dash to Dock is enabled.
- `helper`: root system-bus service. Every mutating call requires `io.github.gnomecustomizer.modify-system` authorization and accepts typed JSON values rather than commands or paths.
- `data`: GSettings, D-Bus interface, PolicyKit policy, desktop/AppStream metadata, icon, theme schema, and samples.
- `packaging/gnome-customizer.spec`: Fedora RPM packaging with the complete build and runtime dependency set.
- `debian`: Debian packaging retained for Ubuntu builds.

The helper owns its GDM dconf state, `/usr/local/share/gnome-customizer`, and the managed GDM account monitor configuration. It validates and compiles a replacement GResource before activating it through the platform's alternatives implementation (`update-alternatives` on Debian or `alternatives` on Fedora). It never restarts GDM.

## Build on Fedora Linux Asahi Remix 44

Install the system dependencies and RPM build tools:

```sh
sudo dnf install \
  @development-tools rpm-build rpmdevtools meson ninja-build \
  python3-devel python3-gobject python3-pillow \
  gtk4-devel libadwaita-devel polkit-devel glib2-devel \
  gsettings-desktop-schemas gnome-shell gdm desktop-file-utils \
  systemd-rpm-macros
```

Build and test the local application:

```sh
meson setup build-fedora --prefix=/usr --libexecdir=/usr/libexec
meson compile -C build-fedora
meson test -C build-fedora --print-errorlogs
DESTDIR="$PWD/stage-fedora" meson install -C build-fedora
python3 tests/integration/check_install_tree.py "$PWD/stage-fedora"
```

Build the architecture-independent Fedora RPM:

```sh
./packaging/build-fedora-rpm.sh
```

The resulting RPM is written to `.rpmbuild/RPMS/noarch/`. Install it on the Asahi system with:

```sh
sudo dnf install .rpmbuild/RPMS/noarch/gnome-customizer-1.05*.noarch.rpm
gnome-customizer
```

The RPM declares the GTK, Libadwaita, PyGObject, Pillow, GNOME Shell, GDM, Polkit, dconf, systemd, and power-profile provider dependencies. Fedora can satisfy the power-profile feature with either `power-profiles-daemon` or its `tuned-ppd` provider. Those system components stay native to Fedora/aarch64; they are not copied into the application package.

The package does not enable or start the helper service during installation. The application activates it over the system D-Bus only when a privileged login-screen operation is applied. On first launch, the app enables the bundled blur and dock extensions when the desktop does not already provide them. Ubuntu/Debian builds use the installed Ubuntu Dock or Dash to Dock provider instead of installing a second copy of its shared schema.

The Dock page writes the upstream Dash to Dock schema and includes the full placement, visibility, appearance, interaction, and shortcut controls. Ubuntu's `ubuntu-dock@ubuntu.com` is used when available; otherwise the packaged upstream Dash to Dock actor supplies the dock without a separate extension download.

## Build on Ubuntu/Debian

Install build dependencies on Ubuntu 26.04:

```sh
sudo apt build-dep .
```

Developer build and tests:

```sh
meson setup build --prefix=/usr --libexecdir=/usr/libexec -Dbundle-dock=false
meson compile -C build
meson test -C build --print-errorlogs
DESTDIR="$PWD/stage" meson install -C build
python3 tests/integration/check_install_tree.py "$PWD/stage"
```

Build a native package:

```sh
dpkg-buildpackage -us -uc -b
```

Native amd64 and arm64 builders produce architecture-matched `.deb` packages. On an amd64 development host, the package can also be cross-packaged with `dpkg-buildpackage -us -uc -b -d -aarm64 -Pcross`; Meson uses the documented `debian/cross-arm64.ini`. Cross-packaging verifies package architecture and contents, but the release checklist still requires native arm64 smoke and lifecycle testing.

## Install and uninstall on Fedora

```sh
sudo dnf install .rpmbuild/RPMS/noarch/gnome-customizer-1.05*.noarch.rpm
gnome-customizer
```

To remove it:

```sh
sudo dnf remove gnome-customizer
```

Before removal, the helper restores a valid previous or stock GDM resource if the custom resource is active. Unrelated dconf overrides and extensions are never removed.

## Install and uninstall on Ubuntu/Debian

```sh
sudo apt install ./gnome-customizer_1.05-19_amd64.deb
gnome-customizer
```

The Debian package includes `libglib2.0-bin`, which supplies the GLib resource compiler used for login-screen themes. No separate `gresource` command is required.

Installation does not change GNOME or GDM. The Shell companion is part of the package; a small GNOME-session helper keeps selected bundled Shell extensions enabled without opening the application. Privileged changes use Ubuntu/Debian's normal PolicyKit authentication agent.

```sh
sudo apt remove gnome-customizer
sudo apt purge gnome-customizer
```

Before removal, the maintainer script restores a valid previous or stock GDM resource if the custom resource is active. Purge additionally removes the application-owned GDM override and state. Unrelated dconf overrides and extensions are never removed.

## Theme format

`.gctheme` is a ZIP-compatible, versioned appearance archive:

```text
manifest.json
assets/optional-wallpaper.webp
assets/optional-login-wallpaper.webp
assets/optional-preview.png
```

Format version 1 permits metadata, wallpapers, GTK/icon/cursor references, application-preview metadata, bounded surface values, and allowlisted complete Desktop and Login Screen settings snapshots, including the GDM monitor layout. It does not permit scripts, raw CSS, services, extensions, hooks, unknown settings, or arbitrary paths. See [docs/theme-format.md](docs/theme-format.md) and `data/themes/gnome-customizer-theme.schema.json`.

Imports enforce file count and expanded-size limits, reject traversal, absolute paths, backslashes, symlinks, duplicates and unknown files, validate strict UTF-8 JSON and all enums/bounds, decode every image, verify MIME/extension and dimensions, and extract through controlled paths.

## Saving a theme

To capture the currently applied appearance, open **Themes** and choose **Save as Theme**. Save and restore share one audited setting map: the archive includes mode and native accent, wallpaper images and presentation, fonts/icons/cursor, sound theme, clock and battery display, every Top Bar/Blur surface value, and every supported Ubuntu Dock/Dash-to-Dock control including placement and Panel Mode.

Choose **Apply Theme** to restore a local or included theme immediately. Local imported and saved themes also have a trash button with confirmation; included samples are read-only.

## Troubleshooting

- **Authentication cancelled or unavailable:** no privileged operation is applied. On Ubuntu/Debian, make sure `policykit-1-gnome` is installed and that the graphical session has been restarted; it supplies the password dialog used by the login-screen helper.
- **Helper unavailable:** verify `gnome-customizer-system-helper.service` and the system-bus service file are installed.
- **Shell companion unavailable:** verify its directory and compile its local schemas, then log out and back in after package upgrades.
- **Blur My Shell:** the complete extension is included in the package and controlled from the Blur page; installing it separately is unnecessary.
- **Login changes are not visible immediately:** log out or reboot. GNOME Customizer intentionally never restarts GDM.
- **Resource compilation fails:** the active alternative is left unchanged. The Status page reports the active resource.
- **Application appearance:** GNOME Settings remains authoritative; imported application palettes are interchange metadata and are not injected as GTK CSS.
- **Files transparency:** turn the switch off and Apply before uninstalling to remove its marked GTK 4 CSS block. Close and reopen Files after changing it.
- **Restore:** desktop restoration returns values captured before the first Customizer change. Application restore removes only the marked Customizer CSS block; login restore removes only application-owned state.

## Known limitations

Shell internals can change between GNOME releases; the package targets only GNOME 50.1+. Overview and app-grid backgrounds use per-monitor wallpaper actors with controlled blur, tint opacity, brightness, and desaturation; saturation values above the native level are treated as fully saturated. Files transparency is background alpha only because Nautilus does not expose a supported background-blur API. GDM honors only installed schemas and some visual changes become visible after logout/reboot. Desktop monitor arrangement remains in GNOME Settings so its compositor-owned confirmation rollback is preserved; GNOME Customizer can safely copy that layout to GDM.

## Testing and security

Unit tests cover transactions, rollback, restoration, theme schema and hostile archives. Integration checks cover the install tree. The release checklist in [docs/testing.md](docs/testing.md) covers real Shell/GDM, authentication, package lifecycle, amd64, and arm64. Report security issues privately to the project maintainers; diagnostic copying intentionally excludes credentials and unrelated personal data.

License: GPL-3.0-or-later.
