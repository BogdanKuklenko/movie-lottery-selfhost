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
                modal.renderError('Информация о победителе еще не доступна.');
            }
        } catch (error) {
            modal.renderError(error.message);
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
                const query = encodeURIComponent(`${movieName.trim()} ${movieYear || ''}`.trim());
                window.open(`https://rutracker.org/forum/tracker.php?nm=${query}`, '_blank');
            } else if (button.classList.contains('download-button')) {
                if (hasMagnet === 'true' && kinopoiskId) {
                    torrentApi.startDownloadByKpId(kinopoiskId).then(data => showToast(data.message, data.success ? 'success' : 'error'));
                } else {
                    showToast('Сначала нужно добавить magnet-ссылку.', 'info');
                    handleOpenModal(lotteryId);
                }
            }
        } else if (!card.classList.contains('waiting-card')) {
            handleOpenModal(lotteryId);
        } else {
            showToast('Эта лотерея еще не разыграна.', 'info');
        }
    });

    document.querySelectorAll('.date-badge').forEach(badge => {
        badge.textContent = formatDate(badge.dataset.date);
    });

    if (window.torrentUpdater) {
        window.torrentUpdater.updateUi();
    }
});