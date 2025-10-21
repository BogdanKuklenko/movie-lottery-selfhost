import re
import requests
from flask import current_app


def get_movie_data_from_kinopoisk(query):
    """
    Search for a movie by name or ID on Kinopoisk and return structured data.
    """
    config = current_app.config
    headers = {"X-API-KEY": config['KINOPOISK_API_TOKEN']}
    params = {}
    
    kinopoisk_id_match = re.search(r'kinopoisk\.ru/(?:film|series)/(\d+)/', query)
    
    if kinopoisk_id_match:
        movie_id = kinopoisk_id_match.group(1)
        search_url = f"https://api.kinopoisk.dev/v1.4/movie/{movie_id}"
    else:
        search_url = "https://api.kinopoisk.dev/v1.4/movie/search"
        params['query'] = query
        params['limit'] = 1
        
    try:
        response = requests.get(search_url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        if 'docs' in data and data['docs']:
            movie_data = data['docs'][0]
        elif 'id' in data:
            movie_data = data
        else:
            return None
            
        genres = [g['name'] for g in movie_data.get('genres', [])[:3]]
        countries = [c['name'] for c in movie_data.get('countries', [])[:3]]
        
        search_name = movie_data.get('alternativeName') or movie_data.get('enName')

        return {
            "kinopoisk_id": movie_data.get('id'),
            "name": movie_data.get('name', 'Название не найдено'),
            "search_name": search_name,
            "poster": movie_data.get('poster', {}).get('url'),
            "year": str(movie_data.get('year', '')),
            "description": movie_data.get('description', 'Описание отсутствует.'),
            "rating_kp": movie_data.get('rating', {}).get('kp', 0.0),
            "genres": ", ".join(genres),
            "countries": ", ".join(countries)
        }
        
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе к API Кинопоиска: {e}")
        return None