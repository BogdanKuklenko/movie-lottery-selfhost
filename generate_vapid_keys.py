#!/usr/bin/env python3
"""
Скрипт для генерации VAPID ключей для push-уведомлений.

Запустите один раз для генерации ключей:
    python generate_vapid_keys.py

Затем добавьте сгенерированные ключи в ваш .env файл.
"""

try:
    from py_vapid import Vapid
except ImportError:
    print("Ошибка: py-vapid не установлен.")
    print("Установите его командой: pip install py-vapid")
    exit(1)


def generate_vapid_keys():
    """Генерирует пару VAPID ключей для push-уведомлений."""
    print("=" * 60)
    print("Генерация VAPID ключей для push-уведомлений")
    print("=" * 60)
    print()

    # Создаём новый экземпляр и генерируем ключи
    vapid = Vapid()
    vapid.generate_keys()

    # Получаем ключи в нужном формате
    from cryptography.hazmat.primitives import serialization

    # Приватный ключ в PEM формате
    private_pem = vapid.private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8').strip()

    # Публичный ключ в формате для браузера (uncompressed point)
    from py_vapid import b64urlencode
    public_raw = vapid.public_key.public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint
    )
    public_key_b64 = b64urlencode(public_raw)

    # Приватный ключ в формате для pywebpush
    private_raw = vapid.private_key.private_numbers().private_value.to_bytes(32, 'big')
    private_key_b64 = b64urlencode(private_raw)

    print("Добавьте следующие строки в ваш .env файл:")
    print()
    print("-" * 60)
    print(f"VAPID_PRIVATE_KEY={private_key_b64}")
    print(f"VAPID_PUBLIC_KEY={public_key_b64}")
    print("VAPID_CLAIMS_EMAIL=mailto:admin@example.com")
    print("VOTE_NOTIFICATIONS_ENABLED=true")
    print("-" * 60)
    print()
    print("ВАЖНО:")
    print("1. Замените admin@example.com на ваш реальный email")
    print("2. Сохраните VAPID_PRIVATE_KEY в безопасном месте")
    print("3. Эти ключи генерируются ОДИН раз и используются постоянно")
    print()
    print("=" * 60)


if __name__ == "__main__":
    generate_vapid_keys()










