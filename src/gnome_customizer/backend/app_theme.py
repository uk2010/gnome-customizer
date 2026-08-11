from __future__ import annotations

import os
import re
import stat
import tempfile
from copy import deepcopy
from pathlib import Path

from .state import StateStore
from .themes import validate_application_palette


BEGIN = b"/* GNOME Customizer application theme: begin */"
END = b"/* GNOME Customizer application theme: end */"
BLOCK = re.compile(re.escape(BEGIN) + rb".*?" + re.escape(END) + rb"\n?", re.DOTALL)

DEFAULT_APPLICATION_PALETTE = {
    "window_color": "#18181C",
    "view_color": "#111114",
    "sidebar_color": "#202027",
    "headerbar_color": "#24242C",
    "card_color": "#292932",
    "popover_color": "#2D2D37",
    "dialog_color": "#24242C",
    "text_color": "#F4F4F6",
    "muted_text_color": "#B6B6C2",
    "accent_color": "#3066D6",
    "accent_text_color": "#FFFFFF",
    "border_color": "#444451",
    "corner_radius": 12,
    "shadow_strength": 0.35,
}

APPLICATION_PRESETS={
    "Light":{"window_color":"#F7F7FA","view_color":"#FFFFFF","sidebar_color":"#E9E9F0","headerbar_color":"#DDDDE7","card_color":"#FFFFFF","popover_color":"#FFFFFF","dialog_color":"#F7F7FA","text_color":"#18181C","muted_text_color":"#5E5E6B","accent_color":"#3066D6","accent_text_color":"#FFFFFF","border_color":"#B8B8C5","corner_radius":12,"shadow_strength":.25},
    "Dark":{"window_color":"#18181C","view_color":"#101014","sidebar_color":"#24242D","headerbar_color":"#2C2C38","card_color":"#30303C","popover_color":"#292934","dialog_color":"#24242C","text_color":"#F4F4F6","muted_text_color":"#B6B6C2","accent_color":"#3066D6","accent_text_color":"#FFFFFF","border_color":"#555568","corner_radius":12,"shadow_strength":.4},
    "High Contrast":{"window_color":"#000000","view_color":"#000000","sidebar_color":"#111111","headerbar_color":"#111111","card_color":"#181818","popover_color":"#000000","dialog_color":"#000000","text_color":"#FFFFFF","muted_text_color":"#D8D8D8","accent_color":"#FFD400","accent_text_color":"#000000","border_color":"#FFFFFF","corner_radius":4,"shadow_strength":.7},
}


def application_css(palette: dict) -> str:
    palette = validate_application_palette(deepcopy(palette), require_complete=True)
    p = {**DEFAULT_APPLICATION_PALETTE, **palette}
    shadow_alpha = round(p["shadow_strength"], 3)
    radius = p["corner_radius"]
    scope="window:not(.gnome-customizer-window):not(.desktopwindow)"
    return f"""{scope} {{ background-color: {p['window_color']}; color: {p['text_color']}; }}
{scope} headerbar, {scope} .titlebar {{ background-color: {p['headerbar_color']}; color: {p['text_color']}; border-color: {p['border_color']}; }}
{scope} .sidebar, {scope} .navigation-sidebar, {scope} .sidebar-pane {{ background-color: {p['sidebar_color']}; color: {p['text_color']}; }}
{scope} .view, {scope} treeview.view, {scope} listview, {scope} gridview, {scope} columnview {{ background-color: {p['view_color']}; color: {p['text_color']}; }}
{scope} .card {{ background-color: {p['card_color']}; color: {p['text_color']}; border-color: {p['border_color']}; border-radius: {radius}px; }}
{scope} popover > contents, {scope} .popover > contents {{ background-color: {p['popover_color']}; color: {p['text_color']}; border: 1px solid {p['border_color']}; border-radius: {radius}px; box-shadow: 0 6px 20px alpha(#000000, {shadow_alpha}); }}
{scope} dialog, {scope} messagedialog {{ background-color: {p['dialog_color']}; color: {p['text_color']}; }}
{scope} button, {scope} entry, {scope} spinbutton, {scope} dropdown {{ border-radius: {radius}px; }}
{scope} row:selected, {scope} .view:selected, {scope} treeview.view:selected {{ background-color: {p['accent_color']}; color: {p['accent_text_color']}; }}
{scope} .dim-label, {scope} .caption, {scope} .subtitle {{ color: {p['muted_text_color']}; }}
{scope}.nautilus-window .sidebar, {scope}.nautilus-window .navigation-sidebar {{ background-color: {p['sidebar_color']}; }}
{scope}.nautilus-window .view, {scope}.nautilus-window gridview, {scope}.nautilus-window listview {{ background-color: {p['view_color']}; color: {p['text_color']}; }}
"""


