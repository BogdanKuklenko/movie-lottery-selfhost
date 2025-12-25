"""
Менеджер WebSocket соединений для push-уведомлений.
"""
import threading
from flask import current_app
from flask_socketio import emit
from .. import socketio

# Хранилище активных соединений: {voter_token: [session_id, ...]}
_websocket_connections = {}
_connection_lock = threading.Lock()

# Хранилище admin-клиентов для уведомлений (notification_client.py)
_admin_connections = set()
_admin_lock = threading.Lock()


def register_websocket_connection(voter_token, session_id):
    """Регистрирует WebSocket соединение для voter_token."""
    with _connection_lock:
        if voter_token not in _websocket_connections:
            _websocket_connections[voter_token] = []
        if session_id not in _websocket_connections[voter_token]:
            _websocket_connections[voter_token].append(session_id)
            current_app.logger.debug(f'[WebSocket] Зарегистрировано соединение для {voter_token[:8]}... (всего: {len(_websocket_connections[voter_token])})')


def unregister_websocket_connection(voter_token, session_id):
    """Удаляет WebSocket соединение."""
    with _connection_lock:
        if voter_token in _websocket_connections:
            if session_id in _websocket_connections[voter_token]:
                _websocket_connections[voter_token].remove(session_id)
                current_app.logger.debug(f'[WebSocket] Удалено соединение для {voter_token[:8]}...')
            if not _websocket_connections[voter_token]:
                del _websocket_connections[voter_token]


def has_active_websocket(voter_token):
    """Проверяет наличие активного WebSocket соединения для voter_token."""
    with _connection_lock:
        return voter_token in _websocket_connections and len(_websocket_connections[voter_token]) > 0


def send_websocket_notification(voter_token, notification_data):
    """
    Отправляет уведомление через WebSocket всем активным соединениям voter_token.
    
    Args:
        voter_token: Токен пользователя
        notification_data: dict с данными уведомления
        
    Returns:
        int: Количество успешно отправленных уведомлений
    """
    with _connection_lock:
        sessions = _websocket_connections.get(voter_token, [])
    
    if not sessions:
        return 0
    
    success_count = 0
    for session_id in sessions:
        try:
            socketio.emit('vote_notification', notification_data, room=session_id)
            success_count += 1
        except Exception as e:
            current_app.logger.warning(f'[WebSocket] Ошибка отправки на сессию {session_id[:8]}...: {e}')
            # Удаляем недействительное соединение
            unregister_websocket_connection(voter_token, session_id)
    
    if success_count > 0:
        current_app.logger.debug(f'[WebSocket] Отправлено {success_count} уведомлений для {voter_token[:8]}...')
    
    return success_count


def get_connection_count(voter_token=None):
    """Возвращает количество активных WebSocket соединений."""
    with _connection_lock:
        if voter_token:
            return len(_websocket_connections.get(voter_token, []))
        return sum(len(sessions) for sessions in _websocket_connections.values())


def get_all_voter_tokens():
    """Возвращает список всех voter_token с активными WebSocket соединениями."""
    with _connection_lock:
        return list(_websocket_connections.keys())


# ============================================================================
# Admin-клиенты (notification_client.py) - для уведомлений без браузера
# ============================================================================

def register_admin_connection(session_id):
    """Регистрирует admin-клиента для получения уведомлений о голосах."""
    with _admin_lock:
        _admin_connections.add(session_id)
        current_app.logger.info(f'[WebSocket] Admin-клиент зарегистрирован: {session_id[:8]}... (всего: {len(_admin_connections)})')


def unregister_admin_connection(session_id):
    """Удаляет admin-клиента."""
    with _admin_lock:
        _admin_connections.discard(session_id)
        current_app.logger.debug(f'[WebSocket] Admin-клиент отключен: {session_id[:8]}...')


def has_admin_connections():
    """Проверяет наличие активных admin-клиентов."""
    with _admin_lock:
        return len(_admin_connections) > 0


def get_admin_connection_count():
    """Возвращает количество активных admin-клиентов."""
    with _admin_lock:
        return len(_admin_connections)


def send_admin_notification(notification_data):
    """
    Отправляет уведомление всем admin-клиентам (notification_client.py).
    
    Args:
        notification_data: dict с данными уведомления
        
    Returns:
        int: Количество успешно отправленных уведомлений
    """
    with _admin_lock:
        sessions = list(_admin_connections)
    
    if not sessions:
        return 0
    
    success_count = 0
    failed_sessions = []
    
    for session_id in sessions:
        try:
            socketio.emit('admin_vote_notification', notification_data, room=session_id)
            success_count += 1
        except Exception as e:
            current_app.logger.warning(f'[WebSocket] Ошибка отправки admin уведомления на {session_id[:8]}...: {e}')
            failed_sessions.append(session_id)
    
    # Удаляем недействительные соединения
    if failed_sessions:
        with _admin_lock:
            for session_id in failed_sessions:
                _admin_connections.discard(session_id)
    
    if success_count > 0:
        current_app.logger.info(f'[WebSocket] Отправлено {success_count} admin уведомлений')
    
    return success_count

