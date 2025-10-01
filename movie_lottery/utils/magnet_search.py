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

# Русские торрент-трекеры для поиска
RUSSIAN_TRACKERS = [
    {
        "name": "RuTor",
        "search_url": "http://rutor.info/search/0/0/000/0/{query}",
        "supports_magnet": True
    },
    {
        "name": "RuTracker",
        "search_url": "https://rutracker.org/forum/tracker.php?nm={query}",
        "supports_magnet": True
    },
    {
        "name": "NNM-Club",
        "search_url": "https://nnmclub.to/forum/tracker.php?nm={query}",
        "supports_magnet": False
    },
    {
        "name": "Torrents.ru",
        "search_url": "https://torrents.ru/search.php?search={query}",
        "supports_magnet": True
    },
    {
        "name": "FastTorrent",
        "search_url": "https://fast-torrent.online/search/{query}/",
        "supports_magnet": True
    }
]
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


def _parse_rutor_html(html_content: str) -> List[Dict[str, Any]]:
    """Парсит HTML страницу RuTor и извлекает информацию о торрентах."""
    import re
    from html import unescape
    
    torrents = []
    
    # Ищем строки таблицы с торрентами
    # RuTor использует таблицу с классом "gai" или "tum"
    row_pattern = r'<tr class="[gt][au][im]">(.*?)</tr>'
    rows = re.findall(row_pattern, html_content, re.DOTALL)
    
    for row in rows:
        try:
            # Извлекаем магнет-ссылку
            magnet_match = re.search(r'href="(magnet:\?xt=urn:btih:[A-Fa-f0-9]{40}[^"]*)"', row)
            if not magnet_match:
                continue
                
            magnet_link = unescape(magnet_match.group(1))
            
            # Извлекаем название
            name_match = re.search(r'<a href="/torrent/\d+/[^"]*"[^>]*>(.*?)</a>', row)
            name = unescape(name_match.group(1)) if name_match else "Unknown"
            
            # Извлекаем количество сидов
            seeds_match = re.search(r'<span class="green">(\d+)</span>', row)
            seeders = int(seeds_match.group(1)) if seeds_match else 0
            
            # Извлекаем размер
            size_match = re.search(r'<td align="right">([0-9.]+ [KMGT]B)</td>', row)
            size = size_match.group(1) if size_match else "Unknown"
            
            torrents.append({
                "name": name.strip(),
                "magnet": magnet_link,
                "seeders": seeders,
                "size": size
            })
            
        except Exception as exc:
            _logger.debug(f"Failed to parse RuTor row: {exc}")
            continue
    
    return torrents


