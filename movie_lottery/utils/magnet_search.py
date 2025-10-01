"""Utilities for performing background magnet link searches."""
from __future__ import annotations

import logging
import string
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Lock
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urlencode

import requests
from flask import current_app, has_app_context

from .. import db
from ..models import MovieIdentifier

# Список API для поиска торрентов (с поддержкой русского языка)
TORRENT_APIS = [
    {
        "name": "Torrent Project",
        "url": "https://torrent-project.cc/api",
        "params": lambda query: {"query": query, "lang": "ru"},
        "supports_russian": True
    },
    {
        "name": "1337x API",
        "url": "https://1337x.to/search/{query}/1/",
        "supports_russian": True
    },
    {
        "name": "YTS",
        "url": "https://yts.mx/api/v2/list_movies.json",
        "params": lambda query: {"query_term": query, "limit": 20, "sort_by": "seeds"},
        "supports_russian": False
    }
]

DEFAULT_SEARCH_URL = "https://apibay.org/q.php?q={query}"
DEFAULT_TRACKERS = (
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://open.demonii.com:1337/announce",
    "udp://tracker.openbittorrent.com:6969/announce",
    "udp://exodus.desync.com:6969/announce",
    "udp://tracker.torrent.eu.org:451/announce",
    "udp://tracker.moeking.me:6969/announce",
    "udp://opentracker.i2p.rocks:6969/announce",
    "udp://open.stealth.si:80/announce",
)

_logger = logging.getLogger(__name__)

_search_executor = ThreadPoolExecutor(max_workers=3)
_tasks: Dict[int, Dict[str, Any]] = {}
_tasks_lock = Lock()


def _get_configured_value(key: str, default: Any) -> Any:
    if has_app_context():
        return current_app.config.get(key, default)
    return default


def _build_magnet(info_hash: str, name: str, trackers: Optional[Any] = None) -> str:
    trackers = trackers or _get_configured_value("MAGNET_TRACKERS", DEFAULT_TRACKERS)
    if isinstance(trackers, str):
        trackers = [trackers]
    params = [f"xt=urn:btih:{info_hash}", f"dn={quote_plus(name)}"]
    for tracker in trackers or ():
        if tracker:
            params.append(f"tr={quote_plus(str(tracker))}")
    return "magnet:?" + "&".join(params)


def _extract_seeders(payload: Dict[str, Any]) -> int:
    for key in ("seeders", "seeds", "Seeders", "seeders_count", "num_seeders", "seedersCount"):
        if key in payload:
            try:
                return int(payload[key])
            except (TypeError, ValueError):
                continue
    return 0


def _extract_info_hash(payload: Dict[str, Any]) -> Optional[str]:
    for key in ("info_hash", "hash", "infoHash", "torrent_hash"):
        value = payload.get(key)
        if value:
            return str(value)
    return None


def _is_valid_info_hash(value: Optional[str]) -> bool:
    if not value or not isinstance(value, str):
        return False
    normalized = value.strip()
    return len(normalized) == 40 and all(ch in string.hexdigits for ch in normalized)


def _search_via_yts(query: str, session: requests.Session, timeout: int = 15) -> Optional[str]:
    """Поиск через YTS API (английские фильмы)."""
    try:
        url = "https://yts.mx/api/v2/list_movies.json"
        params = {"query_term": query, "limit": 20, "sort_by": "seeds"}
        response = session.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") == "ok" and data.get("data", {}).get("movies"):
            movies = data["data"]["movies"]
            trackers = _get_configured_value("MAGNET_TRACKERS", DEFAULT_TRACKERS)
            
            for movie in movies:
                torrents = movie.get("torrents", [])
                # Ищем 1080p торрент
                for torrent in torrents:
                    if torrent.get("quality") in ["1080p", "1080p.x265"]:
                        info_hash = torrent.get("hash")
                        if _is_valid_info_hash(info_hash):
                            title = f"{movie.get('title', query)} {torrent.get('quality')}"
                            return _build_magnet(info_hash, title, trackers)
                
                # Если нет 1080p, берем лучший доступный
                if torrents:
                    best_torrent = max(torrents, key=lambda t: t.get("seeds", 0))
                    info_hash = best_torrent.get("hash")
                    if _is_valid_info_hash(info_hash):
                        title = f"{movie.get('title', query)} {best_torrent.get('quality')}"
                        return _build_magnet(info_hash, title, trackers)
    except Exception as exc:
        _logger.debug(f"YTS search failed: {exc}")
        return None


