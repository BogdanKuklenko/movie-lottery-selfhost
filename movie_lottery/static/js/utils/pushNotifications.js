// Модуль для работы с push-уведомлениями о новых голосах
// movie_lottery/static/js/utils/pushNotifications.js
//
// ПРИМЕЧАНИЕ: Браузерные уведомления отключены.
// Уведомления доставляются через notification_client.py (Windows Toast).
// Этот модуль сохранен для совместимости API, но не показывает уведомления.

import { buildPollApiUrl } from './polls.js';

const SW_PATH = '/push-worker.js';

/**
 * Менеджер push-уведомлений (заглушка)
 * 
 * Браузерные push-уведомления отключены, т.к. используется
 * единый канал доставки через notification_client.py (Windows Toast).
 * 
 * Этот класс сохранен для обратной совместимости, но не показывает уведомления.
 */
class PushNotificationManager {
    constructor() {
        this.isSupported = 'serviceWorker' in navigator && 'PushManager' in window;
        this.registration = null;
        this.subscription = null;
        this.isEnabled = false;
        this.vapidPublicKey = null;
        this.isLoading = false;
        this.isInitialized = false;
        this.globallyEnabled = false; // Отключено - используем notification_client.py
        this.websocketEnabled = false;
        this.socket = null;
        this.websocketSupported = false; // Отключено
    }

    /**
     * Инициализация менеджера
     * @returns {Promise<boolean>} Успешность инициализации
     */
    async init() {
        if (this.isInitialized) {
            return this.isSupported;
        }

        // Браузерные уведомления отключены
        // Уведомления доставляются через notification_client.py
        console.log('[Push] Браузерные уведомления отключены. Используйте notification_client.py');
        
        this.isInitialized = true;
        this.globallyEnabled = false;
        
        return false;
    }

    /**
     * Получить VAPID ключ с сервера (заглушка)
     */
    async fetchVapidKey() {
        // Отключено
        this.vapidPublicKey = null;
        this.globallyEnabled = false;
    }

    /**
     * Синхронизация с сервером (заглушка)
     */
    async syncWithServer() {
        // Отключено
        this.isEnabled = false;
        this.globallyEnabled = false;
    }

    /**
     * Конвертация base64 в Uint8Array для VAPID ключа
     * @param {string} base64String - Base64 строка
     * @returns {Uint8Array}
     */
    urlBase64ToUint8Array(base64String) {
        const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
        const base64 = (base64String + padding)
            .replace(/-/g, '+')
            .replace(/_/g, '/');
        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);
        for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
    }

    /**
     * Проверка разрешения на уведомления
     * @returns {string} 'granted', 'denied', или 'default'
     */
    getNotificationPermission() {
        if (!('Notification' in window)) {
            return 'unsupported';
        }
        return Notification.permission;
    }

    /**
     * Подписаться на push-уведомления (заглушка)
     * @returns {Promise<boolean>} Всегда false - отключено
     */
    async subscribe() {
        console.log('[Push] Браузерные push-уведомления отключены');
        return false;
    }

    /**
     * Отписаться от push-уведомлений (заглушка)
     * @returns {Promise<boolean>} Всегда true
     */
    async unsubscribe() {
        this.isEnabled = false;
        return true;
    }

    /**
     * Переключить состояние подписки (заглушка)
     * @returns {Promise<boolean>} Всегда false
     */
    async toggle() {
        console.log('[Push] Браузерные push-уведомления отключены');
        return false;
    }

    /**
     * Проверить, доступны ли push-уведомления
     * @returns {boolean} Всегда false - отключено
     */
    isAvailable() {
        return false; // Отключено
    }

    /**
     * Инициализация WebSocket соединения (отключено)
     */
    async initWebSocket() {
        // WebSocket уведомления отключены
        // Используется notification_client.py для Windows Toast
        console.log('[WebSocket] Браузерные WebSocket уведомления отключены');
        this.websocketEnabled = false;
    }

    /**
     * Показать браузерное уведомление (отключено)
     */
    async showBrowserNotification(data) {
        // Отключено - уведомления через notification_client.py
        console.log('[Push] Браузерные уведомления отключены:', data);
    }

    /**
     * Отключить WebSocket (заглушка)
     */
    disconnectWebSocket() {
        if (this.socket) {
            this.socket.disconnect();
            this.socket = null;
        }
        this.websocketEnabled = false;
    }
}

export default PushNotificationManager;
