#!/usr/bin/env python
"""
Скрипт для добавления колонки poster_file_path в таблицу library_movie.
Запускать напрямую без Flask.
"""

import sqlite3
import os

# Путь к базе данных
db_path = os.path.join(os.path.dirname(__file__), 'instance', 'lottery.db')

print(f"База данных: {db_path}")

if not os.path.exists(db_path):
    print("Ошибка: база данных не найдена!")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Проверяем, существует ли уже колонка
cursor.execute("PRAGMA table_info(library_movie)")
columns = [col[1] for col in cursor.fetchall()]

if 'poster_file_path' in columns:
    print("Колонка poster_file_path уже существует")
else:
    print("Добавляем колонку poster_file_path...")
    cursor.execute("ALTER TABLE library_movie ADD COLUMN poster_file_path VARCHAR(500)")
    conn.commit()
    print("Колонка добавлена успешно!")

conn.close()
print("Готово!")

