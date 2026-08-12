from __future__ import annotations

import io
import hashlib
import json
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any
from functools import lru_cache
from urllib.parse import unquote, urlparse
from PIL import Image

from .constants import MIN_GNOME, THEMES_DIR

MAX_FILES = 32
MAX_TOTAL = 50 * 1024 * 1024
MAX_IMAGE = 20 * 1024 * 1024
MAX_JSON = 256 * 1024
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
COLOR = re.compile(r"^#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?$")
SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")
ACCENTS = {"blue", "teal", "green", "yellow", "orange", "red", "pink", "purple", "slate", "brown"}
SURFACE_FIELDS = {"enabled", "background_type", "color", "color1", "color2", "gradient_angle", "opacity", "blur", "brightness", "saturation", "hover_color", "hover_opacity", "text_color", "muted_text_color", "selected_color", "border_color", "corner_radius", "shadow_strength", "icon_size", "spacing", "indicator_style"}
APPLICATION_FIELDS = {"window_color", "view_color", "sidebar_color", "headerbar_color", "card_color", "popover_color", "dialog_color", "text_color", "muted_text_color", "accent_color", "accent_text_color", "border_color", "corner_radius", "shadow_strength"}
DESKTOP_THEME_SETTINGS = {
    "color_scheme": ("org.gnome.desktop.interface", "color-scheme"),
    "accent": ("org.gnome.desktop.interface", "accent-color"),
    "icons": ("org.gnome.desktop.interface", "icon-theme"),
    "cursor": ("org.gnome.desktop.interface", "cursor-theme"),
    "gtk_theme": ("org.gnome.desktop.interface", "gtk-theme"),
    "cursor_size": ("org.gnome.desktop.interface", "cursor-size"),
    "text_scale": ("org.gnome.desktop.interface", "text-scaling-factor"),
    "font": ("org.gnome.desktop.interface", "font-name"),
    "font_antialiasing": ("org.gnome.desktop.interface", "font-antialiasing"),
    "font_hinting": ("org.gnome.desktop.interface", "font-hinting"),
    "wallpaper_options": ("org.gnome.desktop.background", "picture-options"),
    "wallpaper_shading": ("org.gnome.desktop.background", "color-shading-type"),
    "wallpaper_primary_color": ("org.gnome.desktop.background", "primary-color"),
    "wallpaper_secondary_color": ("org.gnome.desktop.background", "secondary-color"),
    "clock_format": ("org.gnome.desktop.interface", "clock-format"),
    "clock_show_date": ("org.gnome.desktop.interface", "clock-show-date"),
    "clock_show_weekday": ("org.gnome.desktop.interface", "clock-show-weekday"),
    "clock_show_seconds": ("org.gnome.desktop.interface", "clock-show-seconds"),
    "battery_percentage": ("org.gnome.desktop.interface", "show-battery-percentage"),
    "sound_theme": ("org.gnome.desktop.sound", "theme-name"),
}
DOCK_THEME_SETTINGS = {
    "position": "dock-position", "panel_mode": "extend-height",
    "icon_size": "dash-max-icon-size", "icon_size_fixed": "icon-size-fixed",
    "height_fraction": "height-fraction", "multi_monitor": "multi-monitor",
    "show_favorites": "show-favorites", "show_running": "show-running",
    "show_applications": "show-show-apps-button", "show_applications_first": "show-apps-at-top",
    "always_visible": "dock-fixed", "autohide": "autohide", "intellihide": "intellihide",
    "transparency": "transparency-mode", "opacity": "background-opacity",
    "custom_color": "custom-background-color", "color": "background-color",
    "indicator_style": "running-indicator-style", "built_in_theme": "apply-custom-theme",
    "straight_corners": "force-straight-corner",
}
SHELL_SURFACE_SETTINGS = {
    "panel": {"enabled": "panel-enabled", "color": "panel-color", "color2": "panel-color2", "opacity": "panel-opacity", "blur": "panel-blur", "text_color": "panel-text-color", "corner_radius": "panel-radius"},
    "menus": {"enabled": "menu-enabled", "color": "menu-color", "color2": "menu-color2", "opacity": "menu-opacity", "blur": "menu-blur", "text_color": "menu-text-color", "border_color": "menu-border-color", "corner_radius": "menu-radius"},
    "overview": {"enabled": "overview-enabled", "color": "overview-color", "opacity": "overview-opacity", "blur": "overview-blur", "brightness": "overview-brightness", "saturation": "overview-saturation", "hover_color": "overview-hover-color", "hover_opacity": "overview-hover-opacity"},
}
DOCK_FIELDS = set(DOCK_THEME_SETTINGS) | (SURFACE_FIELDS - {"indicator_style", "icon_size", "opacity", "color"})


