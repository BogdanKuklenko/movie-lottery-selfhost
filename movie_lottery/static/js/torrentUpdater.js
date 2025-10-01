// F:\GPT\movie-lottery V2\movie_lottery\static\js\torrentUpdater.js

class TorrentUpdater {
    constructor(storageKey = 'activeTorrents') {
        this.storageKey = storageKey;
        this.statusKey = storageKey + '_qbitStatus';
        this.updateInProgress = false;
        
        // Адаптивные интервалы опроса (в миллисекундах)
        this.INTERVALS = {
            FAST: 5000,      // 5 сек - qBittorrent доступен
            MEDIUM: 15000,   // 15 сек - qBittorrent восстанавливается
            SLOW: 60000,     // 60 сек - qBittorrent недоступен
            VERY_SLOW: 120000 // 2 мин - долгое недоступность
        };
        
        this.currentInterval = this.INTERVALS.FAST;
        this.failureCount = 0;
        this.pollTimeoutId = null;
        
        // Запускаем обновление сразу при создании объекта
        this.startPolling();
    }

    /**
     * Запускает непрерывный опрос с адаптивными интервалами
     */
    startPolling() {
        this.fetchAndStoreTorrents();
    }

    /**
     * Останавливает опрос
     */
    stopPolling() {
        if (this.pollTimeoutId) {
            clearTimeout(this.pollTimeoutId);
            this.pollTimeoutId = null;
        }
    }

    /**
     * Планирует следующее обновление
     */
    scheduleNextUpdate() {
        this.stopPolling();
        this.pollTimeoutId = setTimeout(() => {
            this.fetchAndStoreTorrents();
        }, this.currentInterval);
        
        console.log(`[TorrentUpdater] Следующее обновление через ${this.currentInterval / 1000} сек`);
    }

    /**
     * Определяет интервал опроса на основе статуса qBittorrent
     */
    determineInterval(qbitStatus) {
        if (!qbitStatus) {
            // Нет информации о статусе - используем средний интервал
            return this.INTERVALS.MEDIUM;
        }

        if (qbitStatus.available) {
            if (qbitStatus.state === 'half_open') {
                // Восстановление - средний интервал
                return this.INTERVALS.MEDIUM;
            } else {
                // Нормальная работа - быстрый опрос
                return this.INTERVALS.FAST;
            }
        } else {
            // qBittorrent недоступен
            if (this.failureCount > 3) {
                // Долгая недоступность - очень редкий опрос
                return this.INTERVALS.VERY_SLOW;
            } else {
                // Первые неудачи - редкий опрос
                return this.INTERVALS.SLOW;
            }
        }
    }

    /**
     * Запрашивает статус qBittorrent
     */
    async fetchQBittorrentStatus() {
        try {
            const response = await fetch('/api/qbittorrent-status');
            if (!response.ok) throw new Error('Failed to fetch qBittorrent status');
            return await response.json();
        } catch (error) {
            console.error('[TorrentUpdater] Ошибка получения статуса qBittorrent:', error);
            return null;
        }
    }

