#!/usr/bin/env python3
"""
Windows Toast Notification Client для Movie Lottery.

Подключается к WebSocket серверу и показывает Windows Toast уведомления
о новых голосах без необходимости держать браузер открытым.

Использование:
    python notification_client.py [--server URL]
    
Примеры:
    python notification_client.py
    python notification_client.py --server http://localhost:8888
"""

import argparse
import sys
import time
import threading
from pathlib import Path

try:
    import socketio
except ImportError:
    print("Ошибка: установите зависимости: pip install -r requirements.txt")
    sys.exit(1)

try:
    from win10toast_click import ToastNotifier
    HAS_TOAST = True
except ImportError:
    try:
        from win10toast import ToastNotifier
        HAS_TOAST = True
    except ImportError:
        HAS_TOAST = False
        print("Предупреждение: win10toast не установлен, уведомления будут в консоли")


class NotificationClient:
    """Клиент для получения уведомлений о голосах через WebSocket."""
    
    def __init__(self, server_url: str = "http://localhost:8888"):
        self.server_url = server_url
        self.sio = socketio.Client(
            reconnection=True,
            reconnection_delay=1,
            reconnection_delay_max=10,
            reconnection_attempts=0,  # Бесконечные попытки
            logger=False,
            engineio_logger=False,
        )
        self.running = False
        self.connected = False
        
        # Windows Toast
        if HAS_TOAST:
            self.toaster = ToastNotifier()
        else:
            self.toaster = None
        
        # Путь к иконке
        self.icon_path = self._find_icon()
        
        # Регистрируем обработчики событий
        self._register_handlers()
    
    def _find_icon(self) -> str | None:
        """Ищет иконку для уведомлений."""
        # Проверяем разные места
        possible_paths = [
            Path(__file__).parent / "icon.ico",
            Path(__file__).parent.parent / "movie_lottery" / "static" / "icons" / "icon.ico",
            Path(__file__).parent.parent / "movie_lottery" / "static" / "favicon.ico",
        ]
        for path in possible_paths:
            if path.exists():
                return str(path)
        return None
    
    def _register_handlers(self):
        """Регистрирует обработчики Socket.IO событий."""
        
        @self.sio.event
        def connect():
            self.connected = True
            print(f"[OK] Подключено к {self.server_url}")
            # Регистрируемся как admin клиент
            self.sio.emit('register_admin_client')
        
        @self.sio.event
        def disconnect():
            self.connected = False
            print("[!] Отключено от сервера, переподключение...")
        
        @self.sio.event
        def connect_error(data):
            print(f"[!] Ошибка подключения: {data}")
        
        @self.sio.on('connected')
        def on_connected(data):
            print(f"[OK] Сервер подтвердил подключение: {data}")
        
        @self.sio.on('admin_registered')
        def on_admin_registered(data):
            print(f"[OK] Зарегистрирован как admin клиент: {data}")
        
        @self.sio.on('vote_notification')
        def on_vote_notification(data):
            self._handle_vote_notification(data)
        
        @self.sio.on('admin_vote_notification')
        def on_admin_vote_notification(data):
            self._handle_vote_notification(data)
    
    def _handle_vote_notification(self, data: dict):
        """Обрабатывает уведомление о голосе."""
        title = data.get('title', 'Новый голос!')
        body = data.get('body', 'Кто-то проголосовал')
        poll_id = data.get('poll_id', '')
        
        print(f"\n{'='*50}")
        print(f"[ГОЛОС] {title}")
        print(f"        {body}")
        if poll_id:
            print(f"        Опрос: {poll_id}")
        print(f"{'='*50}\n")
        
        # Показываем Windows Toast
        self._show_toast(title, body, poll_id)
    
    def _show_toast(self, title: str, body: str, poll_id: str = ""):
        """Показывает Windows Toast уведомление."""
        if not self.toaster:
            return
        
        try:
            # Запускаем в отдельном потоке чтобы не блокировать
            def show():
                try:
                    # Функция при клике - открыть страницу опроса
                    url = f"{self.server_url}/p/{poll_id}/results" if poll_id else self.server_url
                    
                    # win10toast-click поддерживает callback
                    if hasattr(self.toaster, 'show_toast'):
                        self.toaster.show_toast(
                            title,
                            body,
                            icon_path=self.icon_path,
                            duration=5,
                            threaded=False,
                            callback_on_click=lambda: self._open_url(url)
                        )
                except Exception as e:
                    print(f"[!] Ошибка показа уведомления: {e}")
            
            threading.Thread(target=show, daemon=True).start()
        except Exception as e:
            print(f"[!] Ошибка Toast: {e}")
    
    def _open_url(self, url: str):
        """Открывает URL в браузере."""
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:
            pass
    
    def connect(self) -> bool:
        """Подключается к серверу."""
        try:
            print(f"[...] Подключение к {self.server_url}...")
            self.sio.connect(
                self.server_url,
                transports=['websocket', 'polling'],
                wait_timeout=10,
            )
            return True
        except Exception as e:
            print(f"[!] Не удалось подключиться: {e}")
            return False
    
    def run(self):
        """Запускает клиент в бесконечном цикле."""
        self.running = True
        print(f"""
╔══════════════════════════════════════════════════════════════╗
║     Movie Lottery - Клиент уведомлений о голосах             ║
╠══════════════════════════════════════════════════════════════╣
║  Сервер: {self.server_url:<52} ║
║  Toast:  {'Включён' if self.toaster else 'Отключён (только консоль)':<52} ║
╚══════════════════════════════════════════════════════════════╝
""")
        
        while self.running:
            if not self.connected:
                if self.connect():
                    pass  # Подключились
                else:
                    print("[...] Повторная попытка через 5 секунд...")
                    time.sleep(5)
                    continue
            
            try:
                # Ждём пока соединение активно
                self.sio.wait()
            except KeyboardInterrupt:
                print("\n[!] Остановка по Ctrl+C...")
                break
            except Exception as e:
                print(f"[!] Ошибка: {e}")
                time.sleep(1)
        
        self.stop()
    
    def stop(self):
        """Останавливает клиент."""
        self.running = False
        if self.connected:
            try:
                self.sio.disconnect()
            except Exception:
                pass
        print("[OK] Клиент остановлен")


def main():
    parser = argparse.ArgumentParser(
        description="Клиент Windows уведомлений для Movie Lottery"
    )
    parser.add_argument(
        "--server", "-s",
        default="http://localhost:8888",
        help="URL сервера (по умолчанию: http://localhost:8888)"
    )
    args = parser.parse_args()
    
    client = NotificationClient(server_url=args.server)
    
    try:
        client.run()
    except KeyboardInterrupt:
        client.stop()


if __name__ == "__main__":
    main()



