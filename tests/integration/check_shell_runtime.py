#!/usr/bin/python3
"""Run the companion inside a real isolated headless GNOME Shell session."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
UUID = "gnome-customizer@io.github.gnomecustomizer"


def main() -> None:
    required = ("dbus-run-session", "glib-compile-schemas", "gsettings", "gdbus", "gnome-shell")
    missing = [program for program in required if not shutil.which(program)]
    if missing:
        raise SystemExit(f"Missing runtime-test programs: {', '.join(missing)}")

    install_root = Path(sys.argv[1]).resolve() if len(sys.argv) == 2 else None
    if len(sys.argv) > 2:
        raise SystemExit(f"Usage: {sys.argv[0]} [extracted-package-root]")
    shell_source = (
        install_root / "usr/share/gnome-shell/extensions" / UUID if install_root else ROOT / "shell"
    )
    schema_source = (
        install_root / "usr/share/glib-2.0/schemas/io.github.gnomecustomizer.gschema.xml"
        if install_root
        else ROOT / "data/schemas/io.github.gnomecustomizer.gschema.xml"
    )
    python_source = install_root / "usr/lib/python3/dist-packages" if install_root else ROOT / "src"
    for required_path in (shell_source / "extension.js", shell_source / "schemas", schema_source, python_source):
        if not required_path.exists():
            raise SystemExit(f"Missing runtime-test input: {required_path}")

    with tempfile.TemporaryDirectory(prefix="gnome-customizer-shell-") as temporary:
        base = Path(temporary)
        extension = base / "data/gnome-shell/extensions" / UUID
        extension.mkdir(parents=True)
        (base / "config").mkdir()
        (base / "home").mkdir()
        (base / "runtime").mkdir(mode=0o700)
        (base / "schemas").mkdir()
        for name in ("extension.js", "metadata.json", "stylesheet.css"):
            shutil.copy2(shell_source / name, extension / name)
        shutil.copytree(shell_source / "schemas", extension / "schemas")
        subprocess.run(["glib-compile-schemas", str(extension / "schemas")], check=True)
        shutil.copy2(schema_source, base / "schemas")
        subprocess.run(["glib-compile-schemas", str(base / "schemas")], check=True)

        script = r'''
set -eu
export XDG_DATA_HOME="$SMOKE_ROOT/data"
export XDG_CONFIG_HOME="$SMOKE_ROOT/config"
export XDG_RUNTIME_DIR="$SMOKE_ROOT/runtime"
export GSETTINGS_BACKEND=keyfile
export GSETTINGS_SCHEMA_DIR="$SMOKE_ROOT/schemas"
gsettings set org.gnome.shell disable-user-extensions false
gsettings set org.gnome.shell enabled-extensions '["gnome-customizer@io.github.gnomecustomizer"]'
gsettings set io.github.gnomecustomizer.shell panel-enabled true
gsettings set io.github.gnomecustomizer.shell panel-color '#ff0000'
gsettings set io.github.gnomecustomizer.shell panel-opacity 1.0
gsettings set io.github.gnomecustomizer.shell panel-blur 20
gsettings set io.github.gnomecustomizer.shell overview-enabled true
gsettings set io.github.gnomecustomizer.shell overview-blur 30
gsettings set io.github.gnomecustomizer.shell overview-opacity 0
gsettings set io.github.gnomecustomizer.shell overview-brightness 0.2
gsettings set io.github.gnomecustomizer.shell overview-saturation 0
gsettings set io.github.gnomecustomizer.shell overview-hover-opacity 0.35
gsettings set io.github.gnomecustomizer.shell overview-hover-color '#123456'
gsettings set io.github.gnomecustomizer.shell alphabetical-app-grid true
gnome-shell --wayland --headless --virtual-monitor 1024x768 --no-x11 >"$SMOKE_ROOT/shell.log" 2>&1 &
shell_pid=$!
cleanup() { kill "$shell_pid" 2>/dev/null || true; wait "$shell_pid" 2>/dev/null || true; }
trap cleanup EXIT
ready=false
for _ in $(seq 1 20); do
    if gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.freedesktop.DBus.Peer.Ping >/dev/null 2>&1; then ready=true; break; fi
    sleep 1
done
$ready
sleep 2
gsettings set io.github.gnomecustomizer.shell overview-opacity 0.5
sleep 1
gsettings set io.github.gnomecustomizer.shell overview-opacity 0
sleep 1
export WAYLAND_DISPLAY=wayland-0
if [ "$RUN_ACCENT_DRIVER" = 1 ]; then
    GDK_DEBUG=no-portals PYTHONPATH="$PYTHON_SOURCE" python3 "$ACCENT_DRIVER" >"$SMOKE_ROOT/app.log" 2>&1
else
    : >"$SMOKE_ROOT/app.log"
fi
gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.gnome.Shell.Extensions.GetExtensionInfo gnome-customizer@io.github.gnomecustomizer >"$SMOKE_ROOT/info-before.log"
gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.gnome.Shell.Extensions.GetExtensionErrors gnome-customizer@io.github.gnomecustomizer >"$SMOKE_ROOT/errors-before.log"
gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.gnome.Shell.Extensions.DisableExtension gnome-customizer@io.github.gnomecustomizer >"$SMOKE_ROOT/disable.log"
sleep 1
gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.gnome.Shell.Extensions.EnableExtension gnome-customizer@io.github.gnomecustomizer >"$SMOKE_ROOT/enable.log"
sleep 2
gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.gnome.Shell.Extensions.GetExtensionInfo gnome-customizer@io.github.gnomecustomizer >"$SMOKE_ROOT/info-after.log"
gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.gnome.Shell.Extensions.GetExtensionErrors gnome-customizer@io.github.gnomecustomizer >"$SMOKE_ROOT/errors-after.log"
'''
        environment = os.environ.copy()
        environment["SMOKE_ROOT"] = str(base)
        environment["HOME"] = str(base / "home")
        environment["PYTHON_SOURCE"] = str(python_source)
        environment["ACCENT_DRIVER"] = str(ROOT / "tests/integration/accent_runtime_driver.py")
        isolated_system_bus = environment.get("GNOME_CUSTOMIZER_ISOLATED_SYSTEM_BUS") == "1"
        environment["RUN_ACCENT_DRIVER"] = "0" if isolated_system_bus else "1"
        completed = subprocess.run(
            ["dbus-run-session", "--", "bash", "-c", script],
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        if completed.returncode:
            app_log = (base / "app.log").read_text(errors="replace") if (base / "app.log").exists() else "(no app log)"
            shell_log = (base / "shell.log").read_text(errors="replace") if (base / "shell.log").exists() else "(no shell log)"
            raise SystemExit(
                f"Headless GNOME Shell harness failed:\n{completed.stdout}\n{completed.stderr}"
                f"\nApplication log:\n{app_log}\nShell log:\n{shell_log}"
            )

        before = (base / "info-before.log").read_text()
        after = (base / "info-after.log").read_text()
        errors = (base / "errors-before.log").read_text() + (base / "errors-after.log").read_text()
        controls = (base / "disable.log").read_text() + (base / "enable.log").read_text()
        shell_log = (base / "shell.log").read_text(errors="replace")
        app_log = (base / "app.log").read_text(errors="replace")
        for stage, info in (("initial", before), ("re-enabled", after)):
            if "'state': <1.0>" not in info or "'enabled': <true>" not in info or "'error': <''>" not in info:
                raise SystemExit(f"Companion was not active during {stage} check:\n{info}")
        if errors.count("(@as [],)") != 2:
            raise SystemExit(f"GNOME Shell reported extension errors:\n{errors}")
        if controls.count("(true,)") != 2:
            raise SystemExit(f"Disable/re-enable lifecycle failed:\n{controls}")
        if "GNOME Customizer: panel applied (opacity=1, blur=20, style=true, effect=true)" not in shell_log:
            raise SystemExit("The real GNOME panel did not receive its configured style and blur effect")
        if "GNOME Customizer: overview applied (blur=30, tint=0.5, brightness=0.2, saturation=0, tintActors=1, desaturateActors=1, neutralWallpapers=1, monitors=1)" not in shell_log:
            raise SystemExit("The overview did not receive its configured per-monitor blur")
        neutral="GNOME Customizer: overview applied (blur=30, tint=0, brightness=1, saturation=1, tintActors=0, desaturateActors=0, neutralWallpapers=1, monitors=1)"
        if shell_log.count(neutral) < 2:
            raise SystemExit("Zero tint opacity did not produce a neutral blur before and after a nonzero tint")
        if re.search(r"tint=0, .*tintActors=[1-9]",shell_log):
            raise SystemExit("A tint actor remained in the Shell scene graph at zero opacity")
        if re.search(r"tint=0, .*neutralWallpapers=0",shell_log):
            raise SystemExit("GNOME's background actor still dimmed the wallpaper at zero tint opacity")
        if not re.search(r"GNOME Customizer: overview hover backgrounds tracked \([1-9][0-9]*\)", shell_log):
            raise SystemExit("GNOME Shell did not expose any overview tiles to the hover-background controller")
        if "GNOME Customizer: alphabetical app grid enabled" not in shell_log:
            raise SystemExit("The alphabetical app-grid renderer was not enabled")
        forbidden = re.compile(r"JS ERROR|TypeError|ReferenceError|gnome-customizer-panel-background|needs an allocation|assertion 'width >= 1'", re.I)
        problems = [line for line in shell_log.splitlines() if forbidden.search(line)]
        if isolated_system_bus:
            known_mock_failures = (
                "Could not get a proxy for user",
                'TypeError: can only concatenate str (not "dbus.UInt32") to str',
            )
            problems = [
                line for line in problems
                if not any(message in line for message in known_mock_failures)
            ]
        if problems:
            raise SystemExit("Companion emitted runtime errors:\n" + "\n".join(problems))
        if not isolated_system_bus:
            if re.search(r"Traceback|SettingsError|Gtk-ERROR|Gdk-ERROR", app_log, re.I):
                raise SystemExit("GNOME Customizer application failed under the test compositor:\n" + app_log)
            if "Appearance accent runtime passed" not in app_log:
                raise SystemExit("The Appearance accent end-to-end check did not complete:\n" + app_log)
            print("GNOME runtime check passed: native accent, panel/overview effects, and disable/re-enable clean")
        else:
            print("GNOME runtime check passed: panel/overview effects and disable/re-enable clean")


def run() -> None:
    if os.environ.get("GNOME_CUSTOMIZER_ISOLATED_SYSTEM_BUS") != "1":
        main()
        return

    try:
        from dbusmock import DBusTestCase
    except ImportError as error:
        raise SystemExit("GNOME_CUSTOMIZER_ISOLATED_SYSTEM_BUS requires python3-dbusmock") from error

    DBusTestCase.start_system_bus()
    mock_process = None
    try:
        mock_process, _ = DBusTestCase.spawn_server_template(
            "logind", {}, stdout=subprocess.DEVNULL
        )
        main()
    finally:
        if mock_process is not None:
            mock_process.terminate()
            mock_process.wait(timeout=5)
        DBusTestCase.tearDownClass()


if __name__ == "__main__":
    run()
