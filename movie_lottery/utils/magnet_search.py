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


def _search_via_piratebay(query: str, session: requests.Session, timeout: int = 15, prefer_russian: bool = True) -> Optional[str]:
    """Поиск через Pirate Bay API с приоритетом на русскую озвучку."""
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

        candidates = [item for item in results if isinstance(item, dict) and "no results" not in str(item.get("name") or item.get("title") or "").lower()]

        if not candidates:
            return None

        candidates.sort(key=lambda x: _calculate_torrent_score(x, prefer_1080p=True), reverse=True)
        
        trackers = _get_configured_value("MAGNET_TRACKERS", DEFAULT_TRACKERS)
        
        for i, item in enumerate(candidates[:3], 1):
            name = str(item.get("name") or item.get("title") or "")
            score = _calculate_torrent_score(item)
            has_rus = _has_russian_audio(name)
            seeds = _extract_seeders(item)
            _logger.debug(f"  #{i} (score={score:.1f}, rus={has_rus}, seeds={seeds}): {name[:80]}")

        for item in candidates:
            name = str(item.get("name") or item.get("title") or query)
            
            magnet = item.get("magnet") or item.get("magnet_link") or item.get("magnetLink")
            if magnet and isinstance(magnet, str) and magnet.strip():
                has_rus = _has_russian_audio(name)
                _logger.info(f"Selected torrent (Russian audio: {has_rus}): {name[:80]}")
                return magnet
            
            info_hash = _extract_info_hash(item)
            if _is_valid_info_hash(info_hash):
                has_rus = _has_russian_audio(name)
                _logger.info(f"Selected torrent (Russian audio: {has_rus}): {name[:80]}")
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


def _has_russian_audio(torrent_name: str) -> bool:
    """Проверяет, содержит ли название торрента указание на русскую озвучку."""
    if not torrent_name:
        return False
    
    name_lower = torrent_name.lower()
    
    # Ключевые слова русской озвучки
    russian_audio_keywords = [
        'дубляж', 'дублированный', 'многоголос', 'двухголос',
        'профессиональный', 'лицензия', 'лиц.', 
        'дубл.', 'dubl', 'rus', 'russian',
        'звук', 'озвуч', 'перевод',
        # Конкретные студии озвучки
        'baibako', 'lostfilm', 'newstudio', 'alexfilm',
        'paramount comedy', 'кураж-бамбей', 'amedia'
    ]
    
    # Проверяем наличие хотя бы одного ключевого слова
    return any(keyword in name_lower for keyword in russian_audio_keywords)


def _calculate_torrent_score(torrent_data: Dict[str, Any], prefer_1080p: bool = True) -> float:
    """Вычисляет балл торрента на основе качества и количества сидов.
    
    Балансирует между:
    - Качеством видео (1080p получает бонус)
    - Количеством сидеров
    - Наличием русской озвучки (получает огромный бонус)
    """
    score = 0.0
    
    # Базовый балл от сидов (логарифмическая шкала для баланса)
    seeders = _extract_seeders(torrent_data)
    if seeders > 0:
        import math
        score += math.log10(seeders + 1) * 10  # макс ~20-30 баллов для 100+ сидов
    
    # Бонус за качество 1080p
    name = str(torrent_data.get("name") or torrent_data.get("title") or "")
    if prefer_1080p and ("1080p" in name.lower() or "1080" in name.lower()):
        score += 50  # Большой бонус за 1080p
    
    # Огромный бонус за русскую озвучку
    if _has_russian_audio(name):
        score += 100  # Русская озвучка - приоритет номер 1!
    
    return score


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
    """Ищет лучшую magnet-ссылку для указанного названия фильма с русской озвучкой.
    
    Приоритет поиска:
    1. Торренты с русской озвучкой (дубляж, многоголосый)
    2. Качество 1080p
    3. Количество сидов
    
    Функция автоматически добавляет ключевые слова для поиска русской озвучки
    и использует балансировку между качеством и сидами.
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

    # Создаем варианты запросов с приоритетом на русскую озвучку
    search_queries = []
    
    if is_cyrillic:
        # Для русских названий
        search_queries.append(f"{query} дубляж")  # С явным указанием дубляжа
        search_queries.append(f"{query} многоголосый")  # Альтернативный вариант
        search_queries.append(query)  # Оригинальный запрос
        
        # Добавляем транслитерированные варианты
        transliterated = _transliterate_russian(query)
        if transliterated and transliterated != query:
            search_queries.append(f"{transliterated} russian")
            search_queries.append(transliterated)
            _logger.info(f"Added transliterated variants")
    else:
        # Для английских названий ищем версии с русской озвучкой
        search_queries.append(f"{query} дубляж 1080p")  # Приоритет: дубляж + качество
        search_queries.append(f"{query} многоголосый")  # Многоголосая озвучка
        search_queries.append(f"{query} russian")  # Английский запрос + russian
        search_queries.append(f"{query} rus")  # Короткая форма
        search_queries.append(query)  # Оригинальный запрос (fallback)

    # Источники поиска: PirateBay лучше для русской озвучки
    search_methods = [
        ("PirateBay (RUS priority)", _search_via_piratebay),
    ]

    # Пробуем каждый вариант запроса
    for i, query_variant in enumerate(search_queries, 1):
        _logger.info(f"[{i}/{len(search_queries)}] Searching with: '{query_variant}'")
        
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
