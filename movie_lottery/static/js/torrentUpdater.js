// F:\GPT\movie-lottery V2\movie_lottery\static\js\torrentUpdater.js

class TorrentUpdater {
    constructor(storageKey = 'activeTorrents') {
        this.storageKey = storageKey;
        this.updateInProgress = false;
        // Запускаем обновление сразу при создании объекта
        this.fetchAndStoreTorrents();
    }

    /**
     * Запрашивает с сервера список активных торрентов и сохраняет его в sessionStorage.
     */
    async fetchAndStoreTorrents() {
        if (this.updateInProgress) return;
        this.updateInProgress = true;
        
        try {
            const response = await fetch('/api/active-downloads');
            if (!response.ok) throw new Error('Network response was not ok');
            const data = await response.json();
            sessionStorage.setItem(this.storageKey, JSON.stringify(data));
        } catch (error) {
            console.error('Failed to fetch active torrents:', error);
            // В случае ошибки очищаем старые данные, чтобы не показывать неверный статус
            sessionStorage.removeItem(this.storageKey);
        } finally {
            this.updateInProgress = false;
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