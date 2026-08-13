from pathlib import Path

APP_ID = "io.github.gnomecustomizer"
HELPER_BUS = "io.github.gnomecustomizer.SystemHelper"
HELPER_PATH = "/io/github/gnomecustomizer/SystemHelper"
HELPER_IFACE = HELPER_BUS
MIN_GNOME = (50, 1)
DATA_DIR = Path("/usr/share/gnome-customizer")
USER_DATA = Path.home() / ".local/share/gnome-customizer"
USER_CONFIG = Path.home() / ".config/gnome-customizer"
STATE_FILE = USER_CONFIG / "state.json"
THEMES_DIR = USER_DATA / "themes"
ASSETS_DIR = USER_DATA / "assets"
LOGIN_THEME_ASSETS_DIR = USER_DATA / "login-theme-assets"

DESKTOP_KEYS = {
    "color_scheme": ("org.gnome.desktop.interface", "color-scheme"),
    "accent": ("org.gnome.desktop.interface", "accent-color"),
    "icon_theme": ("org.gnome.desktop.interface", "icon-theme"),
    "cursor_theme": ("org.gnome.desktop.interface", "cursor-theme"),
    "cursor_size": ("org.gnome.desktop.interface", "cursor-size"),
    "font_name": ("org.gnome.desktop.interface", "font-name"),
    "text_scale": ("org.gnome.desktop.interface", "text-scaling-factor"),
    "wallpaper": ("org.gnome.desktop.background", "picture-uri"),
    "wallpaper_dark": ("org.gnome.desktop.background", "picture-uri-dark"),
    "clock_date": ("org.gnome.desktop.interface", "clock-show-date"),
    "clock_weekday": ("org.gnome.desktop.interface", "clock-show-weekday"),
    "clock_seconds": ("org.gnome.desktop.interface", "clock-show-seconds"),
    "clock_format": ("org.gnome.desktop.interface", "clock-format"),
}
