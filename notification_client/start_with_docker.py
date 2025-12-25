#!/usr/bin/env python3
"""
Скрипт автозапуска notification_client при старте Docker-контейнера.

Ожидает запуска контейнера movie_lottery_app и затем запускает клиент уведомлений.
Работает как демон — можно добавить в автозагрузку Windows.

Использование:
    pythonw start_with_docker.py    # Без окна консоли
    python start_with_docker.py     # С окном консоли (для отладки)
"""

import subprocess
import sys
import time
from pathlib import Path

# Настройки
CONTAINER_NAME = "movie_lottery_app"
SERVER_URL = "http://localhost:8888"
CHECK_INTERVAL = 5  # Секунд между проверками


def is_docker_running():
    """Проверяет, запущен ли Docker."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        return result.returncode == 0
    except Exception:
        return False


def is_container_running(container_name: str) -> bool:
    """Проверяет, запущен ли контейнер."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", container_name],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        return result.returncode == 0 and "true" in result.stdout.lower()
    except Exception:
        return False


def wait_for_server(url: str, timeout: int = 60) -> bool:
    """Ждёт пока сервер станет доступен."""
    import urllib.request
    import urllib.error
    
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(f"{url}/health", method="GET")
            with urllib.request.urlopen(req, timeout=5):
                return True
        except Exception:
            time.sleep(1)
    return False


def main():
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  Movie Lottery - Автозапуск клиента уведомлений              ║
╠══════════════════════════════════════════════════════════════╣
║  Контейнер: {CONTAINER_NAME:<49} ║
║  Сервер:    {SERVER_URL:<49} ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    # Путь к notification_client.py
    script_dir = Path(__file__).parent
    client_script = script_dir / "notification_client.py"
    
    if not client_script.exists():
        print(f"[!] Не найден {client_script}")
        sys.exit(1)
    
    client_process = None
    was_running = False
    
    print("[...] Ожидание Docker и контейнера...")
    
    try:
        while True:
            docker_ok = is_docker_running()
            container_ok = is_container_running(CONTAINER_NAME) if docker_ok else False
            
            if container_ok and not was_running:
                # Контейнер только что запустился
                print(f"[OK] Контейнер {CONTAINER_NAME} запущен")
                print("[...] Ожидание готовности сервера...")
                
                if wait_for_server(SERVER_URL):
                    print("[OK] Сервер доступен, запуск клиента уведомлений...")
                    
                    # Запускаем notification_client.py
                    client_process = subprocess.Popen(
                        [sys.executable, str(client_script), "--server", SERVER_URL],
                        cwd=str(script_dir),
                    )
                    print(f"[OK] Клиент запущен (PID: {client_process.pid})")
                else:
                    print("[!] Сервер не ответил, повтор через 10 сек...")
                    time.sleep(10)
                    continue
                
                was_running = True
                
            elif not container_ok and was_running:
                # Контейнер остановился
                print(f"[!] Контейнер {CONTAINER_NAME} остановлен")
                
                if client_process and client_process.poll() is None:
                    print("[...] Останавливаем клиент уведомлений...")
                    client_process.terminate()
                    try:
                        client_process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        client_process.kill()
                    print("[OK] Клиент остановлен")
                
                client_process = None
                was_running = False
                print("[...] Ожидание перезапуска контейнера...")
            
            elif container_ok and was_running:
                # Проверяем что клиент ещё работает
                if client_process and client_process.poll() is not None:
                    print("[!] Клиент завершился, перезапуск...")
                    client_process = subprocess.Popen(
                        [sys.executable, str(client_script), "--server", SERVER_URL],
                        cwd=str(script_dir),
                    )
                    print(f"[OK] Клиент перезапущен (PID: {client_process.pid})")
            
            time.sleep(CHECK_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n[!] Остановка...")
        if client_process and client_process.poll() is None:
            client_process.terminate()
        print("[OK] Готово")


if __name__ == "__main__":
    main()



