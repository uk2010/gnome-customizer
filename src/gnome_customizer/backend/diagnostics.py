from __future__ import annotations

import platform, re, shutil, subprocess
from pathlib import Path
from .settings import SettingsBackend
from .system_proxy import SystemHelperProxy


def _command(*argv):
    try: return subprocess.run(argv, text=True, capture_output=True, timeout=3, check=False).stdout.strip()
    except (OSError, subprocess.TimeoutExpired): return "Unavailable"


def collect(settings: SettingsBackend, helper: SystemHelperProxy, pending=0) -> dict[str, str]:
    os_name = "Unknown"
    try:
        values = dict(line.split("=", 1) for line in Path("/etc/os-release").read_text().splitlines() if "=" in line)
        os_name = values.get("PRETTY_NAME", "Unknown").strip('"')
    except OSError: pass
    shell_version=_command("gnome-shell", "--version")
    gdm_command = next((candidate for candidate in ("gdm", "gdm3") if shutil.which(candidate)), "gdm")
    result = {
        "Operating System": os_name, "GNOME Shell": shell_version,
        "GDM": _command(gdm_command, "--version"), "Architecture": platform.machine(),
        "Session": (Path("/run/systemd/seats").exists() and "Wayland-compatible") or "Unknown",
        "Pending changes": str(pending),
    }
    match=re.search(r"(\d+)\.(\d+)",shell_version)
    if match:
        version=(int(match.group(1)),int(match.group(2)));result["Compatibility"]="Verified target (GNOME 50.1)" if version==(50,1) else ("Unsupported: GNOME 50.1 or newer is required" if version<(50,1) else f"Newer untested GNOME {version[0]}.{version[1]}; supported settings remain schema-gated")
    for label, schema, key in (
        ("Accent", "org.gnome.desktop.interface", "accent-color"), ("Color scheme", "org.gnome.desktop.interface", "color-scheme"),
        ("Interface font", "org.gnome.desktop.interface", "font-name"), ("Icon theme", "org.gnome.desktop.interface", "icon-theme"),
        ("Cursor theme", "org.gnome.desktop.interface", "cursor-theme"), ("Wallpaper", "org.gnome.desktop.background", "picture-uri")):
        if settings.supports(schema, key): result[label] = "Configured" if label == "Wallpaper" and settings.get(schema,key) else str(settings.get(schema, key))
    if settings.supports("org.gnome.shell","enabled-extensions"):
        result["Shell companion"]="Enabled" if "gnome-customizer@io.github.gnomecustomizer" in settings.get("org.gnome.shell","enabled-extensions") else "Disabled"
    result["Installed theme format"]="1"
    status = helper.status()
    result.update({"System helper": "Available" if status.get("available") else "Unavailable", "GDM account": str(status.get("gdm_user", "Unknown")),
                   "Active GDM resource": str(status.get("active_resource", "Unknown")), "Customizer GDM resource": "Active" if status.get("custom_resource_active") else "Inactive",
                   "GDM dconf override": "Installed" if status.get("dconf_override") else "Not installed", "Login display layout": "Managed" if status.get("monitor_managed") else "Not managed"})
    for key,value in status.get("effective",{}).items():result[f"GDM {key}"]=str(value)
    return result


def safe_report(values: dict[str, str]) -> str:
    private=("Wallpaper","Logo","Banner text")
    return "GNOME Customizer diagnostics\n" + "\n".join(f"{key}: {'Configured (redacted)' if any(x in key for x in private) and value not in ('','None','Unknown') else value}" for key, value in values.items()) + "\n"