def _search_via_piratebay(query: str, session: requests.Session, timeout: int = 15) -> Optional[str]:
    """Поиск через Pirate Bay API (старый метод, работает с английскими названиями)."""
    try:
        base_url = _get_configured_value("MAGNET_SEARCH_URL", DEFAULT_SEARCH_URL)
        response = session.get(base_url.format(query=quote_plus(query)), timeout=timeout)
        response.raise_for_status()
        data = response.json()

        if isinstance(data, dict) and "results" in data:
            results = data.get("results") or []
        elif isinstance(data, list):
            results = data
        else:
            return None

        if not results:
            return None

        quality_keywords = ("1080p", "1080")
        filtered: list[Dict[str, Any]] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("title") or "")
            lower_name = name.lower()
            if any(q in lower_name for q in quality_keywords):
                filtered.append(item)

        candidates = filtered or [item for item in results if isinstance(item, dict)]
        if not candidates:
            return None

        candidates.sort(key=_extract_seeders, reverse=True)
        trackers = _get_configured_value("MAGNET_TRACKERS", DEFAULT_TRACKERS)

        for item in candidates:
            name = str(item.get("name") or item.get("title") or query)
            if "no results" in name.lower():
                continue
            magnet = item.get("magnet") or item.get("magnet_link") or item.get("magnetLink")
            if magnet and isinstance(magnet, str) and magnet.strip():
                return magnet
            info_hash = _extract_info_hash(item)
            if _is_valid_info_hash(info_hash):
                return _build_magnet(info_hash.strip(), name, trackers)
    except Exception as exc:
        _logger.debug(f"PirateBay search failed: {exc}")
    return None


def _search_via_rutracker_proxy(query: str, session: requests.Session, timeout: int = 15) -> Optional[str]:
    """Поиск через публичное API RuTracker (с поддержкой русского языка)."""
    try:
        # Используем публичный API-прокси для RuTracker
        url = f"https://rutracker.org/forum/tracker.php?nm={quote_plus(query)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        # Примечание: полноценный парсинг RuTracker требует авторизации
        # Это базовая заглушка, которая может быть расширена
        _logger.info(f"RuTracker search attempted for: {query}")
        
    except Exception as exc:
        _logger.debug(f"RuTracker proxy search failed: {exc}")
    return None


def _has_cyrillic(text: str) -> bool:
    """Проверяет, содержит ли текст кириллические символы."""
    return bool(text and any('\u0400' <= c <= '\u04FF' for c in text))


def _transliterate_russian(text: str) -> str:
    """Транслитерация русского текста в латиницу."""
    translit_dict = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '',
        'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
        'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'Yo',
        'Ж': 'Zh', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M',
        'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
        'Ф': 'F', 'Х': 'H', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Sch', 'Ъ': '',
        'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya'
    }
    return ''.join(translit_dict.get(c, c) for c in text)


def search_best_magnet(title: str, *, session: Optional[requests.Session] = None, timeout: int = 15) -> Optional[str]:
    """Ищет лучшую magnet-ссылку для указанного названия фильма.
    
    Функция последовательно пробует несколько источников поиска:
    1. YTS API (для английских названий, высокое качество)
    2. Pirate Bay API (универсальный, работает с английскими названиями)
    3. Транслитерация + повторный поиск (для русских названий)
    
    Для русских названий автоматически применяется транслитерация.
    """
    query = (title or "").strip()
    if not query:
        return None

    session = session or requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    
    is_cyrillic = _has_cyrillic(query)
    _logger.info(f"Searching magnet for: '{query}' (Cyrillic: {is_cyrillic})")

    # Список вариантов запроса для поиска
    search_queries = [query]
    
    # Если название на русском, добавляем транслитерированный вариант
    if is_cyrillic:
        transliterated = _transliterate_russian(query)
        if transliterated and transliterated != query:
            search_queries.append(transliterated)
            _logger.info(f"Added transliterated variant: '{transliterated}'")

    # Источники поиска по приоритету
    search_methods = [
        ("YTS", _search_via_yts),
        ("PirateBay", _search_via_piratebay),
    ]

    # Пробуем каждый вариант запроса с каждым источником
    for query_variant in search_queries:
        _logger.info(f"Searching with variant: '{query_variant}'")
        
        for source_name, search_func in search_methods:
            try:
                _logger.info(f"  → Trying {source_name}...")
                magnet = search_func(query_variant, session, timeout)
                if magnet:
                    _logger.info(f"  ✓ Found magnet via {source_name} for '{query_variant}'!")
                    return magnet
                else:
                    _logger.debug(f"  ✗ {source_name}: no results")
            except Exception as exc:
                _logger.debug(f"  ✗ {source_name} error: {exc}")
            continue
    
    _logger.warning(f"❌ No magnet found for: '{query}' (tried {len(search_queries)} variants)")
    return None


def _store_identifier(kinopoisk_id: int, magnet_link: str) -> None:
    identifier = MovieIdentifier.query.get(kinopoisk_id)
    if identifier:
        identifier.magnet_link = magnet_link
    else:
        identifier = MovieIdentifier(kinopoisk_id=kinopoisk_id, magnet_link=magnet_link)
        db.session.add(identifier)