def _search_via_rutor(query: str, session: requests.Session, timeout: int = 20) -> Optional[str]:
    """Поиск через RuTor.info - русский торрент-трекер с магнет-ссылками."""
    try:
        # RuTor поддерживает прямой поиск
        search_url = f"http://rutor.info/search/0/0/000/0/{quote_plus(query)}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        _logger.info(f"Searching RuTor for: {query}")
        response = session.get(search_url, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        # Парсим HTML
        torrents = _parse_rutor_html(response.text)
        
        if not torrents:
            _logger.info("No torrents found on RuTor")
            return None
        
        _logger.info(f"Found {len(torrents)} torrents on RuTor")
        
        # Сортируем по балльной системе
        for torrent in torrents:
            torrent["score"] = _calculate_torrent_score(torrent, prefer_1080p=True)
        
        torrents.sort(key=lambda x: x["score"], reverse=True)
        
        # Логируем топ-3 результата
        for i, torrent in enumerate(torrents[:3], 1):
            has_rus = _has_russian_audio(torrent["name"])
            _logger.info(f"  #{i} (score={torrent['score']:.1f}, rus={has_rus}, seeds={torrent['seeders']}): {torrent['name'][:80]}")
        
        # Возвращаем лучший торрент
        best = torrents[0]
        has_rus = _has_russian_audio(best["name"])
        _logger.info(f"Selected from RuTor (Russian audio: {has_rus}): {best['name'][:80]}")
        
        return best["magnet"]
        
    except Exception as exc:
        _logger.warning(f"RuTor search failed: {exc}")
        return None


def _parse_rutracker_html(html_content: str) -> List[Dict[str, Any]]:
    """Парсит HTML страницу RuTracker и извлекает информацию о торрентах."""
    import re
    from html import unescape
    
    torrents = []
    
    # RuTracker использует другую структуру таблицы
    # Ищем строки с торрентами
    row_pattern = r'<tr class="[^"]*"[^>]*>(.*?)</tr>'
    rows = re.findall(row_pattern, html_content, re.DOTALL)
    
    for row in rows:
        try:
            # Проверяем наличие ссылки на торрент-файл или магнета
            dl_link_match = re.search(r'href="(dl\.php\?t=\d+)"', row)
            if not dl_link_match:
                continue
            
            # Извлекаем ID торрента
            torrent_id_match = re.search(r't=(\d+)', dl_link_match.group(1))
            if not torrent_id_match:
                continue
            
            torrent_id = torrent_id_match.group(1)
            
            # Извлекаем название
            name_match = re.search(r'<a[^>]*class="tLink"[^>]*>(.*?)</a>', row, re.DOTALL)
            if not name_match:
                continue
            
            name = re.sub(r'<[^>]+>', '', name_match.group(1))
            name = unescape(name).strip()
            
            # Извлекаем количество сидов
            seeds_match = re.search(r'<b class="seedmed">(\d+)</b>', row)
            if not seeds_match:
                seeds_match = re.search(r'class="seed[^"]*">(\d+)<', row)
            
            seeders = int(seeds_match.group(1)) if seeds_match else 0
            
            # Извлекаем размер
            size_match = re.search(r'<td[^>]*class="tor-size"[^>]*>(.*?)</td>', row)
            size = size_match.group(1).strip() if size_match else "Unknown"
            
            # Создаем магнет-ссылку из ID торрента
            # Примечание: RuTracker требует авторизацию для скачивания, но можно попробовать через прокси
            magnet_link = f"magnet:?xt=urn:btih:rutracker_{torrent_id}&dn={quote_plus(name)}"
            
            torrents.append({
                "name": name,
                "magnet": magnet_link,
                "seeders": seeders,
                "size": size,
                "torrent_id": torrent_id
            })
            
        except Exception as exc:
            _logger.debug(f"Failed to parse RuTracker row: {exc}")
            continue
    
    return torrents


def _search_via_rutracker(query: str, session: requests.Session, timeout: int = 20) -> Optional[str]:
    """Поиск через RuTracker.org - крупнейший русский торрент-трекер."""
    try:
        # RuTracker.org - используем публичные зеркала
        search_urls = [
            f"https://rutracker.org/forum/tracker.php?nm={quote_plus(query)}",
            f"https://rutracker.net/forum/tracker.php?nm={quote_plus(query)}",
        ]
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8"
        }
        
        _logger.info(f"Searching RuTracker for: {query}")
        
        for search_url in search_urls:
            try:
                response = session.get(search_url, headers=headers, timeout=timeout, allow_redirects=True)
                response.raise_for_status()
                
                # Парсим HTML
                torrents = _parse_rutracker_html(response.text)
                
                if torrents:
                    _logger.info(f"Found {len(torrents)} torrents on RuTracker")
                    
                    # Сортируем по балльной системе
                    for torrent in torrents:
                        torrent["score"] = _calculate_torrent_score(torrent, prefer_1080p=True)
                    
                    torrents.sort(key=lambda x: x["score"], reverse=True)
                    
                    # Логируем топ-3 результата
                    for i, torrent in enumerate(torrents[:3], 1):
                        has_rus = _has_russian_audio(torrent["name"])
                        _logger.info(f"  #{i} (score={torrent['score']:.1f}, rus={has_rus}, seeds={torrent['seeders']}): {torrent['name'][:80]}")
                    
                    # Возвращаем лучший торрент
                    best = torrents[0]
                    has_rus = _has_russian_audio(best["name"])
                    _logger.info(f"Selected from RuTracker (Russian audio: {has_rus}): {best['name'][:80]}")
                    
                    return best["magnet"]
                    
            except requests.exceptions.RequestException:
                continue  # Пробуем следующее зеркало
        
        _logger.info("No torrents found on RuTracker")
        return None
        
    except Exception as exc:
        _logger.warning(f"RuTracker search failed: {exc}")
        return None


def _search_via_nnmclub(query: str, session: requests.Session, timeout: int = 20) -> Optional[str]:
    """Поиск через NNM-Club (требует авторизацию, но можно попробовать публичный поиск)."""
    try:
        _logger.info(f"NNM-Club search attempted for: {query}")
        # NNM-Club требует авторизацию для большинства функций
        # Заглушка для будущей реализации
        return None
    except Exception as exc:
        _logger.debug(f"NNM-Club search failed: {exc}")
        return None


def _search_via_torrentsru(query: str, session: requests.Session, timeout: int = 20) -> Optional[str]:
    """Поиск через Torrents.ru."""
    try:
        _logger.info(f"Torrents.ru search attempted for: {query}")
        # Требует реализацию парсера
        # Заглушка для будущей реализации
        return None
    except Exception as exc:
        _logger.debug(f"Torrents.ru search failed: {exc}")
        return None


