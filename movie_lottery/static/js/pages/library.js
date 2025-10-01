// F:\GPT\movie-lottery V2\movie_lottery\static\js\pages\library.js

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

    const downloadButton = actionButtons.querySelector('.download-button');
    const searchButton = actionButtons.querySelector('.search-button');
    if (downloadButton) downloadButton.remove();
    if (searchButton) searchButton.remove();

    const newButton = document.createElement('button');
    newButton.type = 'button';
    
    if (hasMagnet) {
        newButton.className = 'icon-button download-button';
        newButton.title = 'Скачать торрент';
        newButton.setAttribute('aria-label', 'Скачать торрент');
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
    const gallery = document.querySelector('.library-gallery');
    const modalElement = document.getElementById('library-modal');
    const widgetElement = document.getElementById('torrent-status-widget');

    if (!gallery || !modalElement || !widgetElement) return;

    const modal = new ModalManager(modalElement);
    const widget = new StatusWidgetManager(widgetElement, 'libraryActiveDownloads');

    const getMovieDataFromCard = (card) => {
        const ds = card.dataset;
        return {
            id: ds.movieId,
            kinopoisk_id: ds.kinopoiskId,
            name: ds.movieName,
            search_name: ds.movieSearchName,
            year: ds.movieYear,
            poster: ds.moviePoster,
            description: ds.movieDescription,
            rating_kp: ds.movieRating,
            genres: ds.movieGenres,
            countries: ds.movieCountries,
            has_magnet: ds.hasMagnet === 'true',
            magnet_link: ds.magnetLink,
            is_on_client: card.classList.contains('has-torrent-on-client'),
            torrent_hash: ds.torrentHash,
        };
    };

    const handleOpenModal = (card) => {
        const movieData = getMovieDataFromCard(card);
        modalElement.dataset.activeCardId = card.dataset.movieId || '';
        modal.open();
        modal.renderLibraryModal(movieData, {
            onSaveMagnet: async (kinopoiskId, magnetLink) => {
                const result = await movieApi.saveMagnetLink(kinopoiskId, magnetLink);
                showToast(result.message, 'success');
                // Обновляем данные и иконку на карточке
                card.dataset.hasMagnet = result.has_magnet.toString();
                card.dataset.magnetLink = result.magnet_link;
                toggleDownloadIcon(card, result.has_magnet);
                handleOpenModal(card);
            },
            onDeleteFromLibrary: () => {
                movieApi.deleteLibraryMovie(movieData.id).then(data => {
                    if (data.success) {
                        modal.close();
                        card.remove();
                    }
                    showToast(data.message, data.success ? 'success' : 'error');
                });
            },
            onDownload: () => torrentApi.startLibraryDownload(movieData.id).then(data => showToast(data.message, data.success ? 'success' : 'error')),
            onDeleteTorrent: async (torrentHash) => {
                await torrentApi.deleteTorrentFromClient(torrentHash);
                card.classList.remove('has-torrent-on-client');
                handleOpenModal(card);
            }
        });
    };

    // АВТОПОИСК МАГНЕТ-ССЫЛОК ОТКЛЮЧЕН
    // Пользователь вручную вводит магнет-ссылки через модальное окно
    // Кнопка RuTracker для поиска на сайте сохранена

    gallery.addEventListener('click', (event) => {
        const card = event.target.closest('.gallery-item');
        if (!card) return;

        const { movieId, kinopoiskId, movieName, movieYear, hasMagnet } = card.dataset;
        const button = event.target.closest('.icon-button');

        if (button) {
            event.stopPropagation();
            if (button.classList.contains('delete-button')) {
                movieApi.deleteLibraryMovie(movieId).then(data => {
                    if (data.success) card.remove();
                    showToast(data.message, data.success ? 'success' : 'error');
                });
            } else if (button.classList.contains('add-magnet-button')) {
                // Открываем модальное окно для ручного ввода magnet-ссылки
                handleOpenModal(card);
            } else if (button.classList.contains('download-button')) {
                if (hasMagnet === 'true' && kinopoiskId) {
                    torrentApi.startLibraryDownload(movieId).then(data => showToast(data.message, data.success ? 'success' : 'error'));
                } else {
                    showToast('Сначала нужно добавить magnet-ссылку.', 'info');
                    handleOpenModal(card);
                }
            }
        } else {
            handleOpenModal(card);
        }
    });

    document.querySelectorAll('.date-badge').forEach(badge => {
        badge.textContent = formatDate(badge.dataset.date);
    });

    if (window.torrentUpdater) {
        window.torrentUpdater.updateUi();
    }
});