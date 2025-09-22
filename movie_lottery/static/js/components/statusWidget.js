// F:\GPT\movie-lottery V2\movie_lottery\static\js\components\statusWidget.js

import { fetchActiveDownloads, getDownloadStatusByKpId, getTorrentStatusForLibrary, getTorrentStatusForLottery } from '../api/torrents.js';

// --- Вспомогательные функции ---

function getDownloadKey(id, type) {
    if (type === 'kinopoisk' && id) return `kp-${id}`;
    if (type === 'lottery' && id) return `lottery-${id}`;
    if (type === 'library' && id) return `lib-${id}`;
    return null;
}

function safeJsonParse(value) {
    try {
        return JSON.parse(value);
    } catch (error) {
        return null;
    }
}

// --- Класс для управления виджетом ---

export class StatusWidgetManager {
    constructor(widgetElement, storageKey) {
        this.widget = widgetElement;
        this.storageKey = storageKey;
        this.header = this.widget.querySelector('.widget-header');
        this.toggleBtn = this.widget.querySelector('#widget-toggle-btn');
        this.downloadsContainer = this.widget.querySelector('#widget-downloads');
        this.emptyText = this.widget.querySelector('.widget-empty');

        this.pollIntervals = new Map();
        this.activeDownloads = new Map();

        this.init();
    }

