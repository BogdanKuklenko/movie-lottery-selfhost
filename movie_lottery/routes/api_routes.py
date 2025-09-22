# F:\GPT\movie-lottery V2\movie_lottery\routes\api_routes.py
import random
from flask import Blueprint, request, jsonify, url_for, current_app
from qbittorrentapi import Client, exceptions as qbittorrent_exceptions

from .. import db
from ..models import Movie, Lottery, MovieIdentifier, LibraryMovie
from ..utils.kinopoisk import get_movie_data_from_kinopoisk
from ..utils.helpers import generate_unique_id, ensure_background_photo
from ..utils.qbittorrent import get_active_torrents_map

api_bp = Blueprint('api', __name__, url_prefix='/api')

# --- Маршруты для работы с фильмами и лотереями ---

@api_bp.route('/fetch-movie', methods=['POST'])
def get_movie_info():
    query = request.json.get('query')
    if not query:
        return jsonify({"error": "Пустой запрос"}), 400
    movie_data = get_movie_data_from_kinopoisk(query)
    if movie_data:
        return jsonify(movie_data)
    else:
        return jsonify({"error": "Фильм не найден"}), 404

@api_bp.route('/create', methods=['POST'])
def create_lottery():
    movies_json = request.json.get('movies')
    if not movies_json or len(movies_json) < 2:
        return jsonify({"error": "Нужно добавить хотя бы два фильма"}), 400
    
    new_lottery = Lottery(id=generate_unique_id())
    db.session.add(new_lottery)

    for movie_data in movies_json:
        new_movie = Movie(
            kinopoisk_id=movie_data.get('kinopoisk_id'),
            name=movie_data['name'],
            poster=movie_data.get('poster'),
            year=movie_data.get('year'),
            description=movie_data.get('description'),
            rating_kp=movie_data.get('rating_kp'),
            genres=movie_data.get('genres'),
            countries=movie_data.get('countries'),
            lottery=new_lottery
        )
        db.session.add(new_movie)
        if poster := movie_data.get('poster'):
            ensure_background_photo(poster)

    db.session.commit()
    # url_for для маршрутов в других blueprint'ах требует указания имени blueprint'а
    wait_url = url_for('main.wait_for_result', lottery_id=new_lottery.id)
    return jsonify({"wait_url": wait_url})

@api_bp.route('/draw/<lottery_id>', methods=['POST'])
def draw_winner(lottery_id):
    lottery = Lottery.query.get_or_404(lottery_id)
    if lottery.result_name:
        return jsonify({
            "name": lottery.result_name, 
            "poster": lottery.result_poster, 
            "year": lottery.result_year
        })
    
    winner = random.choice(lottery.movies)
    lottery.result_name = winner.name
    lottery.result_poster = winner.poster
    lottery.result_year = winner.year
    db.session.commit()
    return jsonify({
        "name": winner.name, 
        "poster": winner.poster, 
        "year": winner.year
    })

@api_bp.route('/result/<lottery_id>')
def get_result_data(lottery_id):
    lottery = Lottery.query.get_or_404(lottery_id)
    active_torrents = get_active_torrents_map()
    movies_data = []

    for m in lottery.movies:
        identifier = MovieIdentifier.query.get(m.kinopoisk_id) if m.kinopoisk_id else None
        is_on_client = m.kinopoisk_id in active_torrents if m.kinopoisk_id else False
        movies_data.append({
            "kinopoisk_id": m.kinopoisk_id, "name": m.name, "poster": m.poster, "year": m.year,
            "description": m.description, "rating_kp": m.rating_kp, "genres": m.genres, "countries": m.countries,
            "has_magnet": bool(identifier), "magnet_link": identifier.magnet_link if identifier else None,
            "is_on_client": is_on_client, "torrent_hash": active_torrents.get(m.kinopoisk_id) if is_on_client else None
        })

    result_data = next((m for m in movies_data if m["name"] == lottery.result_name), None) if lottery.result_name else None
    return jsonify({
        "movies": movies_data, 
        "result": result_data, 
        "createdAt": lottery.created_at.isoformat() + "Z", 
        "play_url": url_for('main.play_lottery', lottery_id=lottery.id, _external=True)
    })
    
