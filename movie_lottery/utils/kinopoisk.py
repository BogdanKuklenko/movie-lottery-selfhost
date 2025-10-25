import argparse
import json
import os
import re
from typing import Any, Dict, Iterable, Optional, Tuple

import requests
from flask import current_app, has_app_context

_KINOPOISK_URL_PATTERN = re.compile(r"kinopoisk\.ru/(?:film|series|name|movie)/(\d+)", re.IGNORECASE)


def _extract_kinopoisk_id(raw_query: str) -> Optional[str]:
    """Try to extract a Kinopoisk numeric identifier from the provided query."""
    if not raw_query:
        return None

    query = raw_query.strip()
    if not query:
        return None

    url_match = _KINOPOISK_URL_PATTERN.search(query)
    if url_match:
        return url_match.group(1)

    lowered = query.lower()
    if lowered.startswith("kp") and query[2:].isdigit():
        return query[2:]

    if query.isdigit():
        return query

    return None


def _get_logger():
    if has_app_context():
        return getattr(current_app, "logger", None)
    return None


def _log_warning(message: str) -> None:
    logger = _get_logger()
    if logger:
        logger.warning(message)
    else:
        print(message)


def _log_error(message: str) -> None:
    logger = _get_logger()
    if logger:
        logger.error(message)
    else:
        print(message)


def _log_info(message: str) -> None:
    logger = _get_logger()
    if logger:
        logger.info(message)
    else:
        print(message)


def _resolve_api_token() -> Optional[str]:
    if has_app_context():
        config = current_app.config
        token = config.get('KINOPOISK_API_TOKEN') or config.get('KINOPOISK_API_KEY')
        if token:
            return token
    return os.environ.get('KINOPOISK_API_TOKEN') or os.environ.get('KINOPOISK_API_KEY')


def _format_movie_payload(movie_data: Dict[str, Any]) -> Dict[str, Any]:
    genres = [g.get('name') for g in movie_data.get('genres', [])[:3] if g.get('name')]
    countries = [c.get('name') for c in movie_data.get('countries', [])[:3] if c.get('name')]

    search_name = movie_data.get('alternativeName') or movie_data.get('enName')

    poster_data = movie_data.get('poster') or {}
    poster_url = poster_data.get('url') if isinstance(poster_data, dict) else None

    rating_data = movie_data.get('rating') or {}
    rating_kp = rating_data.get('kp') if isinstance(rating_data, dict) else None

    year_value = movie_data.get('year')
    year_str = str(year_value) if year_value not in (None, "") else ""

    return {
        "kinopoisk_id": movie_data.get('id'),
        "name": movie_data.get('name') or 'Название не найдено',
        "search_name": search_name,
        "poster": poster_url,
        "year": year_str,
        "description": movie_data.get('description') or 'Описание отсутствует.',
        "rating_kp": rating_kp if isinstance(rating_kp, (int, float)) else 0.0,
        "genres": ", ".join(genres),
        "countries": ", ".join(countries),
    }


def get_movie_data_from_kinopoisk(query: str) -> Optional[Dict[str, Any]]:
    """
    Search for a movie by name or ID on Kinopoisk and return structured data.
    """
    if not query or not query.strip():
        _log_warning("Пустой запрос к Кинопоиску.")
        return None

    api_token = _resolve_api_token()

    if not api_token:
        _log_warning("Kinopoisk API token is not configured.")
        return None

    headers = {
        "X-API-KEY": api_token,
        "accept": "application/json",
    }

    movie_id = _extract_kinopoisk_id(query)
    if movie_id:
        search_url = f"https://api.kinopoisk.dev/v1.4/movie/{movie_id}"
        params = None
    else:
        search_url = "https://api.kinopoisk.dev/v1.4/movie/search"
        params = {"query": query.strip(), "limit": 1, "page": 1}

    try:
        response = requests.get(search_url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        status_code = getattr(exc.response, "status_code", "unknown")
        _log_warning(f"Kinopoisk API returned status {status_code} for query '{query}': {exc}")
        return None
    except requests.exceptions.RequestException as exc:
        _log_error(f"Ошибка при запросе к API Кинопоиска: {exc}")
        return None

    try:
        data = response.json()
    except ValueError:
        _log_error("Некорректный JSON-ответ от API Кинопоиска.")
        return None
    if not data:
        return None

    movie_data: Optional[Dict[str, Any]] = None

    if isinstance(data, dict):
        docs = data.get('docs') if 'docs' in data else None
        if docs:
            movie_data = docs[0]
        elif data.get('id'):
            movie_data = data  # direct lookup by ID

    if not movie_data:
        return None

    return _format_movie_payload(movie_data)


def _run_real_checks(queries: Iterable[str]) -> Tuple[int, Dict[str, Optional[Dict[str, Any]]]]:
    results: Dict[str, Optional[Dict[str, Any]]] = {}
    failures = 0
    for query in queries:
        movie = get_movie_data_from_kinopoisk(query)
        results[query] = movie
        if movie is None:
            failures += 1
            _log_error(f"Тест не прошёл: не удалось получить данные для запроса '{query}'.")
        else:
            _log_info(f"Тест успешен для запроса '{query}'.")
    return failures, results


def _print_cli_results(results: Dict[str, Optional[Dict[str, Any]]]) -> None:
    for query, movie in results.items():
        header = f"\n=== Результат для запроса: {query} ==="
        print(header)
        if not movie:
            print("Данные не получены.")
            continue
        print(json.dumps(movie, ensure_ascii=False, indent=2))


def _default_cli_queries() -> Iterable[str]:
    return (
        "301",  # Иван Васильевич меняет профессию
        "https://www.kinopoisk.ru/film/435/",  # Брюс Всемогущий
        "Интерстеллар",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Реальные проверки работы Кинопоиск API."
    )
    parser.add_argument(
        "queries",
        nargs="*",
        help="Список запросов (ID, URL или название фильма).",
    )
    args = parser.parse_args()

    queries = args.queries or list(_default_cli_queries())

    api_token = _resolve_api_token()
    if not api_token:
        _log_error(
            "Для запуска требуется переменная окружения KINOPOISK_API_TOKEN или KINOPOISK_API_KEY."
        )
        return 1

    failures, results = _run_real_checks(queries)
    _print_cli_results(results)
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
