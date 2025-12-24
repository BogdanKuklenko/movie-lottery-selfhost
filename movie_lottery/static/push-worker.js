// Service Worker для push-уведомлений о новых голосах в опросах
// movie_lottery/static/push-worker.js
// Renamed from sw.js to avoid ad-blocker false positives

const SW_VERSION = '1.0.0';

// Установка Service Worker
self.addEventListener('install', (event) => {
    console.log('[SW] Service Worker установлен, версия:', SW_VERSION);
    // Активируем сразу, не дожидаясь закрытия старых вкладок
    self.skipWaiting();
});

// Активация Service Worker
self.addEventListener('activate', (event) => {
    console.log('[SW] Service Worker активирован');
    // Захватываем все открытые вкладки
    event.waitUntil(clients.claim());
});

// Обработка входящих push-уведомлений
self.addEventListener('push', (event) => {
    console.log('[SW] Получено push-уведомление');

    // Данные по умолчанию
    let notificationData = {
        title: '🗳️ Новый голос в опросе!',
        body: 'Кто-то проголосовал',
        icon: '/static/icons/icon128.png',
        badge: '/static/icons/icon32.png',
        tag: 'vote-notification',
        data: {
            url: '/',
        },
    };

    // Парсим данные из push-сообщения
    try {
        if (event.data) {
            const payload = event.data.json();
            notificationData = {
                ...notificationData,
                ...payload,
            };
        }
    } catch (error) {
        console.error('[SW] Ошибка парсинга данных push:', error);
    }

    // Опции уведомления
    const options = {
        body: notificationData.body,
        icon: notificationData.icon,
        badge: notificationData.badge,
        tag: notificationData.tag,
        requireInteraction: true,
        renotify: true,  // Заменяет существующее уведомление с тем же tag
        vibrate: [200, 100, 200],
        data: notificationData.data,
        actions: [
            { action: 'open', title: 'Открыть' },
            { action: 'dismiss', title: 'Закрыть' },
        ],
    };

    // Показываем уведомление
    event.waitUntil(
        self.registration.showNotification(notificationData.title, options)
    );
});

// Обработка клика по уведомлению
self.addEventListener('notificationclick', (event) => {
    console.log('[SW] Клик по уведомлению, action:', event.action);

    // Закрываем уведомление
    event.notification.close();

    // Если пользователь нажал "Закрыть", ничего не делаем
    if (event.action === 'dismiss') {
        return;
    }

    // Определяем URL для открытия
    const targetUrl = event.notification.data?.url || '/';

    // Ищем открытую вкладку с этим опросом или открываем новую
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
            // Ищем вкладку с конкретным URL результатов
            for (const client of clientList) {
                if (client.url.includes(targetUrl) && 'focus' in client) {
                    return client.focus();
                }
            }

            // Если нет открытой вкладки — открываем новую
            if (clients.openWindow) {
                return clients.openWindow(targetUrl);
            }
        })
    );
});

// Обработка закрытия уведомления (свайп или таймаут)
self.addEventListener('notificationclose', (event) => {
    console.log('[SW] Уведомление закрыто');
});

// Обработка сообщений от WebSocket (для показа уведомлений через единый канал)
self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'SHOW_NOTIFICATION') {
        console.log('[SW] Получен запрос на показ уведомления от WebSocket');
        const data = event.data.payload;
        
        const options = {
            body: data.body,
            icon: data.icon || '/static/icons/icon128.png',
            badge: data.badge || '/static/icons/icon32.png',
            tag: data.tag || `vote-${data.poll_id}`,
            requireInteraction: true,
            renotify: true,  // Заменяет существующее уведомление с тем же tag
            vibrate: [200, 100, 200],
            data: data.data || {},
            actions: [
                { action: 'open', title: 'Открыть' },
                { action: 'dismiss', title: 'Закрыть' },
            ],
        };
        
        self.registration.showNotification(data.title || '🗳️ Новый голос!', options);
    }
});


