# F:\GPT\movie-lottery V2\movie_lottery\utils\qbittorrent.py
import requests
from flask import current_app
from qbittorrentapi import Client, exceptions as qbittorrent_exceptions


def is_downloading(torrent):
    """Возвращает True, если торрент находится в активной загрузке."""
    completed_states = {
        "completed",
        "pausedUP",
        "stalledUP",
        "queuedUP",
        "uploading",
        "seeding",
        "forcedUP",
        "checkingUP",
    }

    try:
        progress = float(getattr(torrent, "progress", 0))
    except (TypeError, ValueError):
        progress = 0

    state = getattr(torrent, "state", "")
    return progress < 1 and state not in completed_states


def _extract_progress(torrent) -> float:
    """Безопасно извлекает прогресс торрента в процентах."""
    try:
        progress_value = float(getattr(torrent, "progress", 0) or 0)
    except (TypeError, ValueError):
        progress_value = 0
    return round(progress_value * 100, 2)


def get_active_torrents_map():
    """
    Подключается к qBittorrent, получает все торренты и возвращает структуру с
    активными загрузками и полной картой торрентов с тегами `kp-*`.

    Возвращаемый словарь имеет вид::

        {
            "active": {kp_id: {"hash": str, "state": str, "progress": float, "is_active": bool}},
            "kp": {kp_id: {"hash": str, "state": str, "progress": float, "is_active": bool}},
        }
    """
    config = current_app.config
    qbt_client = None
    active_torrents = {}
    kp_torrents = {}

    try:
        qbt_client = Client(
            host=config['QBIT_HOST'],
            port=config['QBIT_PORT'],
            username=config['QBIT_USERNAME'],
            password=config['QBIT_PASSWORD']
        )
        qbt_client.auth_log_in()
        
        torrents = qbt_client.torrents_info()
        for torrent in torrents:
            tags_raw = getattr(torrent, "tags", "") or ""
            tags = tags_raw.split(',') if tags_raw else []
            torrent_state = getattr(torrent, "state", "unknown") or "unknown"
            torrent_hash = getattr(torrent, "hash", "") or ""
            torrent_progress = _extract_progress(torrent)
            torrent_is_active = is_downloading(torrent)

            for tag in tags:
                tag = tag.strip()
                if tag.startswith('kp-'):
                    try:
                        kp_id = int(tag.replace('kp-', ''))
                    except (ValueError, TypeError):
                        continue

                    torrent_payload = {
                        "hash": torrent_hash,
                        "state": torrent_state,
                        "progress": torrent_progress,
                        "is_active": torrent_is_active,
                    }

                    kp_torrents[kp_id] = torrent_payload

                    if torrent_is_active:
                        active_torrents[kp_id] = torrent_payload

                    break

    except (qbittorrent_exceptions.APIConnectionError, requests.exceptions.RequestException) as e:
        print(f"Ошибка подключения к qBittorrent: {e}")
        return {"active": {}, "kp": {}}
    except Exception as e:
        print(f"Неизвестная ошибка при работе с qBittorrent: {e}")
        return {"active": {}, "kp": {}}
    finally:
        if qbt_client and qbt_client.is_logged_in:
            try:
                qbt_client.auth_log_out()
            except Exception:
                pass

    return {"active": active_torrents, "kp": kp_torrents}
