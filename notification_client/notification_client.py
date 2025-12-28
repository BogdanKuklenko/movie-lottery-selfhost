#!/usr/bin/env python3
"""
Windows Toast Notification Client для Movie Lottery.

Подключается к WebSocket серверу и показывает Windows Toast уведомления
о новых голосах без необходимости держать браузер открытым.

Особенности:
- Уведомления поверх всех окон (persistent)
- Уведомления остаются пока пользователь не закроет
- Пробуждение экрана при неактивности
- Кнопки: "Открыть результаты" и "RuTracker" (поиск лидера)

Использование:
    python notification_client.py [--server URL]
    
Примеры:
    python notification_client.py
    python notification_client.py --server http://localhost:8888
"""

import argparse
import ctypes
import sys
import time
import threading
import webbrowser
import urllib.parse
from pathlib import Path
from typing import Optional

try:
    import socketio
except ImportError:
    print("Ошибка: установите зависимости: pip install -r requirements.txt")
    sys.exit(1)

# Windows Toast с поддержкой кнопок и persistent режима
HAS_TOAST = False
Toast = None
InteractableWindowsToaster = None
ToastButton = None
ToastDisplayImage = None
ToastDuration = None
ToastScenario = None
ToastActivatedEventArgs = None

try:
    from windows_toasts import (
        Toast,
        InteractableWindowsToaster,
        ToastButton,
        ToastDisplayImage,
        ToastDuration,
        ToastScenario,
        ToastActivatedEventArgs,
        ToastImagePosition,
    )
    HAS_TOAST = True
