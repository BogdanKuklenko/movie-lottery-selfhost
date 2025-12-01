import os
import sys

# Нужен Flask app context для работы API
sys.path.insert(0, '.')
os.environ.setdefault('FLASK_APP', 'run.py')

from movie_lottery import create_app
from movie_lottery.utils.kinopoisk import get_movie_data_from_kinopoisk

app = create_app()
with app.app_context():
    data, err = get_movie_data_from_kinopoisk('Интерстеллар')
    if data:
        print(f"Название: {data.get('name')}")
        print(f"Poster URL: {data.get('poster')}")
    else:
        print(f"Ошибка: {err}")