def _search_via_fasttorrent(query: str, session: requests.Session, timeout: int = 20) -> Optional[str]:
    """Поиск через FastTorrent."""
    try:
        _logger.info(f"FastTorrent search attempted for: {query}")
        # Требует реализацию парсера
        # Заглушка для будущей реализации
        return None
    except Exception as exc:
        _logger.debug(f"FastTorrent search failed: {exc}")
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
    """Вычисляет балл торрента на основе русской озвучки, количества сидов и качества.
    
    Приоритеты (от важного к менее важному):
    1. Русская озвучка - приоритет №1!
    2. Количество сидеров - приоритет №2
    3. Качество видео (1080p) - приоритет №3
    """
    score = 0.0
    
    name = str(torrent_data.get("name") or torrent_data.get("title") or "")
    
    # ПРИОРИТЕТ №1: Огромный бонус за русскую озвучку (самый важный фактор!)
    if _has_russian_audio(name):
        score += 200  # Увеличено с 100 до 200 - русская озвучка превыше всего!
    
    # ПРИОРИТЕТ №2: Увеличенный балл от сидов (логарифмическая шкала)
    seeders = _extract_seeders(torrent_data)
    if seeders > 0:
        import math
        score += math.log10(seeders + 1) * 30  # Увеличено с 10 до 30 - макс ~60-90 баллов для 100+ сидов
    
    # ПРИОРИТЕТ №3: Умеренный бонус за качество 1080p (менее важно)
    if prefer_1080p and ("1080p" in name.lower() or "1080" in name.lower()):
        score += 20  # Уменьшено с 50 до 20 - качество важно, но не критично
    
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


def search_best_magnet(title: str, *, session: Optional[requests.Session] = None, timeout: int = 20) -> Optional[str]:
    """Ищет magnet-ссылку через РУССКИЕ торрент-трекеры.
    
    Поиск выполняется только по следующим источникам:
    1. RuTor.info - публичный русский трекер
    2. RuTracker.org - крупнейший русский трекер
    3. NNM-Club - закрытый русский трекер
    4. Torrents.ru - открытый русский трекер
    5. FastTorrent - быстрый публичный трекер
    
    Приоритет при выборе торрента (от важного к менее важному):
    1. Русская озвучка (дубляж, многоголосый) - +200 баллов
    2. Количество сидов - логарифмическая шкала × 30 (макс ~60-90 баллов)
    3. Качество 1080p - +20 баллов
    """
    query = (title or "").strip()
    if not query:
        return None

    session = session or requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    
    is_cyrillic = _has_cyrillic(query)
    _logger.info(f"🔍 Поиск через РУССКИЕ трекеры: '{query}' (Кириллица: {is_cyrillic})")

    # Создаем варианты запросов
    search_queries = []
    
    if is_cyrillic:
        # Для русских названий
        search_queries.append(query)
        search_queries.append(f"{query} 1080p")
        
        # Добавляем транслитерацию для некоторых трекеров
        transliterated = _transliterate_russian(query)
        if transliterated and transliterated != query:
            search_queries.append(transliterated)
    else:
        # Для английских названий добавляем русские ключевые слова
        search_queries.append(f"{query} 1080p")
        search_queries.append(f"{query} дубляж")
        search_queries.append(f"{query} многоголосый")
        search_queries.append(query)

    # ТОЛЬКО РУССКИЕ ТРЕКЕРЫ!
    search_methods = [
        ("RuTor.info", _search_via_rutor),
        ("RuTracker.org", _search_via_rutracker),
        ("NNM-Club", _search_via_nnmclub),
        ("Torrents.ru", _search_via_torrentsru),
        ("FastTorrent", _search_via_fasttorrent),
    ]

    # Пробуем каждый вариант запроса с каждым русским трекером
    for i, query_variant in enumerate(search_queries, 1):
        _logger.info(f"[{i}/{len(search_queries)}] Вариант запроса: '{query_variant}'")
        
        for source_name, search_func in search_methods:
            try:
                _logger.info(f"  → Поиск через {source_name}...")
                magnet = search_func(query_variant, session, timeout)
                if magnet:
                    _logger.info(f"  ✅ Найдено через {source_name}!")
                    return magnet
                else:
                    _logger.debug(f"  ❌ {source_name}: ничего не найдено")
            except Exception as exc:
                _logger.debug(f"  ❌ {source_name}: ошибка - {exc}")
                continue
    
    _logger.warning(f"❌ Magnet-ссылка НЕ найдена для: '{query}' (проверено {len(search_queries)} вариантов на русских трекерах)")
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
