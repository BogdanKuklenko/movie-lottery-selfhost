// F:\GPT\movie-lottery V2\movie_lottery\static\js\pages\library.js

import { ModalManager } from '../components/modal.js';
import { StatusWidgetManager } from '../components/statusWidget.js';
import * as movieApi from '../api/movies.js';
import * as torrentApi from '../api/torrents.js';

document.addEventListener('DOMContentLoaded', () => {
    // --- ИНИЦИАЛИЗАЦИЯ ОСНОВНЫХ ЭЛЕМЕНТОВ ---
    const gallery = document.querySelector('.library-gallery');
    const modalElement = document.getElementById('library-modal');
    const widgetElement = document.getElementById('torrent-status-widget');

    if (!gallery || !modalElement || !widgetElement) {
        console.error('Essential page elements not found. Aborting script.');
        return;
    }

    const modal = new ModalManager(modalElement);
    const widget = new StatusWidgetManager(widgetElement, 'libraryActiveDownloads');

    // --- ЛОГИКА СТРАНИЦЫ "БИБЛИОТЕКА" ---
    
    // Функция для получения данных о фильме прямо из data-атрибутов карточки
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
            is_on_client: ds.isOnClient === 'true',
            torrent_hash: ds.torrentHash,
        };
    };

    const handleOpenModal = (card) => {
        const movieData = getMovieDataFromCard(card);
        modal.open();
        modal.renderLibraryModal(movieData, {
            onSaveMagnet: async (kinopoiskId, magnetLink) => {
                await movieApi.saveMagnetLink(kinopoiskId, magnetLink);
                // Обновляем данные на карточке и перерисовываем модалку
                const updatedCardData = await movieApi.fetchLotteryDetails(card.dataset.lotteryId)
                const updatedMovie = updatedCardData.movies.find(m => m.kinopoisk_id == kinopoiskId);
                Object.assign(card.dataset, updatedMovie); // Упрощенное обновление
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
                // Обновляем данные на карточке и перерисовываем модалку
                card.dataset.isOnClient = 'false';
                card.classList.remove('has-torrent-on-client');
                handleOpenModal(card);
            }
        });
    };
    
    // --- ГЛАВНЫЙ ОБРАБОТЧИК СОБЫТИЙ ---
    gallery.addEventListener('click', (event) => {
        const card = event.target.closest('.gallery-item');
        if (!card) return;

        const { movieId, kinopoiskId, movieName, movieYear, hasMagnet } = card.dataset;
        const button = event.target.closest('.icon-button');

        if (button) { // Клик был по кнопке
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
        } else { // Клик по самой карточке
            handleOpenModal(card);
        }
    });
});