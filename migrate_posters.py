#!/usr/bin/env python
"""
Скрипт для миграции существующих постеров на локальное хранение.
Скачивает все постеры из внешних URL и сохраняет их локально.

Использование:
    python migrate_posters.py
"""

import os
import sqlite3
import requests

# Путь к базе данных и директории для постеров
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'lottery.db')
MEDIA_DIR = os.path.join(BASE_DIR, 'instance', 'media')
POSTER_DIR = os.path.join(MEDIA_DIR, 'posters')


def fix_poster_url(poster_url):
    """Исправляет URL постера с нерабочего домена на рабочий."""
    if not poster_url:
        return poster_url
    if 'image.openmoviedb.com/kinopoisk-images/' in poster_url:
        return poster_url.replace(
            'image.openmoviedb.com/kinopoisk-images/',
            'avatars.mds.yandex.net/get-kinopoisk-image/'
        )
    return poster_url


def download_poster(poster_url, movie_id):
    """Скачивает постер и сохраняет его локально."""
    if not poster_url:
        return None

    fixed_url = fix_poster_url(poster_url)

    try:
        response = requests.get(fixed_url, timeout=15, stream=True)
        response.raise_for_status()

        content_type = response.headers.get('Content-Type', '').lower()
        if 'jpeg' in content_type or 'jpg' in content_type:
            ext = '.jpg'
        elif 'png' in content_type:
            ext = '.png'
        elif 'webp' in content_type:
            ext = '.webp'
        else:
            ext = '.jpg'

        filename = f"poster_{movie_id}{ext}"
        os.makedirs(POSTER_DIR, exist_ok=True)
        absolute_path = os.path.join(POSTER_DIR, filename)

        with open(absolute_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return f"posters/{filename}"

    except Exception as exc:
        print(f"  Ошибка при скачивании: {exc}")
        return None


def migrate_posters():
    """Основная функция миграции."""
    print(f"База данных: {DB_PATH}")
    print(f"Директория для постеров: {POSTER_DIR}")
    
    if not os.path.exists(DB_PATH):
        print("Ошибка: база данных не найдена!")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Получаем все фильмы
    cursor.execute("SELECT id, name, year, poster, poster_file_path FROM library_movie")
    movies = cursor.fetchall()
    total = len(movies)
    
    print(f"\nНайдено {total} фильмов в библиотеке")
    
    downloaded = 0
    skipped = 0
    failed = 0
    
    for i, (movie_id, name, year, poster, poster_file_path) in enumerate(movies, 1):
        print(f"\n[{i}/{total}] {name} ({year})")
        
        # Проверяем, есть ли уже локальный постер
        if poster_file_path:
            print("  Постер уже скачан, пропускаем")
            skipped += 1
            continue
        
        if not poster:
            print("  Нет URL постера, пропускаем")
            skipped += 1
            continue
        
        print(f"  Скачиваем: {poster[:60]}...")
        new_path = download_poster(poster, movie_id)
        
        if new_path:
            cursor.execute(
                "UPDATE library_movie SET poster_file_path = ? WHERE id = ?",
                (new_path, movie_id)
            )
            conn.commit()
            print(f"  ✓ Сохранено: {new_path}")
            downloaded += 1
        else:
            print(f"  ✗ Не удалось скачать")
            failed += 1
    
    conn.close()
    
    print(f"\n{'='*50}")
    print(f"Миграция завершена:")
    print(f"  Скачано: {downloaded}")
    print(f"  Пропущено: {skipped}")
    print(f"  Ошибок: {failed}")


if __name__ == '__main__':
    migrate_posters()
