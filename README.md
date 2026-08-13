# GNOME Customizer

GNOME Customizer is a native GTK4/Libadwaita customization application for Ubuntu 26.04 LTS, GNOME Shell 50.1+, GDM 50.1+, and Wayland. It keeps desktop, Shell, and login-screen operations in separate security domains and stages changes before applying them.

It uses native GNOME settings as the single source of truth and never installs persistent GTK color CSS. It does not bundle third-party extensions, run its GUI as root, or allow themes to execute code.

## Architecture

- `src/gnome_customizer`: unprivileged Python/PyGObject application, dynamic GSettings backend, transactions, immutable wallpaper staging, previews, themes, and diagnostics.
- `shell`: focused GJS companion installed as `gnome-customizer@io.github.gnomecustomizer`; controls supported blur and Shell surfaces. Dock controls write the installed Ubuntu Dock/Dash-to-Dock GSettings directly and never create or suppress a dock actor.
- `helper`: root system-bus service. Every mutating call requires `io.github.gnomecustomizer.modify-system` authorization and accepts typed JSON values rather than commands or paths.
- `data`: GSettings, D-Bus interface, PolicyKit policy, desktop/AppStream metadata, icon, theme schema, and samples.
- `debian`: native Debian packaging with safe resource restoration during removal.

The helper owns only `/etc/dconf/db/gdm.d/99-gdm-customizer`, `/usr/local/share/gnome-customizer`, and its managed `/etc/xdg/monitors.xml` state. It validates and compiles a replacement GResource before activating it through `update-alternatives`. It never restarts GDM.

## Build

Install build dependencies on Ubuntu 26.04:

```sh
sudo apt build-dep .
```

Developer build and tests:

```sh
meson setup build
meson compile -C build
meson test -C build --print-errorlogs
DESTDIR="$PWD/stage" meson install -C build
python3 tests/integration/check_install_tree.py "$PWD/stage"
```

Build a native package:

```sh
dpkg-buildpackage -us -uc -b
```

Native amd64 and arm64 builders produce `gnome-customizer_0.3.21_amd64.deb` and `gnome-customizer_0.3.21_arm64.deb`. On an amd64 development host, the architecture-neutral package can also be cross-packaged with `dpkg-buildpackage -us -uc -b -d -aarm64 -Pcross`; Meson uses the documented `debian/cross-arm64.ini`. Cross-packaging verifies package architecture and contents, but the release checklist still requires native arm64 smoke and lifecycle testing.

## Install and uninstall

```sh
sudo apt install ./dist/gnome-customizer_0.3.21_amd64.deb
gnome-customizer
```

Installation does not change GNOME or GDM. The Shell companion is part of the package and is enabled only through an explicit application action. Privileged changes use Ubuntu's normal authentication agent.

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
assets/optional-preview.png
```

Format version 1 permits metadata, wallpapers, GTK/icon/cursor references, application-preview metadata, and bounded panel, dock, menu, overview, and login-surface values. It does not permit scripts, raw CSS, behavioral login options, power settings, keyboard shortcuts, services, extensions, hooks, or arbitrary paths. See [docs/theme-format.md](docs/theme-format.md) and `data/themes/gnome-customizer-theme.schema.json`.

Imports enforce file count and expanded-size limits, reject traversal, absolute paths, backslashes, symlinks, duplicates and unknown files, validate strict UTF-8 JSON and all enums/bounds, decode every image, verify MIME/extension and dimensions, and extract through controlled paths.

## Saving a theme

To capture the currently applied appearance, open **Themes** and choose **Save as Theme**. Save and restore share one audited setting map: the archive includes mode and native accent, wallpaper images and presentation, fonts/icons/cursor, sound theme, clock and battery display, every Top Bar/Blur surface value, and every supported Ubuntu Dock/Dash-to-Dock control including placement and Panel Mode.

Choose **Apply Theme** to restore a local or included theme immediately. Local imported and saved themes also have a trash button with confirmation; included samples are read-only.

## Troubleshooting

- **Authentication cancelled:** no privileged operation is applied; press Apply again when ready.
- **Helper unavailable:** verify `gnome-customizer-system-helper.service` and the system-bus service file are installed.
- **Shell companion unavailable:** verify its directory and compile its local schemas, then log out and back in after package upgrades.
- **Login changes are not visible immediately:** log out or reboot. GNOME Customizer intentionally never restarts GDM.
- **Resource compilation fails:** the active alternative is left unchanged. The Status page reports the active resource.
- **Application appearance:** GNOME Settings remains authoritative; imported application palettes are preview metadata and are not injected as GTK CSS.
- **Restore:** desktop restoration returns values captured before the first Customizer change. Application restore removes only the marked Customizer CSS block; login restore removes only application-owned state.

## Known limitations

Shell internals can change between GNOME releases; the package targets only GNOME 50.1+. Overview and app-grid backgrounds use per-monitor wallpaper actors with controlled blur, tint opacity, brightness, and desaturation; saturation values above the native level are treated as fully saturated. GDM honors only installed schemas and some visual changes become visible after logout/reboot. Preview blur is an approximation because the app does not run a full compositor inside the preview. Desktop monitor arrangement remains in GNOME Settings so its compositor-owned confirmation rollback is preserved; GNOME Customizer can safely copy that layout to GDM.

## Testing and security

Unit tests cover transactions, rollback, restoration, theme schema and hostile archives. Integration checks cover the install tree. The release checklist in [docs/testing.md](docs/testing.md) covers real Shell/GDM, authentication, package lifecycle, amd64, and arm64. Report security issues privately to the project maintainers; diagnostic copying intentionally excludes credentials and unrelated personal data.

License: GPL-3.0-or-later.