def managed_bytes(existing: bytes, css: str) -> bytes:
    if (BEGIN in existing) != (END in existing):
        raise ValueError("Existing GTK CSS contains an incomplete GNOME Customizer block")
    clean = BLOCK.sub(b"", existing)
    return clean + BEGIN + b"\n" + css.encode("utf-8") + END + b"\n"


def unmanaged_bytes(existing: bytes) -> bytes:
    if (BEGIN in existing) != (END in existing):
        raise ValueError("Existing GTK CSS contains an incomplete GNOME Customizer block")
    return BLOCK.sub(b"", existing) if BLOCK.search(existing) else existing


class ApplicationThemeManager:
    def __init__(self, state: StateStore, home: Path | None = None):
        self.state = state
        root = home or Path.home()
        self.targets = (root / ".config/gtk-3.0/gtk.css", root / ".config/gtk-4.0/gtk.css")

    def snapshot(self) -> dict[Path, tuple[bool, bytes, int]]:
        result = {}
        for path in self.targets:
            if path.is_symlink():
                raise ValueError(f"Refusing symbolic-link GTK CSS: {path}")
            exists = path.is_file()
            result[path] = (exists, path.read_bytes() if exists else b"", stat.S_IMODE(path.stat().st_mode) if exists else 0o600)
        return result

    @staticmethod
    def _atomic(path: Path, content: bytes, mode: int = 0o600):
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor, temporary = tempfile.mkstemp(prefix=".gtk-css-", dir=path.parent)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content);stream.flush();os.fsync(stream.fileno())
            os.chmod(temporary, mode);os.replace(temporary, path)
        finally:
            try:os.unlink(temporary)
            except FileNotFoundError:pass

    def apply(self, palette: dict) -> dict[Path, tuple[bool, bytes, int]]:
        css = application_css(palette)
        before = self.snapshot()
        state_before = deepcopy(self.state.data)
        try:
            for path, (exists, content, mode) in before.items():
                self._atomic(path, managed_bytes(content, css), mode if exists else 0o600)
            previous = self.state.data.get("application_theme", {})
            created = set(previous.get("created", [])) if isinstance(previous, dict) else set()
            created.update(str(path) for path, (exists, _, _) in before.items() if not exists)
            self.state.data["application_theme"] = {"created": sorted(created), "palette": deepcopy(palette)}
            self.state.save()
        except Exception:
            self.restore_snapshot(before);self.state.data=state_before
            try:self.state.save()
            except Exception:pass
            raise
        return before

    def restore_snapshot(self, snapshot: dict[Path, tuple[bool, bytes, int]]):
        for path, (existed, content, mode) in snapshot.items():
            if existed:self._atomic(path, content, mode)
            else:path.unlink(missing_ok=True)

    def restore(self) -> int:
        metadata = self.state.data.get("application_theme", {})
        created = set(metadata.get("created", [])) if isinstance(metadata, dict) else set()
        changed = 0
        for path in self.targets:
            if path.is_symlink():raise ValueError(f"Refusing symbolic-link GTK CSS: {path}")
            if not path.is_file():continue
            original = path.read_bytes();clean = unmanaged_bytes(original)
            if clean == original:continue
            if not clean.strip() and str(path) in created:path.unlink()
            else:self._atomic(path, clean, stat.S_IMODE(path.stat().st_mode))
            changed += 1
        self.state.data.pop("application_theme", None);self.state.save()
        return changed

    def current_palette(self) -> dict:
        metadata = self.state.data.get("application_theme", {})
        palette = metadata.get("palette", {}) if isinstance(metadata, dict) else {}
        return {**DEFAULT_APPLICATION_PALETTE, **palette}


def migrate_managed_application_css() -> int:
    """Retire managed application CSS so GNOME Settings remains authoritative."""
    return ApplicationThemeManager(StateStore()).restore()
