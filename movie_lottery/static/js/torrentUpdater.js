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
        const activeTorrents = this.getStoredTorrents();
        if (!activeTorrents) return;

        const galleryItems = document.querySelectorAll('.gallery-item[data-kinopoisk-id]');
        galleryItems.forEach(item => {
            const kpId = item.dataset.kinopoiskId;
            if (kpId && activeTorrents[kpId]) {
                item.classList.add('has-torrent-on-client');
                item.dataset.isOnClient = 'true';
                item.dataset.torrentHash = activeTorrents[kpId];
            } else {
                // Убираем индикатор, если торрента больше нет
                item.classList.remove('has-torrent-on-client');
                item.dataset.isOnClient = 'false';
                item.dataset.torrentHash = '';
            }
        });
    }
}

// Создаем глобальный экземпляр, который будет доступен на всех страницах
window.torrentUpdater = new TorrentUpdater();