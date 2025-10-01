# F:\GPT\movie-lottery V2\movie_lottery\utils\helpers.py
import random
import string
from sqlalchemy.exc import ProgrammingError
from .. import db
from ..models import BackgroundPhoto, Lottery

def generate_unique_id(length=6):
    """Генерирует уникальный ID для лотереи."""
    while True:
        lottery_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
        if not Lottery.query.get(lottery_id):
            return lottery_id

def get_background_photos():
    """Получает последние 20 фоновых изображений из базы данных."""
    try:
        photos = BackgroundPhoto.query.order_by(BackgroundPhoto.added_at.desc()).limit(20).all()
        return [
            {
                "poster_url": photo.poster_url,
                "pos_top": photo.pos_top,
                "pos_left": photo.pos_left,
                "rotation": photo.rotation,
                "z_index": photo.z_index,
            }
            for photo in photos
        ]
    except (ProgrammingError, Exception) as e:
        # Это может случиться, если база данных еще не создана или недоступна
        # Возвращаем пустой список вместо падения
        return []

def ensure_background_photo(poster_url):
    """
    Добавляет URL постера в базу данных фоновых изображений, если его там еще нет.
    """
    if not poster_url:
        return

    try:
        # Проверяем, существует ли уже такая запись
        if BackgroundPhoto.query.filter_by(poster_url=poster_url).first():
            return

        # Находим максимальный z-index, чтобы новое фото было поверх старых
        max_z_index = db.session.query(db.func.max(BackgroundPhoto.z_index)).scalar() or 0
        
        new_photo = BackgroundPhoto(
            poster_url=poster_url,
            pos_top=random.uniform(5, 65),
            pos_left=random.uniform(5, 75),
            rotation=random.randint(-30, 30),
            z_index=max_z_index + 1,
        )
        db.session.add(new_photo)
    except Exception:
        # Если БД недоступна или таблица не создана, просто пропускаем
        pass