@api_bp.route('/delete-lottery/<lottery_id>', methods=['POST'])
def delete_lottery(lottery_id):
    lottery_to_delete = Lottery.query.get_or_404(lottery_id)
    message = ""
    config = current_app.config
    try:
        qbt_client = Client(host=config['QBIT_HOST'], port=config['QBIT_PORT'], username=config['QBIT_USERNAME'], password=config['QBIT_PASSWORD'])
        qbt_client.auth_log_in()
        
        category = f"lottery-{lottery_id}"
        torrents_to_delete = qbt_client.torrents_info(category=category)
        
        if torrents_to_delete:
            hashes_to_delete = [t.hash for t in torrents_to_delete]
            qbt_client.torrents_delete(delete_files=True, torrent_hashes=hashes_to_delete)
            message = "Лотерея и связанный торрент успешно удалены."
        else:
            message = "Торрент не найден в клиенте. Лотерея удалена из истории."
            
        qbt_client.auth_log_out()

    except (qbittorrent_exceptions.APIConnectionError, requests.exceptions.RequestException):
        message = "Не удалось подключиться к qBittorrent. Лотерея будет удалена только из истории."
    except Exception as e:
        message = f"Произошла ошибка qBittorrent: {e}. Лотерея будет удалена только из истории."
    
    db.session.delete(lottery_to_delete)
    db.session.commit()
    return jsonify({"success": True, "message": message})

# --- Маршруты для Библиотеки ---

@api_bp.route('/library', methods=['POST'])
def add_library_movie():
    movie_data = request.json.get('movie', {})
    if not movie_data.get('name'):
        return jsonify({"success": False, "message": "Не удалось определить название фильма."}), 400
    
    existing_movie = None
    if kinopoisk_id := movie_data.get('kinopoisk_id'):
        existing_movie = LibraryMovie.query.filter_by(kinopoisk_id=kinopoisk_id).first()
    
    if not existing_movie:
         existing_movie = LibraryMovie.query.filter_by(name=movie_data['name'], year=movie_data.get('year')).first()

    if existing_movie:
        # Обновляем существующий фильм
        for key, value in movie_data.items():
            if hasattr(existing_movie, key) and value is not None:
                setattr(existing_movie, key, value)
        existing_movie.added_at = db.func.now()
        message = "Информация о фильме обновлена в библиотеке."
    else:
        # Создаем новый фильм
        new_movie = LibraryMovie(**movie_data)
        db.session.add(new_movie)
        message = "Фильм добавлен в библиотеку."
        
    db.session.commit()
    return jsonify({"success": True, "message": message})

@api_bp.route('/library/<int:movie_id>', methods=['DELETE'])
def remove_library_movie(movie_id):
    library_movie = LibraryMovie.query.get_or_404(movie_id)
    db.session.delete(library_movie)
    db.session.commit()
    return jsonify({"success": True, "message": "Фильм удален из библиотеки."})

# --- Маршруты для работы с торрентами ---

@api_bp.route('/movie-magnet', methods=['POST'])
def save_movie_magnet():
    data = request.json
    kinopoisk_id = data.get('kinopoisk_id')
    magnet_link = (data.get('magnet_link') or '').strip()

    if not kinopoisk_id:
        return jsonify({"success": False, "message": "Отсутствует ID фильма"}), 400

    identifier = MovieIdentifier.query.get(kinopoisk_id)
    
    if magnet_link:
        if identifier:
            identifier.magnet_link = magnet_link
        else:
            identifier = MovieIdentifier(kinopoisk_id=kinopoisk_id, magnet_link=magnet_link)
            db.session.add(identifier)
        message = "Magnet-ссылка сохранена."
    elif identifier:
        db.session.delete(identifier)
        message = "Magnet-ссылка удалена."
    else:
        message = "Действий не требуется."

    db.session.commit()
    refreshed_identifier = MovieIdentifier.query.get(kinopoisk_id)
    return jsonify({
        "success": True, "message": message,
        "has_magnet": bool(refreshed_identifier),
        "magnet_link": refreshed_identifier.magnet_link if refreshed_identifier else "",
    })