class ThemeError(ValueError): pass


@lru_cache(maxsize=1)
def runtime_gnome_version() -> tuple[int,int]:
    try:
        text=subprocess.run(["gnome-shell","--version"],text=True,capture_output=True,check=False,timeout=3).stdout
        match=re.search(r"(\d+)\.(\d+)",text)
        if match:return int(match.group(1)),int(match.group(2))
    except (OSError,subprocess.TimeoutExpired):pass
    return MIN_GNOME


def _text(value: Any, name: str, maximum: int, required=False) -> str:
    if not isinstance(value, str) or (required and not value.strip()) or len(value) > maximum:
        raise ThemeError(f"{name} must be valid text up to {maximum} characters")
    if any(unicodedata.category(c) in {"Cc", "Cs"} and c not in "\n\t" for c in value):
        raise ThemeError(f"{name} contains invalid control characters")
    return value


def _known(obj: dict, allowed: set[str], where: str):
    unknown = set(obj) - allowed
    if unknown: raise ThemeError(f"Unsupported {where} properties: {', '.join(sorted(unknown))}")


def _asset(value: Any, where: str) -> str:
    value = _text(value, where, 150, True)
    path = PurePosixPath(value)
    if path.is_absolute() or len(path.parts) != 2 or path.parts[0] != "assets" or not SAFE_NAME.fullmatch(path.name) or path.suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS:
        raise ThemeError(f"Unsafe asset path for {where}")
    return value


