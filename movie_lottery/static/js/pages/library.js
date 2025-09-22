// F:\GPT\movie-lottery V2\movie_lottery\static\js\pages\library.js

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
    const gallery = document.querySelector('.library-gallery');
    const modalElement = document.getElementById('library-modal');
    const widgetElement = document.getElementById('torrent-status-widget');

    if (!gallery || !modalElement || !widgetElement) {
        console.error('Essential page elements not found. Aborting script.');
        return;
    }

    const modal = new ModalManager(modalElement);
    const widget = new StatusWidgetManager(widgetElement, 'libraryActiveDownloads');

    const getMovieDataFromCard = (card) => {
        const ds = card.dataset;
        return {
            id: ds.movieId,
            kinopoisk_id: ds.kinopoiskId,
            name: ds.movieName,
            year: ds.movieYear,
            poster: ds.moviePoster,
            description: ds.movieDescription,
            rating_kp: ds.movieRating,
            genres: ds.movieGenres,
            countries: ds.movieCountries,
            has_magnet: ds.hasMagnet === 'true',
            magnet_link: ds.magnetLink,
            is_on_client: card.classList.contains('has-torrent-on-client'), // Берем актуальные данные
            torrent_hash: ds.torrentHash,
        };
    };

    const handleOpenModal = (card) => {
        const movieData = getMovieDataFromCard(card);
        modal.open();
        modal.renderLibraryModal(movieData, {
            onSaveMagnet: async (kinopoiskId, magnetLink) => {
                const result = await movieApi.saveMagnetLink(kinopoiskId, magnetLink);
                showToast(result.message, 'success');
                card.dataset.hasMagnet = result.has_magnet.toString();
                card.dataset.magnetLink = result.magnet_link;
                handleOpenModal(card); 
            },
            onDeleteFromLibrary: () => {
                 movieApi.deleteLibraryMovie(movieData.id).then(data => {
                    showToast(data.message, data.success ? 'success' : 'error');
                    if(data.success) {
                        modal.close();
                        card.classList.add('is-deleting');
                        card.addEventListener('transitionend', () => card.remove());
                    }
                });
            },
            onDownload: () => {
                torrentApi.startLibraryDownload(movieData.id)
                   .then(data => showToast(data.message, data.success ? 'success' : 'error'));
            },
            onDeleteTorrent: async (torrentHash) => {
                await torrentApi.deleteTorrentFromClient(torrentHash);
                card.classList.remove('has-torrent-on-client');
                handleOpenModal(card);
            }
        });
    };
    
    gallery.addEventListener('click', (event) => {
        const card = event.target.closest('.gallery-item');
        if (!card) return;

        const { movieId, kinopoiskId, movieName, movieYear, hasMagnet } = card.dataset;
        const button = event.target.closest('.icon-button');

        if (button) {
            event.stopPropagation();
            if (button.classList.contains('delete-button')) {
                movieApi.deleteLibraryMovie(movieId).then(data => {
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
                    torrentApi.startLibraryDownload(movieId)
                        .then(data => showToast(data.message, data.success ? 'success' : 'error'));
                } else {
                    showToast('Сначала нужно добавить magnet-ссылку.', 'info');
                    handleOpenModal(card);
                }
            }
        } else {
            handleOpenModal(card);
        }
    });

    // Форматируем все даты на странице
    document.querySelectorAll('.date-badge').forEach(badge => {
        badge.textContent = formatDate(badge.dataset.date);
    });
    
    // Запускаем фоновое обновление статусов торрентов
    if (window.torrentUpdater) {
        window.torrentUpdater.updateUi();
    }
});