except ImportError:
    print("Предупреждение: windows-toasts не установлен, уведомления будут в консоли")
    print("Установите: pip install windows-toasts")
    ToastImagePosition = None

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    print("Предупреждение: requests не установлен, постеры в уведомлениях недоступны")
    HAS_REQUESTS = False


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
        
        # Windows Toast - используем InteractableWindowsToaster для поддержки callbacks
        if HAS_TOAST:
            try:
                self.toaster = InteractableWindowsToaster('Movie Lottery')
            except Exception as e:
                print(f"[!] Ошибка инициализации WindowsToaster: {e}")
                self.toaster = None
        else:
            self.toaster = None
        
        # Путь к иконке
        self.icon_path = self._find_icon()
        
        # Путь к файлу постера (один файл, перезаписывается)
        self.poster_path = Path(__file__).parent / "current_poster.jpg"
        
        # Регистрируем обработчики событий
        self._register_handlers()
    
    def _find_icon(self) -> Optional[str]:
        """Ищет иконку для уведомлений."""
        possible_paths = [
            Path(__file__).parent / "icon.ico",
            Path(__file__).parent / "icon.png",
            Path(__file__).parent.parent / "movie_lottery" / "static" / "icons" / "icon128.png",
            Path(__file__).parent.parent / "movie_lottery" / "static" / "icons" / "icon.ico",
        ]
        for path in possible_paths:
            if path.exists():
                return str(path)
        return None
    
    def _save_poster(self, poster_url: str) -> Optional[str]:
        """Скачивает постер и перезаписывает current_poster.jpg."""
        if not poster_url or not HAS_REQUESTS:
            return None
        try:
            # Добавляем базовый URL сервера для относительных путей
            if poster_url.startswith('/'):
                poster_url = f"{self.server_url}{poster_url}"
            response = requests.get(poster_url, timeout=5)
            if response.status_code == 200:
                self.poster_path.write_bytes(response.content)
                return str(self.poster_path)
        except Exception as e:
            print(f"[!] Ошибка загрузки постера: {e}")
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
        leader = data.get('leader')
        
        print(f"\n{'='*50}")
        print(f"[ГОЛОС] {title}")
        print(f"        {body}")
        if poll_id:
            print(f"        Опрос: {poll_id}")
        if leader:
            print(f"        Лидер: {leader.get('name', 'N/A')} ({leader.get('votes', 0)} голосов)")
        print(f"{'='*50}\n")
        
        # Пробуждаем экран
        self._wake_display()
        
        # Показываем Windows Toast
        self._show_toast(title, body, poll_id, leader)
    
    def _wake_display(self):
        """Пробуждает монитор и предотвращает засыпание."""
        try:
            # Константы для SetThreadExecutionState
            ES_CONTINUOUS = 0x80000000
            ES_SYSTEM_REQUIRED = 0x00000001
            ES_DISPLAY_REQUIRED = 0x00000002
            
            # Включаем дисплей и предотвращаем засыпание
            ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
            )
            
            # Симулируем микро-движение мыши для пробуждения экрана
            # MOUSEEVENTF_MOVE = 0x0001
            ctypes.windll.user32.mouse_event(0x0001, 1, 1, 0, 0)
            time.sleep(0.05)
            ctypes.windll.user32.mouse_event(0x0001, -1, -1, 0, 0)
            
            # Также отправляем WM_SYSCOMMAND для включения монитора
            # SC_MONITORPOWER = 0xF170, параметр -1 = включить
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if hwnd:
                ctypes.windll.user32.SendMessageW(hwnd, 0x0112, 0xF170, -1)
            
            print("[OK] Экран пробужден")
        except Exception as e:
            print(f"[!] Ошибка пробуждения экрана: {e}")
    
    def _build_rutracker_url(self, leader: dict) -> str:
        """Формирует URL для поиска фильма на RuTracker."""
        countries = (leader.get('countries') or '').lower()
        is_russian = 'россия' in countries or 'ссср' in countries
        
        name = leader.get('name', '')
        search_name = leader.get('search_name') or name
        year = leader.get('year', '')
        
        # Для русского контента - русское название, для иностранного - английское
        search_base = name if is_russian else search_name
        query = f"{search_base} {year}".strip() if year else search_base
        
        return f"https://rutracker.net/forum/tracker.php?nm={urllib.parse.quote(query)}"
    
    def _show_toast(self, title: str, body: str, poll_id: str = "", leader: Optional[dict] = None):
        """Показывает Windows Toast уведомление с кнопками."""
        if not self.toaster:
            # Fallback: просто логируем в консоль
            return
        
        try:
            # Создаём Toast
            toast = Toast()
            
            # Добавляем текст (до 3 строк)
            text_lines = [title, body]
            if leader:
                leader_info = f"Лидер: {leader.get('name', 'N/A')} ({leader.get('votes', 0)} голосов)"
                text_lines.append(leader_info)
            toast.text_fields = text_lines
            
            # Устанавливаем сценарий - IncomingCall делает уведомление persistent
            # и отображает его поверх всех окон
            toast.scenario = ToastScenario.IncomingCall
            
            # Устанавливаем длительность Long для максимального времени показа
            toast.duration = ToastDuration.Long
            
            # Добавляем изображение: постер лидера или иконку приложения
            image_added = False
            if leader and leader.get('poster'):
                poster_file = self._save_poster(leader['poster'])
                if poster_file:
                    try:
                        toast.AddImage(ToastDisplayImage.fromPath(poster_file))
                        image_added = True
                    except Exception as e:
                        print(f"[!] Ошибка добавления постера: {e}")
            
            # Если постера нет - используем иконку приложения
            if not image_added and self.icon_path:
                try:
                    toast.AddImage(ToastDisplayImage.fromPath(self.icon_path))
                except Exception as e:
                    print(f"[!] Ошибка добавления иконки: {e}")
            
            # URL для открытия результатов
            results_url = f"{self.server_url}/p/{poll_id}/results" if poll_id else self.server_url
            
            # Кнопка "Открыть результаты" - launch открывает URL при клике
            open_button = ToastButton(content='Открыть', launch=results_url)
            toast.AddAction(open_button)
            
            # Кнопка "RuTracker" если есть данные о лидере
            if leader and leader.get('name'):
                rutracker_url = self._build_rutracker_url(leader)
                rutracker_button = ToastButton(content='RuTracker', launch=rutracker_url)
                toast.AddAction(rutracker_button)
            
            # Показываем уведомление
            # Запускаем в отдельном потоке чтобы не блокировать основной цикл
            def show_toast_thread():
                try:
                    self.toaster.show_toast(toast)
                except Exception as e:
                    print(f"[!] Ошибка показа Toast: {e}")
            
            threading.Thread(target=show_toast_thread, daemon=True).start()
            
        except Exception as e:
            print(f"[!] Ошибка создания Toast: {e}")
    
    def _open_url(self, url: str):
        """Открывает URL в браузере."""
        try:
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
║  Toast:  {'Включён (persistent + кнопки)' if self.toaster else 'Отключён (только консоль)':<52} ║
║  Экран:  Пробуждение при уведомлении                         ║
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
        
        # Сбрасываем состояние предотвращения засыпания
        try:
            ES_CONTINUOUS = 0x80000000
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
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
