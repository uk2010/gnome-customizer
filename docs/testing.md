# Release test checklist

Automated: Python compile, strict schema compile, unit tests, Meson install, AppStream/desktop validation, Debian package build, package-content audit, hostile themes, failed transaction rollback.

Native Ubuntu 26.04 / GNOME 50.1: desktop wallpaper, light/dark wallpaper, all detected accents, color scheme, icons, cursor, fonts, clock, mouse/touchpad, sound, power, Night Light, dock positions/hide/running/favorites/multiple monitors, panel/dock/overview/menu blur, restore.

GDM: wallpaper/color, resource validation and alternatives, clock/date/weekday/seconds/battery, logo/banner, user list, power buttons, accessibility, sound/input/power schemas where present, display copy/restore, logout visibility, no automatic restart.

Failure paths: cancelled/failed authentication, helper absent, invalid/missing image, compilation failure, partial desktop transaction, malformed/traversal/symlink/duplicate/oversized/Unicode/version-mismatch themes.

Packages on native amd64 and arm64: clean install, upgrade, remove, purge, active-resource uninstall, restored previous alternative, no unrelated dconf or extension changes.

## Current release evidence (0.3.0, 2026-08-11)

- Ubuntu 26.04 amd64 host with GNOME Shell 50.1, GDM 50.1, GTK 4.22.4, Libadwaita 1.9.1, and Python 3.14.
- 46 unit/security tests pass, including unsafe-contrast rejection, legacy CSS migration, coordinated application presets, post-allocation dock anchoring, complete managed-default reset, surface-alpha rendering, controlled application-palette validation, GTK CSS preservation/restore, immutable wallpaper staging, light/dark wallpaper targeting, desktop transaction rollback, extension-list preservation, restore rollback, failed first-activation cleanup, malicious theme archives, Unicode-only names, dconf injection resistance, image validation, actual GResource compilation from the installed Yaru resource, GDM setting merge, and monitor XML restore.
- A real 0.1.0 installation exposed and reproduced a helper activation failure (`226/NAMESPACE`) when its managed `/usr/local/share/gnome-customizer` path did not yet exist. Version 0.1.1 creates the resource, asset, and private state directories in `postinst` before D-Bus activation; the package audit verifies both the maintainer script and the hardened service payload.
- A real 0.1.1 graphical launch exposed a remote/sessionless PolicyKit classification and fixed-name wallpaper overwrite. Version 0.1.2 requires administrator authentication for every session class and uses immutable content-addressed files so selection remains staged until Apply.
- Version 0.2.0 constructs a 16-page desktop UI with a full Files/application palette and preview under isolated GTK4/Libadwaita without warnings. Generated GTK4 CSS parses successfully, unrelated GTK3/GTK4 user CSS survives apply/restore, and a nested GNOME Shell 50.1 session loads both Ubuntu Dock and the Customizer companion without extension errors while the companion suppresses the duplicate dock actor.
- Version 0.2.1 adds the replacement dock's own Show Applications button and verifies that it targets GNOME Shell's app-grid state while remaining enabled by default.
- Version 0.2.2 uses GNOME's session-specific grid icon, makes the button a checked toggle that closes the overview on its second click, supports first/last placement, renders per-monitor blurred wallpaper backgrounds behind the app grid, formats Night Light schedules using the user's 12/24-hour preference, applies opacity through background alpha, exposes native color dialogs, and verifies mouse/touchpad writes.
- Version 0.2.3 repositions the dock after GNOME Shell reports its final startup allocation and clamps the resulting geometry to its monitor, preventing the partially off-screen dock seen immediately after login. Its GNOME Defaults action resets all managed desktop and Shell keys, application CSS, wallpaper copies, and GDM state while preserving unrelated extensions.
- Light, Dark, and High Contrast presets generate distinct, strictly parsed scoped CSS and synchronize every Windows & Files control and preview.
- Version 0.2.4 removes global Libadwaita semantic-color redefinitions, scopes managed selectors away from the Customizer window, and migrates the legacy managed CSS block before GTK initializes.
- Version 0.3.0 removes application CSS generation from normal apply paths, retires legacy managed CSS at startup, and makes panel, menu, dock, and overview styling explicitly opt-in so native GNOME settings remain authoritative.
- Strict GSettings compilation, Python compilation, XML validation, JavaScript syntax validation, Meson test/install, desktop-file validation, AppStream validation, install-tree audit, and Shell-extension packing pass.
- Native amd64 package build and architecture/content audit pass. The architecture-neutral arm64 package cross-build and content audit pass; native arm64 runtime/lifecycle verification remains a release-machine checklist item and is not claimed here.
- The full application constructs with all detected GNOME 50 schemas under an isolated display (15 Desktop pages, 7 Login Screen pages, 45 Theme Builder controls, four previews, and zero startup-staged changes). Wide and collapsed navigation layouts were exercised without GTK/Libadwaita layout warnings.
- An isolated headless GNOME Shell 50.1 Wayland compositor loaded the packaged companion, applied live dock position/indicator/overview changes, disabled it, re-enabled it, and shut down without companion errors or critical warnings. Visual multi-monitor/overlap behavior remains on the native interactive checklist.
- Live GDM authentication, logout appearance, and package lifecycle remain intentionally listed above for native release-machine verification; automated tests do not alter the developer's active login screen or session.
Run the real compositor smoke test on a GNOME 50 development host:

```sh
python3 tests/integration/check_shell_runtime.py
```

It starts an isolated headless GNOME Shell with a virtual monitor, drives the real Appearance accent control through Apply, verifies the native GNOME accent value and Yaru migration, confirms panel and overview blur effects, finds real overview icons for hover-opacity control, and exercises disable/re-enable cleanup.
