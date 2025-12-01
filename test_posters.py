import json
import requests

# Проверяем библиотеку
print("=== Проверка библиотеки ===")
try:
    resp = requests.get("http://localhost:8888/api/library")
    data = resp.json()
    movies = data.get('movies', [])
    print(f"Фильмов в библиотеке: {len(movies)}")
    for m in movies[:3]:
        poster = m.get('poster') or 'NULL'
        print(f"  - {m.get('name')}: poster={poster[:80]}...")
except Exception as e:
    print(f"Ошибка: {e}")

# Создаём опрос из первых 2 фильмов
print("\n=== Создание опроса ===")
try:
    if len(movies) >= 2:
        poll_movies = []
        for m in movies[:2]:
            poll_movies.append({
                'kinopoisk_id': m.get('kinopoisk_id'),
                'name': m.get('name'),
                'search_name': m.get('search_name'),
                'poster': m.get('poster'),
                'year': m.get('year'),
                'description': m.get('description'),
                'rating_kp': m.get('rating_kp'),
                'genres': m.get('genres'),
                'countries': m.get('countries'),
                'points': m.get('points', 1),
            })
        
        resp = requests.post(
            "http://localhost:8888/api/polls/create",
            json={'movies': poll_movies}
        )
        create_data = resp.json()
        print(f"Опрос создан: {create_data}")
        
        poll_id = create_data.get('poll_id')
        if poll_id:
            print(f"\n=== Проверка опроса {poll_id} ===")
            resp = requests.get(f"http://localhost:8888/api/polls/{poll_id}")
            poll_data = resp.json()
            poll_movies = poll_data.get('movies', [])
            print(f"Фильмов в опросе: {len(poll_movies)}")
            for m in poll_movies:
                poster = m.get('poster') or 'NULL'
                print(f"  - {m.get('name')}: poster={poster[:80] if poster != 'NULL' else 'NULL'}...")
    else:
        print("Недостаточно фильмов в библиотеке")
except Exception as e:
    print(f"Ошибка: {e}")

