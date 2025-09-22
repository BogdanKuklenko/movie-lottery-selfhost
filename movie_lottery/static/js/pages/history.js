// F:\GPT\movie-lottery V2\movie_lottery\static\js\pages\history.js

import { ModalManager } from '../components/modal.js';
import { StatusWidgetManager } from '../components/statusWidget.js';
import * as movieApi from '../api/movies.js';
import * as torrentApi from '../api/torrents.js';

function formatDate(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    return date.toLocaleDateString('ru-RU');
}

/**
 * Динамически переключает иконку "скачать"/"искать" на карточке.
 * @param {HTMLElement} card - Элемент карточки.
 * @param {boolean} hasMagnet - Есть ли magnet-ссылка.
 */
function toggleDownloadIcon(card, hasMagnet) {
    const actionButtons = card.querySelector('.action-buttons');
    if (!actionButtons) return;

    // Удаляем обе кнопки, чтобы избежать дублирования
    const downloadButton = actionButtons.querySelector('.download-button');
    const searchButton = actionButtons.querySelector('.search-button');
    if (downloadButton) downloadButton.remove();
    if (searchButton) searchButton.remove();

    // Создаем нужную кнопку и вставляем ее на первое место
    const newButton = document.createElement('button');
    newButton.type = 'button';
    
    if (hasMagnet) {
        newButton.className = 'icon-button download-button';
        newButton.title = 'Скачать фильм';
        newButton.setAttribute('aria-label', 'Скачать фильм');
        newButton.innerHTML = `<svg class="icon-svg icon-download" viewBox="0 0 24 24"><use href="#icon-download"></use></svg>`;
    } else {
        newButton.className = 'icon-button search-button';
        newButton.title = 'Искать торрент';
        newButton.setAttribute('aria-label', 'Искать торрент');
        newButton.innerHTML = `<svg class="icon-svg icon-search" viewBox="0 0 24 24"><use href="#icon-search"></use></svg>`;
    }
    
    actionButtons.prepend(newButton);
}