def _number(value, name, low, high, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or (integer and not isinstance(value, int)) or not low <= value <= high:
        raise ThemeError(f"{name} must be between {low} and {high}")


def _contrast(first: str, second: str) -> float:
    def luminance(value):
        channels=[int(value[i:i+2],16)/255 for i in (1,3,5)]
        channels=[item/12.92 if item<=.04045 else ((item+.055)/1.055)**2.4 for item in channels]
        return .2126*channels[0]+.7152*channels[1]+.0722*channels[2]
    bright,dark=sorted((luminance(first),luminance(second)),reverse=True)
    return (bright+.05)/(dark+.05)


def _surface(obj: Any, where: str):
    if not isinstance(obj, dict): raise ThemeError(f"{where} must be an object")
    _known(obj, SURFACE_FIELDS, where)
    if "enabled" in obj and not isinstance(obj["enabled"], bool): raise ThemeError(f"{where}.enabled must be true or false")
    for field in ("color", "color1", "color2", "hover_color", "text_color", "muted_text_color", "selected_color", "border_color"):
        if field in obj and (not isinstance(obj[field], str) or not COLOR.fullmatch(obj[field])): raise ThemeError(f"Invalid color at {where}.{field}")
    bounds = {"gradient_angle": (0,360,True), "opacity": (0,1,False), "blur": (0,100,True), "brightness": (.2,1.5,False), "saturation": (0,2,False), "hover_opacity": (0,1,False), "corner_radius": (0,32,True), "shadow_strength": (0,1,False), "icon_size": (16,128,True), "spacing": (0,24,True)}
    for field, (low, high, integer) in bounds.items():
        if field in obj: _number(obj[field], f"{where}.{field}", low, high, integer)
    if "background_type" in obj and obj["background_type"] not in {"solid", "gradient"}: raise ThemeError(f"Invalid background type at {where}")
    if "indicator_style" in obj and obj["indicator_style"] not in {"none", "dot", "dash", "line"}: raise ThemeError(f"Invalid indicator style at {where}")


def _dock(obj: Any, where: str):
    if not isinstance(obj, dict): raise ThemeError(f"{where} must be an object")
    _known(obj, DOCK_FIELDS, where)
    legacy = {field: value for field, value in obj.items() if field in SURFACE_FIELDS}
    if legacy.get("indicator_style") in {"DEFAULT", "DOTS", "SQUARES", "DASHES", "SEGMENTED", "SOLID", "CILIORA", "METRO", "BINARY", "DOT"}: legacy.pop("indicator_style")
    _surface(legacy, where)
    booleans = {"panel_mode", "icon_size_fixed", "multi_monitor", "show_favorites", "show_running", "show_applications", "show_applications_first", "always_visible", "autohide", "intellihide", "custom_color", "built_in_theme", "straight_corners"}
    for field in booleans:
        if field in obj and not isinstance(obj[field], bool): raise ThemeError(f"{where}.{field} must be true or false")
    if "position" in obj and obj["position"] not in {"TOP", "RIGHT", "BOTTOM", "LEFT"}: raise ThemeError(f"Invalid dock position at {where}")
    if "transparency" in obj and obj["transparency"] not in {"DEFAULT", "FIXED", "DYNAMIC"}: raise ThemeError(f"Invalid dock transparency at {where}")
    if "indicator_style" in obj and obj["indicator_style"] not in {"DEFAULT", "DOTS", "SQUARES", "DASHES", "SEGMENTED", "SOLID", "CILIORA", "METRO", "BINARY", "DOT", "none", "dot", "dash", "line"}: raise ThemeError(f"Invalid dock indicator at {where}")
    if "color" in obj and (not isinstance(obj["color"], str) or not COLOR.fullmatch(obj["color"])): raise ThemeError(f"Invalid color at {where}.color")
    for field, bounds in {"icon_size": (16,128,True), "height_fraction": (.2,1,False), "opacity": (0,1,False)}.items():
        if field in obj: _number(obj[field], f"{where}.{field}", *bounds)


def validate_application_palette(value: Any, require_complete=False) -> dict:
    if not isinstance(value, dict):raise ThemeError("applications must be an object")
    _known(value, APPLICATION_FIELDS, "applications")
    if require_complete and set(value)!=APPLICATION_FIELDS:raise ThemeError("Application palette is incomplete")
    for field in APPLICATION_FIELDS - {"corner_radius","shadow_strength"}:
        if field in value and (not isinstance(value[field],str) or not COLOR.fullmatch(value[field])):raise ThemeError(f"Invalid color at applications.{field}")
    if "corner_radius" in value:_number(value["corner_radius"],"applications.corner_radius",0,32,True)
    if "shadow_strength" in value:_number(value["shadow_strength"],"applications.shadow_strength",0,1,False)
    if require_complete:
        surfaces=("window_color","view_color","sidebar_color","headerbar_color","card_color","popover_color","dialog_color")
        for field in surfaces:
            if _contrast(value["text_color"],value[field])<4.5:raise ThemeError(f"Application text contrast is unsafe on {field.replace('_color','').replace('_',' ')}")
        if _contrast(value["muted_text_color"],value["window_color"])<3:raise ThemeError("Muted application text contrast is unsafe")
        if _contrast(value["accent_text_color"],value["accent_color"])<4.5:raise ThemeError("Selected application text contrast is unsafe")
    return value


def validate_manifest(manifest: Any, assets: set[str] | None = None, gnome=None) -> dict:
    gnome=gnome or runtime_gnome_version()
    if not isinstance(manifest, dict): raise ThemeError("manifest.json must contain an object")
    _known(manifest, {"format_version", "id", "name", "author", "description", "minimum_gnome", "maximum_tested_gnome", "preview", "desktop", "applications", "shell", "login"}, "manifest")
    if manifest.get("format_version") != 1: raise ThemeError("Only theme format version 1 is supported")
    _text(manifest.get("name"), "name", 100, True); _text(manifest.get("author"), "author", 100, True)
    if "description" in manifest: _text(manifest["description"], "description", 1000)
    if "id" in manifest and (not isinstance(manifest["id"], str) or not SAFE_NAME.fullmatch(manifest["id"]) or len(manifest["id"]) > 100): raise ThemeError("Invalid theme ID")
    minimum = manifest.get("minimum_gnome", "50.1")
    try:
        if not isinstance(minimum,str) or not re.fullmatch(r"[0-9]+\.[0-9]+",minimum):raise ValueError
        required = tuple(int(x) for x in minimum.split("."))
    except Exception: raise ThemeError("minimum_gnome must look like 50.1")
    if required < MIN_GNOME: raise ThemeError("Themes must target GNOME 50.1 or newer")
    if required > gnome: raise ThemeError(f"This theme requires GNOME {minimum}")
    maximum = manifest.get("maximum_tested_gnome")
    if maximum:
        if not isinstance(maximum, str) or not re.fullmatch(r"[0-9]+\.(?:[0-9]+|x)", maximum): raise ThemeError("maximum_tested_gnome must look like 50.3 or 50.x")
    refs = []
    if "preview" in manifest: refs.append(_asset(manifest["preview"], "preview"))
    desktop = manifest.get("desktop", {})
    if not isinstance(desktop, dict): raise ThemeError("desktop must be an object")
    _known(desktop, set(DESKTOP_THEME_SETTINGS) | {"wallpaper", "wallpaper_dark"}, "desktop")
    if "color_scheme" in desktop and desktop["color_scheme"] not in {"default", "prefer-light", "prefer-dark"}: raise ThemeError("Invalid color scheme")
    if "accent" in desktop and desktop["accent"] not in ACCENTS: raise ThemeError("Invalid accent")
    for key in ("wallpaper", "wallpaper_dark"):
        if key in desktop: refs.append(_asset(desktop[key], f"desktop.{key}"))
    for key in ("icons", "cursor", "gtk_theme", "font", "sound_theme"):
        if key in desktop: _text(desktop[key], f"desktop.{key}", 100, True)
    if "cursor_size" in desktop: _number(desktop["cursor_size"], "desktop.cursor_size", 8, 128, True)
    if "text_scale" in desktop: _number(desktop["text_scale"], "desktop.text_scale", .5, 3)
    if "font_antialiasing" in desktop and desktop["font_antialiasing"] not in {"none", "grayscale", "rgba"}: raise ThemeError("Invalid font antialiasing")
    if "font_hinting" in desktop and desktop["font_hinting"] not in {"none", "slight", "medium", "full"}: raise ThemeError("Invalid font hinting")
    if "wallpaper_options" in desktop and desktop["wallpaper_options"] not in {"none", "wallpaper", "centered", "scaled", "stretched", "zoom", "spanned"}: raise ThemeError("Invalid wallpaper placement")
    if "wallpaper_shading" in desktop and desktop["wallpaper_shading"] not in {"solid", "vertical", "horizontal"}: raise ThemeError("Invalid wallpaper shading")
    for key in ("wallpaper_primary_color", "wallpaper_secondary_color"):
        if key in desktop and (not isinstance(desktop[key], str) or not COLOR.fullmatch(desktop[key])): raise ThemeError(f"Invalid color at desktop.{key}")
    if "clock_format" in desktop and desktop["clock_format"] not in {"12h", "24h"}: raise ThemeError("Invalid clock format")
    for key in ("clock_show_date", "clock_show_weekday", "clock_show_seconds", "battery_percentage"):
        if key in desktop and not isinstance(desktop[key], bool): raise ThemeError(f"desktop.{key} must be true or false")
    if "applications" in manifest:validate_application_palette(manifest["applications"])
    shell = manifest.get("shell", {})
    if not isinstance(shell, dict): raise ThemeError("shell must be an object")
    _known(shell, {"panel", "dock", "menus", "overview"}, "shell")
    for key, value in shell.items():
        (_dock if key == "dock" else _surface)(value, f"shell.{key}")
    login = manifest.get("login", {})
    if not isinstance(login, dict): raise ThemeError("login must be an object")
    _known(login, {"wallpaper", "background_color", "accent", "logo", "panel"}, "login")
    for key in ("wallpaper", "logo"):
        if key in login: refs.append(_asset(login[key], f"login.{key}"))
    if "background_color" in login and not COLOR.fullmatch(login["background_color"]): raise ThemeError("Invalid login background color")
    if "accent" in login and login["accent"] not in ACCENTS: raise ThemeError("Invalid login accent")
    if "panel" in login: _surface(login["panel"], "login.panel")
    if assets is not None:
        missing = set(refs) - assets
        if missing: raise ThemeError(f"Missing theme assets: {', '.join(sorted(missing))}")
    return manifest


def compatibility_warnings(manifest: dict, gnome=None) -> list[str]:
    gnome=gnome or runtime_gnome_version()
    maximum = manifest.get("maximum_tested_gnome")
    if not maximum:return []
    major,minor=maximum.split("."); tested=(int(major), 10**9 if minor=="x" else int(minor))
    if gnome>tested:return [f"This theme was tested through GNOME {maximum}; you are running GNOME {gnome[0]}.{gnome[1]}."]
    return []


def inspect_archive(path: Path) -> tuple[dict, zipfile.ZipFile]:
    try: archive = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc: raise ThemeError("The selected file is not a valid .gctheme archive") from exc
    infos = archive.infolist()
    if not infos or len(infos) > MAX_FILES: archive.close(); raise ThemeError("Theme archive contains too many files")
    names, files, total = set(), set(), 0
    for info in infos:
        p = PurePosixPath(info.filename)
        if info.filename in names or p.is_absolute() or ".." in p.parts or "\\" in info.filename: archive.close(); raise ThemeError("Theme archive contains an unsafe or duplicate path")
        names.add(info.filename); total += info.file_size
        if info.external_attr >> 16 & 0o170000 == 0o120000: archive.close(); raise ThemeError("Symbolic links are not allowed in themes")
        if not info.is_dir(): files.add(info.filename)
        if info.file_size > (MAX_JSON if info.filename == "manifest.json" else MAX_IMAGE): archive.close(); raise ThemeError("A theme file exceeds the size limit")
    if total > MAX_TOTAL or "manifest.json" not in files: archive.close(); raise ThemeError("Theme is oversized or has no manifest.json")
    allowed = {"manifest.json"} | {n for n in files if n.startswith("assets/") and PurePosixPath(n).suffix.lower() in ALLOWED_IMAGE_EXTENSIONS}
    if files - allowed: archive.close(); raise ThemeError("Themes may contain only manifest.json and supported images in assets/")
    for name in files - {"manifest.json"}:
        try:
            with Image.open(io.BytesIO(archive.read(name))) as image:
                image.verify()
                if image.width > 16384 or image.height > 16384 or image.width * image.height > 80_000_000: raise ThemeError(f"Image dimensions are unsafe: {name}")
                expected={".png":"PNG",".jpg":"JPEG",".jpeg":"JPEG",".webp":"WEBP"}[PurePosixPath(name).suffix.lower()]
                if image.format != expected: raise ThemeError(f"Image type does not match its name: {name}")
        except ThemeError: archive.close(); raise
        except Exception as exc: archive.close(); raise ThemeError(f"Invalid image asset: {name}") from exc
    try: manifest = json.loads(archive.read("manifest.json").decode("utf-8", "strict"))
    except (UnicodeError, json.JSONDecodeError) as exc: archive.close(); raise ThemeError("manifest.json is invalid UTF-8 JSON") from exc
    return validate_manifest(manifest, files), archive


def import_theme(path: Path, destination: Path = THEMES_DIR) -> Path:
    manifest, archive = inspect_archive(path)
    slug = manifest.get("id") or re.sub(r"[^A-Za-z0-9._-]+", "-", manifest["name"]).strip("-").lower()
    if not slug: slug="theme-"+hashlib.sha256(json.dumps(manifest,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:16]
    target = destination / slug
    destination.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=".import-", dir=destination))
    try:
        for info in archive.infolist():
            if info.is_dir(): continue
            out = temp.joinpath(*PurePosixPath(info.filename).parts)
            out.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as src, out.open("xb") as dst: shutil.copyfileobj(src, dst)
            os.chmod(out, 0o600)
        if target.exists(): shutil.rmtree(target)
        os.replace(temp, target)
        return target
    finally:
        archive.close()
        if temp.exists(): shutil.rmtree(temp)


