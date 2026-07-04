"""Cross-platform user configuration (platformdirs + TOML)."""

from __future__ import annotations

import json
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_config_dir

APP_NAME = "flipper-nfc"
CONFIG_KEYS = frozenset({"port"})


@dataclass(frozen=True)
class Settings:
    port: str | None = None


def config_path() -> Path:
    return Path(user_config_dir(APP_NAME)) / "config.toml"


def load_file() -> dict:
    path = config_path()
    if not path.is_file():
        return {}
    with path.open("rb") as handle:
        return tomllib.load(handle)


def save_file(data: dict) -> None:
    path = config_path()
    conn = data.get("connection") or {}
    lines: list[str] = []
    if conn:
        lines.append("[connection]")
        for key in ("port",):
            value = conn.get(key)
            if value:
                lines.append(f"{key} = {json.dumps(value)}")
    if lines:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    elif path.is_file():
        path.unlink()


def resolve_connection(cli_port: str | None) -> Settings:
    """Merge CLI flags, environment variables, and config file."""
    file_cfg = load_file().get("connection", {})
    port = cli_port or os.environ.get("FLIPPER_NFC_PORT") or file_cfg.get("port")
    return Settings(port=port)


def set_value(key: str, value: str) -> None:
    if key not in CONFIG_KEYS:
        raise ValueError(f"Unknown config key: {key!r}")
    data = load_file()
    conn = dict(data.get("connection", {}))
    conn[key] = value
    data["connection"] = conn
    save_file(data)


def unset_value(key: str) -> None:
    if key not in CONFIG_KEYS:
        raise ValueError(f"Unknown config key: {key!r}")
    data = load_file()
    conn = dict(data.get("connection", {}))
    conn.pop(key, None)
    if conn:
        data["connection"] = conn
    else:
        data.pop("connection", None)
    save_file(data)


def settings_as_dict(settings: Settings) -> dict[str, str | None]:
    return {"port": settings.port}