document.addEventListener('DOMContentLoaded', () => {
    const gallery = document.querySelector('.history-gallery');
    const modalElement = document.getElementById('history-modal');
    const widgetElement = document.getElementById('torrent-status-widget');

    if (!gallery || !modalElement || !widgetElement) return;

    const modal = new ModalManager(modalElement);
    const widget = new StatusWidgetManager(widgetElement, 'lotteryActiveDownloads');

    const handleOpenModal = async (lotteryId) => {
        const card = document.querySelector(`.gallery-item[data-lottery-id="${lotteryId}"]`);
        modalElement.dataset.activeLotteryId = lotteryId;
        modal.open();
        try {
            const lotteryData = await movieApi.fetchLotteryDetails(lotteryId);
            if (lotteryData.result) {
                if (card) {
                    lotteryData.result.is_on_client = card.classList.contains('has-torrent-on-client');
                    lotteryData.result.torrent_hash = card.dataset.torrentHash || '';
                }

                modal.renderHistoryModal(lotteryData, {
                    onSaveMagnet: async (kinopoiskId, magnetLink) => {
                        const result = await movieApi.saveMagnetLink(kinopoiskId, magnetLink);
                        showToast(result.message, result.success ? 'success' : 'error');
                        // Обновляем данные и иконку на карточке
                        if (card) {
                            card.dataset.hasMagnet = result.has_magnet.toString();
                            card.dataset.magnetLink = result.magnet_link;
                            toggleDownloadIcon(card, result.has_magnet);
                        }
                        handleOpenModal(lotteryId);
                    },
                    onAddToLibrary: (movieData) => movieApi.addOrUpdateLibraryMovie(movieData).then(data => showToast(data.message, data.success ? 'success' : 'error')),
                    onDownload: () => torrentApi.startDownloadByKpId(lotteryData.result.kinopoisk_id).then(data => showToast(data.message, data.success ? 'success' : 'error')),
                    onDeleteTorrent: async (torrentHash) => {
                        await torrentApi.deleteTorrentFromClient(torrentHash);
                        if (card) card.classList.remove('has-torrent-on-client');
                        handleOpenModal(lotteryId);
                    }
                });
            } else {
                modal.renderWaitingModal(lotteryData);
            }
        } catch (error) {
            modal.renderError(error.message);
        }
    };

    const activeSearchTimers = new Map();

    const stopPolling = (kinopoiskId) => {
        const timerId = activeSearchTimers.get(kinopoiskId);
        if (timerId) {
            clearTimeout(timerId);
            activeSearchTimers.delete(kinopoiskId);
        }
    };

    const setCardSearching = (card, isSearching) => {
        card.dataset.searching = isSearching ? 'true' : 'false';
        card.classList.toggle('is-searching', isSearching);
        const searchButton = card.querySelector('.search-button');
        if (searchButton) {
            searchButton.disabled = isSearching;
            searchButton.classList.toggle('loading', isSearching);
            if (isSearching) {
                searchButton.setAttribute('aria-busy', 'true');
            } else {
                searchButton.removeAttribute('aria-busy');
            }
        }
    };

    const handleSearchStatus = (card, status, lotteryId, { initialToast = false } = {}) => {
        if (!status || !status.status) {
            setCardSearching(card, false);
            return false;
        }

        const state = status.status;
        if (state === 'queued' || state === 'running') {
            if (initialToast) {
                showToast(status.message || 'Поиск magnet-ссылки запущен.', 'info');
            }
            return true;
        }

        stopPolling(card.dataset.kinopoiskId);
        setCardSearching(card, false);

        const hasMagnet = Boolean(status.has_magnet && status.magnet_link);
        card.dataset.hasMagnet = hasMagnet ? 'true' : 'false';
        card.dataset.magnetLink = hasMagnet ? status.magnet_link : '';
        toggleDownloadIcon(card, hasMagnet);

        if (hasMagnet) {
            showToast(status.message || 'Magnet-ссылка найдена.', 'success');
            if (window.torrentUpdater && typeof window.torrentUpdater.updateUi === 'function') {
                window.torrentUpdater.updateUi();
            }
            if (
                modalElement.style.display === 'flex'
                && modalElement.dataset.activeLotteryId === lotteryId
            ) {
                handleOpenModal(lotteryId);
            }
        } else if (state === 'not_found') {
            showToast(status.message || 'Подходящая magnet-ссылка не найдена.', 'warning');
        } else if (state === 'failed') {
            showToast(status.message || 'Ошибка при поиске magnet.', 'error');
        } else {
            showToast(status.message || 'Поиск завершен.', 'info');
        }

        return false;
    };

    const pollSearchStatus = (card, kinopoiskId, lotteryId) => {
        const scheduleNext = () => {
            const timerId = setTimeout(async () => {
                try {
                    const status = await movieApi.fetchMagnetSearchStatus(kinopoiskId);
                    const shouldContinue = handleSearchStatus(card, status, lotteryId);
                    if (shouldContinue) {
                        scheduleNext();
                    }
                } catch (error) {
                    stopPolling(kinopoiskId);
                    setCardSearching(card, false);
                    showToast(error.message, 'error');
                }
            }, 2000);
            activeSearchTimers.set(kinopoiskId, timerId);
        };

        stopPolling(kinopoiskId);
        scheduleNext();
    };

    const triggerMagnetSearch = async (card) => {
        const { kinopoiskId, movieName, movieYear, lotteryId } = card.dataset;
        if (!kinopoiskId) {
            showToast('Для фильма не указан Kinopoisk ID.', 'error');
            return;
        }

        if (card.dataset.searching === 'true' || activeSearchTimers.has(kinopoiskId)) {
            showToast('Поиск magnet уже выполняется.', 'info');
            return;
        }

        const query = `${(movieName || '').trim()} ${movieYear || ''}`.trim();
        setCardSearching(card, true);

        try {
            const status = await movieApi.startMagnetSearch(kinopoiskId, { query, title: movieName, year: movieYear });
            const shouldContinue = handleSearchStatus(card, status, lotteryId, { initialToast: true });
            if (shouldContinue) {
                pollSearchStatus(card, kinopoiskId, lotteryId);
            }
        } catch (error) {
            setCardSearching(card, false);
            showToast(error.message, 'error');
        }
    };

    gallery.addEventListener('click', (event) => {
        const card = event.target.closest('.gallery-item');
        if (!card) return;

        const { lotteryId, kinopoiskId, movieName, movieYear, hasMagnet } = card.dataset;
        const button = event.target.closest('.icon-button');

        if (button) {
            event.stopPropagation();
            if (button.classList.contains('delete-button')) {
                movieApi.deleteLottery(lotteryId).then(data => {
                    if (data.success) card.remove();
                    showToast(data.message, data.success ? 'success' : 'error');
                });
            } else if (button.classList.contains('search-button')) {
                triggerMagnetSearch(card);
            } else if (button.classList.contains('download-button')) {
                if (hasMagnet === 'true' && kinopoiskId) {
                    torrentApi.startDownloadByKpId(kinopoiskId).then(data => showToast(data.message, data.success ? 'success' : 'error'));
                } else {
                    showToast('Сначала нужно добавить magnet-ссылку.', 'info');
                    handleOpenModal(lotteryId);
                }
            }
        } else if (lotteryId) {
            handleOpenModal(lotteryId);
        }
    });

    document.querySelectorAll('.date-badge').forEach(badge => {
        badge.textContent = formatDate(badge.dataset.date);
    });

    window.addEventListener('beforeunload', () => {
        activeSearchTimers.forEach(timerId => clearTimeout(timerId));
        activeSearchTimers.clear();
    });

    if (window.torrentUpdater) {
        window.torrentUpdater.updateUi();
    }
});