@api_bp.route('/start-download/<int:kinopoisk_id>', methods=['POST'])
def start_download(kinopoisk_id):
    identifier = MovieIdentifier.query.get_or_404(kinopoisk_id)
    # Определяем категорию
    movie_in_lottery = Movie.query.filter_by(kinopoisk_id=kinopoisk_id).order_by(Movie.id.desc()).first()
    category = f"lottery-{movie_in_lottery.lottery_id}" if movie_in_lottery else "lottery-default"
    
    config = current_app.config
    try:
        qbt_client = Client(host=config['QBIT_HOST'], port=config['QBIT_PORT'], username=config['QBIT_USERNAME'], password=config['QBIT_PASSWORD'])
        qbt_client.auth_log_in()
        qbt_client.torrents_add(
            urls=identifier.magnet_link, category=category,
            is_sequential_download=True, is_first_last_piece_priority=True,
            tags=f"kp-{kinopoisk_id}",
        )
        qbt_client.auth_log_out()
        return jsonify({"success": True, "message": "Загрузка началась!"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка qBittorrent: {e}"}), 500

@api_bp.route('/library/start-download/<int:movie_id>', methods=['POST'])
def start_library_download(movie_id):
    library_movie = LibraryMovie.query.get_or_404(movie_id)
    if not library_movie.kinopoisk_id:
        return jsonify({"success": False, "message": "Для фильма не указан kinopoisk_id."}), 400

    identifier = MovieIdentifier.query.get_or_404(library_movie.kinopoisk_id, description="Magnet-ссылка не найдена.")
    
    config = current_app.config
    try:
        qbt_client = Client(host=config['QBIT_HOST'], port=config['QBIT_PORT'], username=config['QBIT_USERNAME'], password=config['QBIT_PASSWORD'])
        qbt_client.auth_log_in()
        qbt_client.torrents_add(
            urls=identifier.magnet_link, category=f"library-{movie_id}",
            is_sequential_download=True, is_first_last_piece_priority=True,
            tags=f"kp-{library_movie.kinopoisk_id}",
        )
        qbt_client.auth_log_out()
        return jsonify({"success": True, "message": "Загрузка началась!"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка qBittorrent: {e}"}), 500

@api_bp.route('/delete-torrent/<string:torrent_hash>', methods=['POST'])
def delete_torrent_from_client(torrent_hash):
    if not torrent_hash:
        return jsonify({"success": False, "message": "Не указан хеш торрента"}), 400
    
    config = current_app.config
    try:
        qbt_client = Client(host=config['QBIT_HOST'], port=config['QBIT_PORT'], username=config['QBIT_USERNAME'], password=config['QBIT_PASSWORD'])
        qbt_client.auth_log_in()
        qbt_client.torrents_delete(delete_files=True, torrent_hashes=torrent_hash)
        qbt_client.auth_log_out()
        return jsonify({"success": True, "message": "Торрент и файлы удалены с клиента."})
    
    except qbittorrent_exceptions.NotFound404Error:
        return jsonify({"success": False, "message": "Торрент не найден в клиенте."}), 404
    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка qBittorrent: {e}"}), 500
        

# --- НОВЫЙ МАРШРУТ ДЛЯ ОПТИМИЗАЦИИ ---
@api_bp.route('/active-downloads')
def get_all_active_downloads():
    """Возвращает словарь всех активных торрентов для быстрой проверки на клиенте."""
    active_torrents = get_active_torrents_map()
    # Ключи (kp_id) должны быть строками для совместимости с JS dataset
    active_torrents_str_keys = {str(k): v for k, v in active_torrents.items()}
    return jsonify(active_torrents_str_keys)