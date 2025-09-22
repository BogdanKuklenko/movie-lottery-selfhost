// F:\GPT\movie-lottery V2\movie_lottery\static\js\pages\history.js

import { ModalManager } from '../components/modal.js';
import { StatusWidgetManager } from '../components/statusWidget.js';
import * as movieApi from '../api/movies.js';
import * as torrentApi from '../api/torrents.js';

/**
 * Форматирует дату из ISO в "ДД.ММ.ГГГГ".
 * @param {string} isoString - Дата в формате ISO.
 * @returns {string} - Отформатированная дата.
 */
function formatDate(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    return `${day}.${month}.${year}`;
}

document.addEventListener('DOMContentLoaded', () => {
    const gallery = document.querySelector('.history-gallery');
    const modalElement = document.getElementById('history-modal');
    const widgetElement = document.getElementById('torrent-status-widget');

    if (!gallery || !modalElement || !widgetElement) {
        console.error('Essential page elements not found. Aborting script.');
        return;
    }

    const modal = new ModalManager(modalElement);
    const widget = new StatusWidgetManager(widgetElement, 'lotteryActiveDownloads');
    
    const handleOpenModal = async (lotteryId) => {
        modal.open();
        try {
            const lotteryData = await movieApi.fetchLotteryDetails(lotteryId);
            if(lotteryData.result) {
                modal.renderHistoryModal(lotteryData, {
                    onSaveMagnet: async (kinopoiskId, magnetLink) => {
                        await movieApi.saveMagnetLink(kinopoiskId, magnetLink);
                        handleOpenModal(lotteryId);
                    },
                    onAddToLibrary: (movieData) => {
                        movieApi.addOrUpdateLibraryMovie(movieData)
                            .then(data => showToast(data.message, data.success ? 'success' : 'error'));
                    },
                    onDownload: () => {
                        torrentApi.startDownloadByKpId(lotteryData.result.kinopoisk_id)
                           .then(data => showToast(data.message, data.success ? 'success' : 'error'));
                    },
                    onDeleteTorrent: async (torrentHash) => {
                        await torrentApi.deleteTorrentFromClient(torrentHash);
                        const card = document.querySelector(`.gallery-item[data-lottery-id="${lotteryId}"]`);
                        if (card) {
                            card.classList.remove('has-torrent-on-client');
                        }
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
                    showToast(data.message, data.success ? 'success' : 'error');
                    if(data.success) {
                        card.classList.add('is-deleting');
                        card.addEventListener('transitionend', () => card.remove());
                    }
                });
            } 
            else if (button.classList.contains('search-button')) {
                const query = encodeURIComponent(`${movieName.trim()} ${movieYear || ''}`.trim());
                window.open(`https://rutracker.org/forum/tracker.php?nm=${query}`, '_blank');
            }
            else if (button.classList.contains('download-button')) {
                 if (hasMagnet === 'true' && kinopoiskId) {
                    torrentApi.startDownloadByKpId(kinopoiskId)
                        .then(data => showToast(data.message, data.success ? 'success' : 'error'));
                } else {
                    showToast('Сначала нужно добавить magnet-ссылку.', 'info');
                    handleOpenModal(lotteryId);
                }
            }
        } else {
            if(!card.classList.contains('waiting-card')) {
                handleOpenModal(lotteryId);
            } else {
                showToast('Эта лотерея еще не разыграна.', 'info');
            }
        }
    });

    // Форматируем все даты на странице
    document.querySelectorAll('.date-badge').forEach(badge => {
        badge.textContent = formatDate(badge.dataset.date);
    });

    // Запускаем фоновое обновление статусов торрентов (оно само возьмет данные из sessionStorage)
    if (window.torrentUpdater) {
        window.torrentUpdater.updateUi();
    }
});