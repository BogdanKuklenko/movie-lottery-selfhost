// F:\GPT\movie-lottery V2\movie_lottery\static\js\pages\history.js

import { ModalManager } from '../components/modal.js';
import { StatusWidgetManager } from '../components/statusWidget.js';
import * as movieApi from '../api/movies.js';
import * as torrentApi from '../api/torrents.js';

document.addEventListener('DOMContentLoaded', () => {
    // --- ИНИЦИАЛИЗАЦИЯ ОСНОВНЫХ ЭЛЕМЕНТОВ ---
    const gallery = document.querySelector('.history-gallery');
    const modalElement = document.getElementById('history-modal');
    const widgetElement = document.getElementById('torrent-status-widget');

    if (!gallery || !modalElement || !widgetElement) {
        console.error('Essential page elements not found. Aborting script.');
        return;
    }

    const modal = new ModalManager(modalElement);
    const widget = new StatusWidgetManager(widgetElement, 'lotteryActiveDownloads');
    
    // --- ЛОГИКА СТРАНИЦЫ "ИСТОРИЯ" ---

    const handleOpenModal = async (lotteryId) => {
        modal.open();
        try {
            const lotteryData = await movieApi.fetchLotteryDetails(lotteryId);
            if(lotteryData.result) {
                modal.renderHistoryModal(lotteryData, {
                    onSaveMagnet: async (kinopoiskId, magnetLink) => {
                        await movieApi.saveMagnetLink(kinopoiskId, magnetLink);
                        handleOpenModal(lotteryId); // Перерисовываем модалку
                        // TODO: Обновить карточку в галерее без перезагрузки
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
                        handleOpenModal(lotteryId); // Перерисовываем модалку
                        // TODO: Обновить карточку в галерее без перезагрузки
                    }
                });
            } else {
                 modal.renderError('Информация о победителе еще не доступна.');
            }
        } catch (error) {
            modal.renderError(error.message);
        }
    };
    
    // --- ГЛАВНЫЙ ОБРАБОТЧИК СОБЫТИЙ ---
    gallery.addEventListener('click', (event) => {
        const card = event.target.closest('.gallery-item');
        if (!card) return;

        const { lotteryId, kinopoiskId, movieName, movieYear, hasMagnet } = card.dataset;
        const button = event.target.closest('.icon-button');

        if (button) { // Клик был по кнопке
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
        } else { // Клик по самой карточке
            if(!card.classList.contains('waiting-card')) {
                handleOpenModal(lotteryId);
            } else {
                showToast('Эта лотерея еще не разыграна.', 'info');
            }
        }
    });

});