def delete_theme(directory: Path, destination: Path = THEMES_DIR) -> None:
    """Delete exactly one imported theme directory and nothing outside the theme store."""
    root = destination.resolve()
    if directory.is_symlink(): raise ThemeError("Symbolic-link themes cannot be deleted")
    try: target = directory.resolve(strict=True)
    except OSError as exc: raise ThemeError("Theme is already missing") from exc
    if target.parent != root or not target.is_dir() or not (target / "manifest.json").is_file():
        raise ThemeError("Only an imported local theme can be deleted")
    shutil.rmtree(target)


def export_theme(manifest: dict, assets: dict[str, Path], target: Path) -> Path:
    validate_manifest(manifest, set(assets))
    target = target.with_suffix(".gctheme")
    fd, tmp = tempfile.mkstemp(prefix=".theme-", dir=target.parent); os.close(fd)
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
            for name, source in assets.items(): archive.write(source, name)
        os.replace(tmp, target); return target
    finally:
        try: os.unlink(tmp)
        except FileNotFoundError: pass


def capture_current_theme(settings, name: str, author: str) -> tuple[dict, dict[str, Path]]:
    """Capture the currently applied appearance settings as a portable theme."""
    get, supports = settings.get, settings.supports
    manifest = {
        "format_version": 1, "name": name, "author": author,
        "description": "Saved from the currently applied GNOME Customizer settings.",
        "minimum_gnome": "50.1", "maximum_tested_gnome": "50.x", "desktop": {},
    }
    desktop = manifest["desktop"]
    for field, (schema, key) in DESKTOP_THEME_SETTINGS.items():
        if supports(schema, key): desktop[field] = get(schema, key)

    assets: dict[str, Path] = {}
    background = "org.gnome.desktop.background"
    for field, key, asset_name in (("wallpaper", "picture-uri", "wallpaper"), ("wallpaper_dark", "picture-uri-dark", "wallpaper-dark")):
        if not supports(background, key): continue
        parsed = urlparse(get(background, key))
        source = Path(unquote(parsed.path)) if parsed.scheme == "file" and not parsed.netloc else None
        if source and source.is_file() and source.suffix.lower() in ALLOWED_IMAGE_EXTENSIONS:
            archive_name = f"assets/{asset_name}{source.suffix.lower()}"
            desktop[field], assets[archive_name] = archive_name, source

    shell_schema = "io.github.gnomecustomizer.shell"
    shell: dict[str, dict] = {}
    for section, fields in SHELL_SURFACE_SETTINGS.items():
        prefix = "menu" if section == "menus" else section
        enabled_key = fields["enabled"]
        if not supports(shell_schema, enabled_key): continue
        surface = {field: get(shell_schema, key) for field, key in fields.items() if supports(shell_schema, key)}
        if section in {"panel", "menus"} and supports(shell_schema, f"{prefix}-gradient-enabled"):
            gradient = get(shell_schema, f"{prefix}-gradient-enabled")
            surface["background_type"] = "gradient" if gradient else "solid"
            if supports(shell_schema, f"{prefix}-gradient-direction"):
                surface["gradient_angle"] = 90 if get(shell_schema, f"{prefix}-gradient-direction") == "vertical" else 0
        shell[section] = surface

    dock_schema = "org.gnome.shell.extensions.dash-to-dock"
    if settings.schema(dock_schema):
        dock = {field: get(dock_schema, key) for field, key in DOCK_THEME_SETTINGS.items() if supports(dock_schema, key)}
        if dock: shell["dock"] = dock
    if shell: manifest["shell"] = shell
    validate_manifest(manifest, set(assets))
    return manifest, assets