    /**
     * Запрашивает с сервера список активных торрентов и сохраняет его в sessionStorage.
     */
    async fetchAndStoreTorrents() {
        if (this.updateInProgress) {
            this.scheduleNextUpdate();
            return;
        }
        
        this.updateInProgress = true;
        
        try {
            // Параллельно запрашиваем торренты и статус
            const [torrentsResponse, qbitStatus] = await Promise.all([
                fetch('/api/active-downloads'),
                this.fetchQBittorrentStatus()
            ]);
            
            if (!torrentsResponse.ok) {
                throw new Error('Network response was not ok');
            }
            
            const data = await torrentsResponse.json();
            const qbitAvailable = data.qbittorrent_available ?? false;
            
            // Сохраняем данные
            sessionStorage.setItem(this.storageKey, JSON.stringify(data));
            
            if (qbitStatus) {
                sessionStorage.setItem(this.statusKey, JSON.stringify(qbitStatus));
            }
            
            // Обновляем интервал на основе статуса
            const newInterval = this.determineInterval(qbitStatus);
            
            if (qbitAvailable) {
                // Сброс счетчика ошибок при успехе
                if (this.failureCount > 0) {
                    console.log('[TorrentUpdater] ✅ qBittorrent восстановлен!');
                }
                this.failureCount = 0;
            } else {
                this.failureCount++;
                console.warn(`[TorrentUpdater] ⚠️ qBittorrent недоступен (попытка ${this.failureCount})`);
            }
            
            // Обновляем интервал только если он изменился
            if (newInterval !== this.currentInterval) {
                const oldInterval = this.currentInterval;
                this.currentInterval = newInterval;
                console.log(
                    `[TorrentUpdater] Переключение интервала: ${oldInterval / 1000}с → ${newInterval / 1000}с`
                );
            }
            
        } catch (error) {
            console.error('[TorrentUpdater] Ошибка обновления:', error);
            this.failureCount++;
            
            // При ошибке переключаемся на редкий опрос
            if (this.currentInterval < this.INTERVALS.SLOW) {
                this.currentInterval = this.INTERVALS.SLOW;
                console.log('[TorrentUpdater] Переключение на редкий опрос из-за ошибки');
            }
            
            // В случае ошибки очищаем старые данные
            sessionStorage.removeItem(this.storageKey);
        } finally {
            this.updateInProgress = false;
            this.scheduleNextUpdate();
        }
    }

    /**
     * Получает сохраненные данные из sessionStorage.
     * @returns {object|null}
     */
    getStoredTorrents() {
        try {
            return JSON.parse(sessionStorage.getItem(this.storageKey));
        } catch (error) {
            return null;
        }
    }

    /**
     * Получает статус qBittorrent из sessionStorage.
     * @returns {object|null}
     */
    getQBittorrentStatus() {
        try {
            return JSON.parse(sessionStorage.getItem(this.statusKey));
        } catch (error) {
            return null;
        }
    }

    /**
     * Возвращает текущий статус для отладки
     */
    getDebugInfo() {
        const status = this.getQBittorrentStatus();
        return {
            currentInterval: this.currentInterval / 1000 + ' сек',
            failureCount: this.failureCount,
            qbitStatus: status,
            isPolling: !!this.pollTimeoutId
        };
    }

    /**
     * Обновляет UI на текущей странице, добавляя индикаторы к нужным карточкам.
     */
    updateUi() {
        const storedPayload = this.getStoredTorrents();
        if (!storedPayload || typeof storedPayload !== 'object') return;

        const kpMap = (storedPayload && typeof storedPayload.kp === 'object' && storedPayload.kp !== null)
            ? storedPayload.kp
            : storedPayload;

        if (!kpMap || typeof kpMap !== 'object') return;

        const resolveTorrentInfo = (value) => {
            if (!value) return { hash: '' };
            if (typeof value === 'object') {
                const hash = typeof value.hash === 'string' ? value.hash : '';
                const state = typeof value.state === 'string' ? value.state : '';
                const progressValue = typeof value.progress === 'number'
                    ? value.progress
                    : parseFloat(value.progress ?? '0') || 0;
                return { hash, state, progress: progressValue };
            }
            if (typeof value === 'string') {
                return { hash: value, state: '', progress: 0 };
            }
            return { hash: '' };
        };

        const galleryItems = document.querySelectorAll('.gallery-item[data-kinopoisk-id]');
        galleryItems.forEach(item => {
            const kpId = item.dataset.kinopoiskId;
            if (!kpId) return;

            const info = resolveTorrentInfo(kpMap[kpId]);
            if (info.hash) {
                item.classList.add('has-torrent-on-client');
                item.dataset.isOnClient = 'true';
                item.dataset.torrentHash = info.hash;
            } else {
                item.classList.remove('has-torrent-on-client');
                item.dataset.isOnClient = 'false';
                item.dataset.torrentHash = '';
            }
        });
    }
}

// Создаем глобальный экземпляр, который будет доступен на всех страницах
window.torrentUpdater = new TorrentUpdater();