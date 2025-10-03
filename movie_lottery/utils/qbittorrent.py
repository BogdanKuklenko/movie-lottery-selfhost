import logging
import requests
from flask import current_app
from qbittorrentapi import Client, exceptions as qbittorrent_exceptions

from .qbittorrent_circuit_breaker import get_circuit_breaker

logger = logging.getLogger(__name__)

# Fast timeout for qBittorrent connections (prevents site blocking)
QBIT_CONNECT_TIMEOUT = 3  # seconds
QBIT_READ_TIMEOUT = 5  # seconds


def is_downloading(torrent):
    """Return True if torrent is actively downloading."""
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
    """Safely extract torrent progress as percentage."""
    try:
        progress_value = float(getattr(torrent, "progress", 0) or 0)
    except (TypeError, ValueError):
        progress_value = 0
    return round(progress_value * 100, 2)


def get_active_torrents_map():
    """
    Connect to qBittorrent, get all torrents and return structure with active
    downloads and full map of torrents with `kp-*` tags.

    Returns dictionary:
        {
            "active": {kp_id: {"hash": str, "state": str, "progress": float, "is_active": bool}},
            "kp": {kp_id: {"hash": str, "state": str, "progress": float, "is_active": bool}},
            "qbittorrent_available": bool,
        }
    
    Uses Circuit Breaker to prevent hanging when qBittorrent is unavailable.
    """
    config = current_app.config
    circuit_breaker = get_circuit_breaker()
    
    # Check if qBittorrent settings are configured
    qbit_host = config.get('QBIT_HOST')
    qbit_port = config.get('QBIT_PORT')
    qbit_username = config.get('QBIT_USERNAME')
    qbit_password = config.get('QBIT_PASSWORD')
    
    if not all([qbit_host, qbit_port, qbit_username, qbit_password]):
        logger.debug("qBittorrent not configured (missing credentials)")
        return {
            "active": {}, 
            "kp": {}, 
            "qbittorrent_available": False
        }
    
    if not qbit_host.strip() or not str(qbit_port).strip():
        logger.debug("qBittorrent host/port empty")
        return {
            "active": {}, 
            "kp": {}, 
            "qbittorrent_available": False
        }
    
    if not circuit_breaker.is_available():
        logger.debug("qBittorrent unavailable (Circuit Breaker OPEN)")
        return {
            "active": {}, 
            "kp": {}, 
            "qbittorrent_available": False
        }
    
    qbt_client = None
    active_torrents = {}
    kp_torrents = {}

    try:
        # Create client with fast timeouts
        qbt_client = Client(
            host=config['QBIT_HOST'],
            port=config['QBIT_PORT'],
            username=config['QBIT_USERNAME'],
            password=config['QBIT_PASSWORD'],
            REQUESTS_ARGS={
                'timeout': (QBIT_CONNECT_TIMEOUT, QBIT_READ_TIMEOUT)
            }
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
        
        circuit_breaker.record_success()
        logger.debug(f"qBittorrent: retrieved {len(kp_torrents)} torrents")
        
        return {
            "active": active_torrents, 
            "kp": kp_torrents,
            "qbittorrent_available": True
        }

    except (
        qbittorrent_exceptions.APIConnectionError,
        requests.exceptions.RequestException,
        requests.exceptions.Timeout
    ) as e:
        logger.warning(f"qBittorrent unavailable: {e}")
        circuit_breaker.record_failure()
        return {
            "active": {}, 
            "kp": {}, 
            "qbittorrent_available": False
        }
    except Exception as e:
        logger.error(f"Unexpected error with qBittorrent: {e}")
        circuit_breaker.record_failure()
        return {
            "active": {}, 
            "kp": {}, 
            "qbittorrent_available": False
        }
    finally:
        if qbt_client and qbt_client.is_logged_in:
            try:
                qbt_client.auth_log_out()
            except Exception:
                pass
