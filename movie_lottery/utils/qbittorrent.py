# F:\GPT\movie-lottery V2\movie_lottery\utils\qbittorrent.py
import requests
from flask import current_app
from qbittorrentapi import Client, exceptions as qbittorrent_exceptions

def get_active_torrents_map():
    """
    Подключается к qBittorrent, получает все торренты и возвращает словарь,
    где ключ - kinopoisk_id (из тега), а значение - хеш торрента.
    """
    config = current_app.config
    qbt_client = None
    active_torrents = {}

    try:
        qbt_client = Client(
            host=config['QBIT_HOST'],
            port=config['QBIT_PORT'],
            username=config['QBIT_USERNAME'],
            password=config['QBIT_PASSWORD']
        )
        qbt_client.auth_log_in()
        
        torrents = qbt_client.torrents_info()
        for torrent in torrents:
            tags = torrent.tags.split(',')
            for tag in tags:
                tag = tag.strip()
                if tag.startswith('kp-'):
                    try:
                        kp_id = int(tag.replace('kp-', ''))
                        active_torrents[kp_id] = torrent.hash
                        break 
                    except (ValueError, TypeError):
                        continue
    
    except (qbittorrent_exceptions.APIConnectionError, requests.exceptions.RequestException) as e:
        print(f"Ошибка подключения к qBittorrent: {e}")
        return {}
    except Exception as e:
        print(f"Неизвестная ошибка при работе с qBittorrent: {e}")
        return {}
    finally:
        if qbt_client and qbt_client.is_logged_in:
            try:
                qbt_client.auth_log_out()
            except Exception:
                pass
                
    return active_torrents