    init() {
        this.header.addEventListener('click', () => this.widget.classList.toggle('minimized'));
        this.toggleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.widget.classList.toggle('minimized');
        });
        
        this.loadStoredDownloads();
        this.ensureState();
        this.syncExternalDownloads();
        
        setInterval(() => this.syncExternalDownloads(), 7000);
        window.addEventListener('focus', () => this.syncExternalDownloads());
    }

    saveActiveDownloads() {
        const payload = Array.from(this.activeDownloads.values());
        localStorage.setItem(this.storageKey, JSON.stringify(payload));
    }

    loadStoredDownloads() {
        const raw = localStorage.getItem(this.storageKey);
        const parsed = safeJsonParse(raw);
        if (Array.isArray(parsed)) {
            parsed.forEach(entry => {
                if(entry.key) this.activeDownloads.set(entry.key, entry);
            });
        }
    }

    ensureState() {
        const hasDownloads = this.activeDownloads.size > 0;
        this.widget.style.display = hasDownloads ? 'block' : 'none';
        if(this.emptyText) this.emptyText.style.display = hasDownloads ? 'none' : 'block';
        if(this.downloadsContainer) this.downloadsContainer.style.display = hasDownloads ? 'block' : 'none';
        if (hasDownloads) this.widget.classList.remove('minimized');
    }

    getOrCreateDownloadElement(key, titleText) {
        let item = this.downloadsContainer.querySelector(`[data-download-key="${key}"]`);
        if (!item) {
            item = document.createElement('div');
            item.className = 'widget-download';
            item.dataset.downloadKey = key;
            item.innerHTML = `
                <h5 class="widget-download-title">${escapeHtml(titleText)}</h5>
                <div class="progress-bar-container"><div class="progress-bar"></div></div>
                <div class="widget-stats">
                    <span class="progress-text">0%</span>
                    <span class="speed-text">0.00 МБ/с</span>
                    <span class="eta-text">--:--</span>
                </div>
                <div class="widget-stats-bottom"><span class="peers-text">Сиды: 0 / Пиры: 0</span></div>`;
            this.downloadsContainer.appendChild(item);
        }
        return item;
    }

    registerDownload(entry) {
        if (!entry.key) return;
        this.activeDownloads.set(entry.key, entry);
        this.ensureState();
        this.saveActiveDownloads();
        this.startPolling(entry);
    }

    removeDownload(key) {
        if (this.pollIntervals.has(key)) {
            clearInterval(this.pollIntervals.get(key));
            this.pollIntervals.delete(key);
        }
        if (this.activeDownloads.has(key)) {
            this.activeDownloads.delete(key);
            this.saveActiveDownloads();
        }
        const element = this.downloadsContainer.querySelector(`[data-download-key="${key}"]`);
        if (element) element.remove();
        this.ensureState();
    }

    updateView(key, data) {
        const element = this.downloadsContainer.querySelector(`[data-download-key="${key}"]`);
        if (!element) return;

        const title = element.querySelector('.widget-download-title');
        const bar = element.querySelector('.progress-bar');
        const progressText = element.querySelector('.progress-text');
        const speedText = element.querySelector('.speed-text');
        const etaText = element.querySelector('.eta-text');
        const peersText = element.querySelector('.peers-text');

        if (data.name && title) title.textContent = `Загрузка: ${data.name}`;
        if (data.status === 'error' || data.status === 'not_found') {
            if (progressText) progressText.textContent = data.status === 'error' ? 'Ошибка' : 'Ожидание...';
            if (speedText) speedText.textContent = '-';
            if (etaText) etaText.textContent = '-';
            if (peersText) peersText.textContent = data.message || (data.status === 'not_found' ? 'Торрент не найден' : '');
            if (bar) bar.style.width = '0%';
            return;
        }

        const progress = parseFloat(data.progress) || 0;
        if (bar) bar.style.width = `${progress}%`;
        if (progressText) progressText.textContent = `${progress.toFixed(0)}%`;
        if (speedText) speedText.textContent = `${data.speed || '0.00'} МБ/с`;
        if (etaText) etaText.textContent = data.eta || '--:--';
        if (peersText) peersText.textContent = `Сиды: ${data.seeds ?? 0} / Пиры: ${data.peers ?? 0}`;
    }

    async poll(entry) {
        try {
            let data;
            if (entry.type === 'kinopoisk') {
                data = await getDownloadStatusByKpId(entry.id);
            } else if (entry.type === 'lottery') {
                data = await getTorrentStatusForLottery(entry.id);
            } else if (entry.type === 'library') {
                data = await getTorrentStatusForLibrary(entry.id);
            }

            if (!data) return;

            if (data.status === 'error' || data.status === 'not_found') {
                this.updateView(entry.key, data);
                this.removeDownload(entry.key);
                return;
            }

            this.updateView(entry.key, data);
            const progress = parseFloat(data.progress) || 0;
            const statusText = (data.status || '').toLowerCase();
            if (progress >= 100 || statusText.includes('seeding') || statusText.includes('completed')) {
                const speedText = this.downloadsContainer.querySelector(`[data-download-key="${entry.key}"] .speed-text`);
                if(speedText) speedText.textContent = "Готово";
                setTimeout(() => this.removeDownload(entry.key), 5000);
            }
        } catch (error) {
            console.error(`Ошибка опроса для ${entry.key}:`, error);
            this.updateView(entry.key, { status: 'error', message: 'Нет связи' });
            this.removeDownload(entry.key);
        }
    }

    startPolling(entry) {
        if (this.pollIntervals.has(entry.key)) return;
        
        this.getOrCreateDownloadElement(entry.key, `Загрузка: ${entry.movieName}`);
        this.poll(entry); // Первый запуск немедленно
        const intervalId = setInterval(() => this.poll(entry), 3000);
        this.pollIntervals.set(entry.key, intervalId);
    }
    
    async syncExternalDownloads() {
        try {
            const data = await fetchActiveDownloads();
            if (!data.downloads) return;

            const galleryItems = document.querySelectorAll('.gallery-item[data-kinopoisk-id]');
            const kpIdToLotteryId = new Map();
            galleryItems.forEach(item => {
                kpIdToLotteryId.set(item.dataset.kinopoiskId, item.dataset.lotteryId || item.dataset.movieId)
            });

            data.downloads.forEach(item => {
                const kpId = String(item.kinopoisk_id);
                const key = getDownloadKey(kpId, 'kinopoisk');
                if (!this.activeDownloads.has(key)) {
                    // Нашли новый торрент, которого нет в localStorage
                    const entry = {
                        key: key,
                        id: kpId,
                        type: 'kinopoisk',
                        movieName: item.name
                    };
                    this.registerDownload(entry);
                }
            });
        } catch (error) {
            console.warn("Не удалось синхронизировать внешние загрузки:", error);
        }
    }
}

// Вспомогательная функция для экранирования HTML, если она нужна только здесь
function escapeHtml(value) {
    const p = document.createElement('p');
    p.textContent = value;
    return p.innerHTML;
}