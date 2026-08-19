#!/usr/bin/python3
from pathlib import Path
import sys
root=Path(sys.argv[1])
python_roots=[root/"usr/lib/python3/dist-packages",root/"usr/lib/python3/site-packages"]
python_root=next((path for path in python_roots if path.is_dir()),python_roots[0])
required=["usr/bin/gnome-customizer","usr/share/applications/io.github.gnomecustomizer.desktop","usr/share/autostart/io.github.gnomecustomizer-extensions.desktop","usr/share/metainfo/io.github.gnomecustomizer.metainfo.xml","usr/libexec/gnome-customizer-system-helper","usr/share/polkit-1/actions/io.github.gnomecustomizer.policy","usr/share/gnome-shell/extensions/gnome-customizer@io.github.gnomecustomizer/extension.js","usr/share/gnome-shell/extensions/gnome-customizer@io.github.gnomecustomizer/blur-my-shell/native-dynamic-blur.js","usr/share/gnome-shell/extensions/gnome-customizer@io.github.gnomecustomizer/blur-my-shell/NOTICE.md"]
launcher=(root/"usr/bin/gnome-customizer").read_text()
if "dist-packages" not in launcher or "site-packages" not in launcher:
    raise SystemExit("Launcher must locate both Debian and Fedora Python package paths")
required.extend([
    "usr/share/gnome-shell/extensions/blur-my-shell@aunetx/extension.js",
    "usr/share/gnome-shell/extensions/blur-my-shell@aunetx/metadata.json",
    "usr/share/gnome-shell/extensions/blur-my-shell@aunetx/components/panel.js",
    "usr/share/gnome-shell/extensions/blur-my-shell@aunetx/preferences/panel.js",
    "usr/share/gnome-shell/extensions/blur-my-shell@aunetx/schemas/org.gnome.shell.extensions.blur-my-shell.gschema.xml",
    "usr/share/gnome-shell/extensions/blur-my-shell@aunetx/schemas/gschemas.compiled",
    "usr/share/glib-2.0/schemas/org.gnome.shell.extensions.blur-my-shell.gschema.xml",
    "usr/share/gnome-shell/extensions/gnome-customizer@io.github.gnomecustomizer/schemas/gschemas.compiled",
])
if (root/"usr/share/gnome-shell/extensions/dash-to-dock@micxgx.gmail.com/extension.js").is_file():
    required.extend([
        "usr/share/gnome-shell/extensions/dash-to-dock@micxgx.gmail.com/metadata.json",
        "usr/share/gnome-shell/extensions/dash-to-dock@micxgx.gmail.com/dependencies/gi.js",
        "usr/share/gnome-shell/extensions/dash-to-dock@micxgx.gmail.com/media/logo.svg",
        "usr/share/gnome-shell/extensions/dash-to-dock@micxgx.gmail.com/schemas/org.gnome.shell.extensions.dash-to-dock.gschema.xml",
        "usr/share/gnome-shell/extensions/dash-to-dock@micxgx.gmail.com/schemas/gschemas.compiled",
        "usr/share/glib-2.0/schemas/org.gnome.shell.extensions.dash-to-dock.gschema.xml",
    ])
required.extend(str(path.relative_to(root)) for path in (python_root/"gnome_customizer/color.py",python_root/"gnome_customizer/backend/app_theme.py",python_root/"gnome_customizer/backend/assets.py",python_root/"gnome_customizer/backend/login_theme.py",python_root/"gnome_customizer/backend/wallpaper.py"))
missing=[x for x in required if not (root/x).exists()]
if missing:raise SystemExit("Missing install files: "+", ".join(missing))
bad=[str(path.relative_to(root)) for path in (
    root/"usr/share/gnome-shell/extensions/blur-my-shell@aunetx/components/components",
    root/"usr/share/gnome-shell/extensions/blur-my-shell@aunetx/preferences/preferences",
    root/"usr/share/gnome-shell/extensions/dash-to-dock@micxgx.gmail.com/dependencies/dependencies",
    root/"usr/share/gnome-shell/extensions/dash-to-dock@micxgx.gmail.com/media/media",
) if path.exists()]
if bad:raise SystemExit("Extension files were installed one directory too deep: "+", ".join(bad))
service=(root/"usr/lib/systemd/system/gnome-customizer-system-helper.service").read_text()
if "/usr/local/share/gnome-customizer" not in service:raise SystemExit("Helper sandbox is missing its managed resource path")
read_write=next((line for line in service.splitlines() if line.startswith("ReadWritePaths=")), "")
for path in ("/var/lib/dpkg/alternatives", "/var/lib/alternatives", "/etc/alternatives", "/var/log/alternatives.log"):
    if f"-{path}" not in read_write:
        raise SystemExit(f"Helper sandbox must tolerate a missing alternatives path: {path}")
policy=(root/"usr/share/polkit-1/actions/io.github.gnomecustomizer.policy").read_text()
if "<allow_any>auth_admin</allow_any>" not in policy:raise SystemExit("Remote/sessionless launches cannot request administrator authentication")
helper=(root/"usr/libexec/gnome-customizer-system-helper").read_text()
if "/usr/bin/gresource" in helper:raise SystemExit("The helper must use Gio.Resource instead of requiring /usr/bin/gresource")
