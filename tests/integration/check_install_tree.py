#!/usr/bin/python3
from pathlib import Path
import sys
root=Path(sys.argv[1])
required=["usr/bin/gnome-customizer","usr/share/applications/io.github.gnomecustomizer.desktop","usr/share/metainfo/io.github.gnomecustomizer.metainfo.xml","usr/libexec/gnome-customizer-system-helper","usr/lib/python3/dist-packages/gnome_customizer/color.py","usr/lib/python3/dist-packages/gnome_customizer/backend/app_theme.py","usr/lib/python3/dist-packages/gnome_customizer/backend/assets.py","usr/lib/python3/dist-packages/gnome_customizer/backend/wallpaper.py","usr/share/polkit-1/actions/io.github.gnomecustomizer.policy","usr/share/gnome-shell/extensions/gnome-customizer@io.github.gnomecustomizer/extension.js"]
missing=[x for x in required if not (root/x).exists()]
if missing:raise SystemExit("Missing install files: "+", ".join(missing))
service=(root/"usr/lib/systemd/system/gnome-customizer-system-helper.service").read_text()
if "/usr/local/share/gnome-customizer" not in service:raise SystemExit("Helper sandbox is missing its managed resource path")
policy=(root/"usr/share/polkit-1/actions/io.github.gnomecustomizer.policy").read_text()
if "<allow_any>auth_admin</allow_any>" not in policy:raise SystemExit("Remote/sessionless launches cannot request administrator authentication")
