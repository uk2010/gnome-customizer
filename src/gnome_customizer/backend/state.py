from __future__ import annotations

import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from .constants import STATE_FILE


class StateStore:
    """Durable user state written atomically with private permissions."""

    def __init__(self, path: Path = STATE_FILE):
        self.path = path
        self.data: dict[str, Any] = {"version": 1, "original": {}, "managed": {}, "last_apply": None}
        self.load()

    def load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and raw.get("version") == 1:
                self.data.update(raw)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.path.parent,0o700)
        fd, tmp_name = tempfile.mkstemp(prefix=".state-", dir=self.path.parent, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(self.data, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(tmp_name, 0o600)
            os.replace(tmp_name, self.path)
        finally:
            try: os.unlink(tmp_name)
            except FileNotFoundError: pass

    def remember_original(self, domain: str, key: str, value: Any) -> None:
        bucket = self.data.setdefault("original", {}).setdefault(domain, {})
        if key not in bucket:
            bucket[key] = deepcopy(value)

    def original(self, domain: str) -> dict[str, Any]:
        return deepcopy(self.data.get("original", {}).get(domain, {}))

    def clear_original(self, domain: str) -> None:
        self.data.get("original", {}).pop(domain, None)
        self.data.get("managed", {}).pop(domain, None)
        self.save()
