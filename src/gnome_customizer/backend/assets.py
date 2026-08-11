from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from pathlib import Path


EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}


def copy_managed_image(source: Path, directory: Path, role: str, mime: str) -> Path:
    """Copy an image to an immutable content-addressed managed path.

    Never overwrite an already-active wallpaper path while a replacement is
    merely staged.  The GSettings URI is the commit point.
    """

    suffix = EXTENSIONS.get(mime)
    if suffix is None:
        raise ValueError("Unsupported managed image type")
    with source.open("rb") as incoming:
        digest = hashlib.file_digest(incoming, "sha256").hexdigest()
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{role}-{digest[:20]}{suffix}"
    if destination.exists():
        if not destination.is_file() or destination.is_symlink():
            raise ValueError("Managed image destination is unsafe")
        return destination
    descriptor, temporary = tempfile.mkstemp(prefix=".image-", dir=directory)
    try:
        with os.fdopen(descriptor, "wb") as output, source.open("rb") as incoming:
            shutil.copyfileobj(incoming, output)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, destination)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
    return destination


def remove_managed_images(directory: Path) -> int:
    """Remove only wallpaper copies created by GNOME Customizer."""
    if not directory.is_dir() or directory.is_symlink():return 0
    removed=0
    for path in directory.iterdir():
        if path.is_file() and not path.is_symlink() and path.name.startswith(("desktop-wallpaper-","desktop-wallpaper-dark-")):
            path.unlink();removed+=1
    return removed
