// Модуль для работы с push-уведомлениями о новых голосах
// movie_lottery/static/js/utils/pushNotifications.js

import { buildPollApiUrl } from './polls.js';

// Socket.IO клиент - используем глобальный объект io, если доступен
// Ожидается, что Socket.IO подключен через CDN в HTML шаблоне
let io = null;
if (typeof window !== 'undefined' && window.io) {
    io = window.io;
}

const SW_PATH = '/push-worker.js';

/**
 * Менеджер push-уведомлений
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
        this.globallyEnabled = true;
        this.websocketEnabled = false;
        this.socket = null;
        this.websocketSupported = io !== null;
    }

    /**
     * Инициализация менеджера
     * @returns {Promise<boolean>} Успешность инициализации
     */
    async init() {
        if (this.isInitialized) {
            return this.isSupported;
        }

        if (!this.isSupported) {
            console.warn('[Push] Браузер не поддерживает push-уведомления');
            this.isInitialized = true;
            return false;
        }

        try {
            // Регистрируем Service Worker
            this.registration = await navigator.serviceWorker.register(SW_PATH, {
                scope: '/',
            });
            console.log('[Push] Service Worker зарегистрирован');

            // Ждём активации
            await navigator.serviceWorker.ready;

            // Получаем VAPID ключ с сервера
            await this.fetchVapidKey();

            if (!this.vapidPublicKey) {
                console.warn('[Push] VAPID ключ не получен, push-уведомления недоступны');
                this.isInitialized = true;
                return false;
            }

            // Проверяем текущую подписку
            this.subscription = await this.registration.pushManager.getSubscription();

            // Синхронизируем с сервером
            await this.syncWithServer();

            // Инициализируем WebSocket если включен
            await this.initWebSocket();

            this.isInitialized = true;
            return true;
        } catch (error) {
            console.error('[Push] Ошибка инициализации:', error);
            this.isInitialized = true;
            return false;
        }
    }

    /**
     * Получить VAPID ключ с сервера
     */
    async fetchVapidKey() {
        try {
            const response = await fetch(buildPollApiUrl('/api/polls/push/vapid-key'), {
                credentials: 'include',
            });

            if (response.ok) {
                const data = await response.json();
                this.vapidPublicKey = data.vapid_public_key;
                this.globallyEnabled = data.enabled !== false;
            } else {
                console.warn('[Push] Не удалось получить VAPID ключ:', response.status);
            }
        } catch (error) {
            console.error('[Push] Ошибка получения VAPID ключа:', error);
        }
    }

    /**
     * Синхронизация с сервером
     */
    async syncWithServer() {
        try {
            const response = await fetch(buildPollApiUrl('/api/polls/notifications/settings'), {
                credentials: 'include',
            });

            if (response.ok) {
                const data = await response.json();
                // isEnabled = есть подписка в браузере И есть подписка на сервере
                this.isEnabled = !!this.subscription && data.has_push_subscription;
                this.globallyEnabled = data.globally_enabled !== false;
                // Обновляем статус WebSocket если доступен
                if (data.has_websocket_connection !== undefined) {
                    this.websocketEnabled = data.has_websocket_connection;
                }
            }
        } catch (error) {
            console.error('[Push] Ошибка синхронизации:', error);
        }
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
     * Подписаться на push-уведомления
     * @returns {Promise<boolean>} Успешность подписки
     */
    async subscribe() {
        if (this.isLoading) {
            return false;
        }

        if (!this.isSupported || !this.vapidPublicKey || !this.registration) {
            console.warn('[Push] Подписка невозможна: не инициализирован');
            return false;
        }

        this.isLoading = true;

        try {
            // Запрашиваем разрешение на уведомления
            const permission = await Notification.requestPermission();

            if (permission !== 'granted') {
                console.warn('[Push] Разрешение на уведомления не получено:', permission);
                this.isLoading = false;
                return false;
            }

            // Подписываемся на push
            this.subscription = await this.registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: this.urlBase64ToUint8Array(this.vapidPublicKey),
            });

            console.log('[Push] Подписка создана');

            // Отправляем подписку на сервер
            const response = await fetch(buildPollApiUrl('/api/polls/push/subscribe'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ subscription: this.subscription.toJSON() }),
            });

            if (response.ok) {
                const data = await response.json();
                this.isEnabled = data.subscribed || data.success;
                console.log('[Push] Подписка сохранена на сервере');
                this.isLoading = false;
                return true;
            } else {
                console.error('[Push] Ошибка сохранения подписки на сервере');
                // Отменяем подписку в браузере
                await this.subscription.unsubscribe();
                this.subscription = null;
                this.isLoading = false;
                return false;
            }
        } catch (error) {
            console.error('[Push] Ошибка подписки:', error);
            this.isLoading = false;
            return false;
        }
    }

    /**
     * Отписаться от push-уведомлений
     * @returns {Promise<boolean>} Успешность отписки
     */
    async unsubscribe() {
        if (this.isLoading) {
            return false;
        }

        this.isLoading = true;

        try {
            // Отписываемся в браузере
            if (this.subscription) {
                await this.subscription.unsubscribe();
                this.subscription = null;
            }

            // Уведомляем сервер
            const response = await fetch(buildPollApiUrl('/api/polls/push/unsubscribe'), {
                method: 'POST',
                credentials: 'include',
            });

            if (response.ok) {
                this.isEnabled = false;
                console.log('[Push] Отписка успешна');
            }

            this.isLoading = false;
            return true;
        } catch (error) {
            console.error('[Push] Ошибка отписки:', error);
            this.isLoading = false;
            return false;
        }
    }

    /**
     * Переключить состояние подписки
     * @returns {Promise<boolean>} Успешность операции
     */
    async toggle() {
        if (this.isEnabled) {
            return await this.unsubscribe();
        } else {
            return await this.subscribe();
        }
    }

    /**
     * Проверить, доступны ли push-уведомления
     * @returns {boolean}
     */
    isAvailable() {
        return this.isSupported && this.globallyEnabled && !!this.vapidPublicKey;
    }

    /**
     * Инициализация WebSocket соединения
     */
    async initWebSocket() {
        if (!this.websocketSupported) {
            console.log('[WebSocket] Socket.IO не доступен');
            return;
        }

        try {
            const baseUrl = window.location.origin;
            this.socket = io(baseUrl, {
                transports: ['websocket', 'polling'],
                reconnection: true,
                reconnectionDelay: 1000,
                reconnectionAttempts: 5,
                reconnectionDelayMax: 5000,
            });

            this.socket.on('connect', () => {
                console.log('[WebSocket] Подключено');
                this.websocketEnabled = true;
            });

            this.socket.on('disconnect', () => {
                console.log('[WebSocket] Отключено');
                this.websocketEnabled = false;
            });

            this.socket.on('vote_notification', (data) => {
                console.log('[WebSocket] Получено уведомление о голосе:', data);
                // Показываем уведомление через браузерный API
                this.showBrowserNotification(data);
            });

            this.socket.on('connected', (data) => {
                console.log('[WebSocket] Соединение подтверждено:', data);
            });

            this.socket.on('connect_error', (error) => {
                console.error('[WebSocket] Ошибка подключения:', error);
                this.websocketEnabled = false;
            });
        } catch (error) {
            console.error('[WebSocket] Ошибка инициализации:', error);
        }
    }

    /**
     * Показать браузерное уведомление (используется для WebSocket)
     * Отправляет данные в Service Worker для унифицированного показа
     */
    async showBrowserNotification(data) {
        // Отправляем в Service Worker для показа (гарантирует дедупликацию и единообразное поведение)
        try {
            if (this.registration) {
                // Ждём готовности SW если он ещё не активен
                const registration = await navigator.serviceWorker.ready;
                if (registration.active) {
                    registration.active.postMessage({
                        type: 'SHOW_NOTIFICATION',
                        payload: data
                    });
                }
            }
        } catch (error) {
            console.error('[Push] Ошибка отправки уведомления в Service Worker:', error);
        }
    }

    /**
     * Отключить WebSocket
     */
    disconnectWebSocket() {
        if (this.socket) {
            this.socket.disconnect();
            this.socket = null;
            this.websocketEnabled = false;
        }
    }
}

export default PushNotificationManager;

