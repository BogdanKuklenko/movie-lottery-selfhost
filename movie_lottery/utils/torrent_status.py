"""Utility helpers for working with qBittorrent torrent status objects."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterable, Optional

from flask import current_app
from qbittorrentapi import Client


def _format_speed(bytes_per_second: Optional[float]) -> str:
    if not bytes_per_second or bytes_per_second <= 0:
        return "0.00"
    megabytes_per_second = float(bytes_per_second) / (1024 ** 2)
    return f"{megabytes_per_second:.2f}"


def _format_eta(seconds: Optional[int]) -> str:
    if seconds is None or seconds < 0:
        return "--:--"

    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02}:{minutes:02}:{secs:02}"
    return f"{minutes:02}:{secs:02}"


def torrent_to_json(torrent) -> dict:
    """Convert a qBittorrent torrent object to a JSON-serialisable dictionary."""
    progress_value = getattr(torrent, "progress", 0) or 0
    status = getattr(torrent, "state", "unknown") or "unknown"

    return {
        "name": getattr(torrent, "name", ""),
        "status": status,
        "progress": round(float(progress_value) * 100, 2),
        "speed": _format_speed(getattr(torrent, "dlspeed", 0)),
        "eta": _format_eta(getattr(torrent, "eta", None)),
        "seeds": getattr(torrent, "num_seeds", 0),
        "peers": getattr(torrent, "num_leechs", 0),
        "hash": getattr(torrent, "hash", ""),
    }


@contextmanager
def qbittorrent_client() -> Iterable[Client]:
    """Context manager that yields an authenticated qBittorrent client."""
    config = current_app.config
    client = Client(
        host=config["QBIT_HOST"],
        port=config["QBIT_PORT"],
        username=config["QBIT_USERNAME"],
        password=config["QBIT_PASSWORD"],
    )
    try:
        client.auth_log_in()
        yield client
    finally:
        if client.is_logged_in:
            try:
                client.auth_log_out()
            except Exception:
                # Ошибки при выходе из клиента не критичны
                pass
