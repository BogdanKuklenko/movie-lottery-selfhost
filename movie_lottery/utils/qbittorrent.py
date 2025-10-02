# F:\GPT\movie-lottery V2\movie_lottery\utils\qbittorrent.py
import logging
import requests
from flask import current_app
from qbittorrentapi import Client, exceptions as qbittorrent_exceptions

from .qbittorrent_circuit_breaker import get_circuit_breaker

logger = logging.getLogger(__name__)

# Быстрый timeout для подключения к qBittorrent (не блокируем сайт)
QBIT_CONNECT_TIMEOUT = 3  # секунды
QBIT_READ_TIMEOUT = 5      # секунды


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
            "qbittorrent_available": bool,
        }
    
    Использует Circuit Breaker для предотвращения зависания при недоступности qBittorrent.
    """
    import os
    config = current_app.config
    circuit_breaker = get_circuit_breaker()
    
    # КРИТИЧНО: Проверяем что настройки qBittorrent заданы И не пустые
    qbit_host = config.get('QBIT_HOST')
    qbit_port = config.get('QBIT_PORT')
    qbit_username = config.get('QBIT_USERNAME')
    qbit_password = config.get('QBIT_PASSWORD')
    
    if not all([qbit_host, qbit_port, qbit_username, qbit_password]):
        # qBittorrent не настроен - возвращаем пустой результат БЕЗ попыток подключения
        logger.debug("qBittorrent не настроен (credentials отсутствуют или пусты)")
        return {
            "active": {}, 
            "kp": {}, 
            "qbittorrent_available": False
        }
    
    # Дополнительная проверка: если значения пустые строки
    if not qbit_host.strip() or not str(qbit_port).strip():
        logger.debug("qBittorrent host/port пустые")
        return {
            "active": {}, 
            "kp": {}, 
            "qbittorrent_available": False
        }
    
    # Проверяем доступность qBittorrent через Circuit Breaker
    if not circuit_breaker.is_available():
        logger.debug("qBittorrent недоступен (Circuit Breaker OPEN)")
        return {
            "active": {}, 
            "kp": {}, 
            "qbittorrent_available": False
        }
    
    qbt_client = None
    active_torrents = {}
    kp_torrents = {}

    try:
        # Создаём клиент с быстрыми таймаутами
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
        
        # Успех - записываем в Circuit Breaker
        circuit_breaker.record_success()
        logger.debug(f"qBittorrent: получено {len(kp_torrents)} торрентов")
        
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
        logger.warning(f"qBittorrent недоступен: {e}")
        circuit_breaker.record_failure()
        return {
            "active": {}, 
            "kp": {}, 
            "qbittorrent_available": False
        }
    except Exception as e:
        logger.error(f"Неожиданная ошибка при работе с qBittorrent: {e}")
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
