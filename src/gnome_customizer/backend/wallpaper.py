from __future__ import annotations


def wallpaper_keys(*, dark_override: bool, supports_dark: bool) -> tuple[str, ...]:
    """Return the GSettings keys affected by a wallpaper selection.

    A normal wallpaper selection must be visible regardless of the session's
    light/dark preference.  The separate dark selector is an explicit override.
    """

    if dark_override:
        return ("picture-uri-dark",) if supports_dark else ()
    if supports_dark:
        return ("picture-uri", "picture-uri-dark")
    return ("picture-uri",)