def _search_worker(app, kinopoisk_id: int, query: str) -> Dict[str, Any]:
    with app.app_context():
        result: Dict[str, Any] = {
            "status": "running",
            "kinopoisk_id": kinopoisk_id,
            "query": query,
            "has_magnet": False,
            "magnet_link": "",
        }
        try:
            magnet_link = search_best_magnet(query)
            if magnet_link:
                _store_identifier(kinopoisk_id, magnet_link)
                db.session.commit()
                result.update(
                    {
                        "status": "completed",
                        "has_magnet": True,
                        "magnet_link": magnet_link,
                        "message": "Magnet-ссылка успешно найдена.",
                    }
                )
            else:
                db.session.commit()
                result.update(
                    {
                        "status": "not_found",
                        "message": "Подходящая magnet-ссылка не найдена.",
                    }
                )
        except Exception as exc:  # noqa: BLE001 - логируем и возвращаем ошибку
            db.session.rollback()
            _logger.exception("Ошибка поиска magnet для %s", kinopoisk_id)
            result.update(
                {
                    "status": "failed",
                    "message": f"Ошибка при поиске magnet: {exc}",
                    "error": str(exc),
                }
            )
        return result


def _set_task_entry(kinopoisk_id: int, future: Future, query: str) -> None:
    with _tasks_lock:
        _tasks[kinopoisk_id] = {"future": future, "query": query, "result": None}


def _update_task_result(kinopoisk_id: int, future: Future) -> None:
    try:
        result = future.result()
    except Exception as exc:  # noqa: BLE001 - фиксируем в результатах
        result = {
            "status": "failed",
            "kinopoisk_id": kinopoisk_id,
            "has_magnet": False,
            "magnet_link": "",
            "message": f"Ошибка при поиске magnet: {exc}",
            "error": str(exc),
        }
    with _tasks_lock:
        entry = _tasks.get(kinopoisk_id)
        if entry is not None:
            entry["result"] = result


def _get_task_entry(kinopoisk_id: int) -> Optional[Dict[str, Any]]:
    with _tasks_lock:
        return _tasks.get(kinopoisk_id)


def start_background_search(kinopoisk_id: int, query: str, *, force: bool = False) -> Dict[str, Any]:
    query = (query or "").strip()
    if not query:
        return {
            "status": "failed",
            "kinopoisk_id": kinopoisk_id,
            "has_magnet": False,
            "magnet_link": "",
            "message": "Не указан поисковый запрос.",
        }

    identifier = MovieIdentifier.query.get(kinopoisk_id)
    if identifier and identifier.magnet_link and not force:
        return {
            "status": "completed",
            "kinopoisk_id": kinopoisk_id,
            "has_magnet": True,
            "magnet_link": identifier.magnet_link,
            "message": "Magnet-ссылка уже сохранена.",
        }

    entry = _get_task_entry(kinopoisk_id)
    if entry:
        future = entry.get("future")
        if future and not future.done() and not force:
            return {
                "status": "running",
                "kinopoisk_id": kinopoisk_id,
                "has_magnet": False,
                "magnet_link": "",
                "message": "Поиск уже выполняется.",
            }

    app = current_app._get_current_object()
    future = _search_executor.submit(_search_worker, app, kinopoisk_id, query)
    future.add_done_callback(lambda f, kp_id=kinopoisk_id: _update_task_result(kp_id, f))
    _set_task_entry(kinopoisk_id, future, query)
    return {
        "status": "queued",
        "kinopoisk_id": kinopoisk_id,
        "has_magnet": False,
        "magnet_link": "",
        "message": "Поиск magnet-ссылки запущен.",
    }


def get_search_status(kinopoisk_id: int) -> Dict[str, Any]:
    entry = _get_task_entry(kinopoisk_id)
    if entry:
        future: Future = entry.get("future")
        if future and not future.done():
            return {
                "status": "running",
                "kinopoisk_id": kinopoisk_id,
                "has_magnet": False,
                "magnet_link": "",
                "message": "Поиск выполняется.",
            }
        result = entry.get("result")
        if result is None and future:
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001 - переводим в понятный ответ
                result = {
                    "status": "failed",
                    "kinopoisk_id": kinopoisk_id,
                    "has_magnet": False,
                    "magnet_link": "",
                    "message": f"Ошибка при поиске magnet: {exc}",
                    "error": str(exc),
                }
            entry["result"] = result
        if result:
            return result

    identifier = MovieIdentifier.query.get(kinopoisk_id)
    if identifier and identifier.magnet_link:
        return {
            "status": "completed",
            "kinopoisk_id": kinopoisk_id,
            "has_magnet": True,
            "magnet_link": identifier.magnet_link,
            "message": "Magnet-ссылка сохранена.",
        }

    return {
        "status": "idle",
        "kinopoisk_id": kinopoisk_id,
        "has_magnet": False,
        "magnet_link": "",
        "message": "Поиск magnet еще не запускался.",
    }
