from __future__ import annotations

import base64
import os
import tempfile
from pathlib import Path

from .assets import EXTENSIONS
from .constants import LOGIN_THEME_ASSETS_DIR


def _remove_asset(snapshot: dict, role: str, directory: Path) -> None:
    value = snapshot.setdefault("assets", {}).pop(role, None)
    if isinstance(value, str):
        try:
            path = Path(value)
            if path.parent.resolve() == directory.resolve() and path.is_file() and not path.is_symlink():
                path.unlink()
        except OSError:
            pass


def _store_asset(role: str, asset: dict, directory: Path) -> Path:
    mime = asset.get("mime")
    suffix = EXTENSIONS.get(mime)
    if role not in {"wallpaper", "logo"} or suffix is None:
        raise ValueError("Unsupported login theme image")
    try:
        payload = base64.b64decode(asset["data"], validate=True)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid login theme image") from exc
    if not payload or len(payload) > 20 * 1024 * 1024:
        raise ValueError("Login theme image exceeds the size limit")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    target = directory / f"{role}{suffix}"
    descriptor, temporary = tempfile.mkstemp(prefix=f".{role}-", dir=directory)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload);stream.flush();os.fsync(stream.fileno())
        os.chmod(temporary, 0o600);os.replace(temporary, target)
    finally:
        try:os.unlink(temporary)
        except FileNotFoundError:pass
    for old in directory.glob(f"{role}.*"):
        if old != target and old.is_file() and not old.is_symlink():old.unlink()
    return target


def remember_applied_login_theme(state, transaction: dict, directory: Path = LOGIN_THEME_ASSETS_DIR) -> None:
    """Merge successfully applied GDM appearance deltas into portable user state."""
    if not any(key in transaction for key in ("resource", "assets", "settings")):return
    raw = state.data.get("login_theme")
    snapshot = raw if isinstance(raw, dict) else {}
    snapshot.setdefault("resource", {});snapshot.setdefault("assets", {})
    resource = transaction.get("resource", {})
    if isinstance(resource, dict):snapshot["resource"].update(resource)
    settings = transaction.get("settings", {})
    interface = settings.get("org.gnome.desktop.interface", {}) if isinstance(settings, dict) else {}
    accent = interface.get("accent-color") if isinstance(interface, dict) else None
    if isinstance(accent, str):snapshot["accent"] = accent
    login = settings.get("org.gnome.login-screen", {}) if isinstance(settings, dict) else {}
    if isinstance(login, dict) and login.get("logo") == "":_remove_asset(snapshot, "logo", directory)
    if resource.get("wallpaper") is False:_remove_asset(snapshot, "wallpaper", directory)
    assets = transaction.get("assets", {})
    if isinstance(assets, dict):
        for role in ("wallpaper", "logo"):
            if role in assets:
                target = _store_asset(role, assets[role], directory)
                old = snapshot["assets"].get(role)
                snapshot["assets"][role] = str(target)
                if isinstance(old, str) and old != str(target):
                    try:
                        old_path=Path(old)
                        if old_path.parent.resolve()==directory.resolve() and old_path.is_file() and not old_path.is_symlink():old_path.unlink()
                    except OSError:pass
    state.data["login_theme"] = snapshot
    state.save()


def clear_login_theme_snapshot(state, directory: Path = LOGIN_THEME_ASSETS_DIR) -> None:
    state.data.pop("login_theme", None);state.save()
    if directory.is_dir() and not directory.is_symlink():
        for path in directory.iterdir():
            if path.is_file() and not path.is_symlink() and path.name.startswith(("wallpaper.", "logo.")):path.unlink()
