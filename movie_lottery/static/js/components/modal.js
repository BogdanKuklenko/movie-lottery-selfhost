// F:\GPT\movie-lottery V2\movie_lottery\static\js\components\modal.js

import { initSlider } from './slider.js';
import { saveMagnetLink } from '../api/movies.js';
import { deleteTorrentFromClient } from '../api/torrents.js';

// --- Вспомогательные функции для рендеринга ---

function escapeHtml(value) {
    if (value === null || value === undefined) return '';
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

const placeholderPoster = 'https://via.placeholder.com/200x300.png?text=No+Image';

/**
 * Создает HTML-разметку для списка участников лотереи.
 * @param {Array<object>} movies - Массив фильмов-участников.
 * @param {string|null} winnerName - Имя победителя для выделения.
 * @returns {string} - HTML-строка.
 */
function createParticipantsHTML(movies, winnerName) {
    if (!movies || movies.length === 0) return '';
    
    const itemsHTML = movies.map(movie => {
        const isWinner = movie.name === winnerName;
        return `
            <li class="participant-item ${isWinner ? 'winner' : ''}">
                <img class="participant-poster" src="${escapeHtml(movie.poster || placeholderPoster)}" alt="${escapeHtml(movie.name)}">
                <span class="participant-name">${escapeHtml(movie.name)}</span>
                <span class="participant-meta">${escapeHtml(movie.year || '')}</span>
                ${isWinner ? '<span class="participant-winner-badge">Победитель</span>' : ''}
            </li>`;
    }).join('');

    return `
        <div id="modal-participants">
            <h3>Участники лотереи</h3>
            <ul class="participants-list">${itemsHTML}</ul>
        </div>`;
}

/**
 * Создает HTML-разметку для карточки победителя или фильма из библиотеки.
 * @param {object} movieData - Данные о фильме.
 * @param {object} actions - Функции обратного вызова для кнопок.
 * @returns {string} - HTML-строка.
 */
function createWinnerCardHTML(movieData, isLibrary) {
    const ratingValue = parseFloat(movieData.rating_kp);
    let ratingBadge = '';
    if (!isNaN(ratingValue)) {
        const ratingClass = ratingValue >= 7 ? 'rating-high' : ratingValue >= 5 ? 'rating-medium' : 'low';
        ratingBadge = `<div class="rating-badge rating-${ratingClass}">${ratingValue.toFixed(1)}</div>`;
    }

    // Кнопка удаления из библиотеки или добавления в нее
    const libraryButtonHTML = isLibrary
        ? `<button class="danger-button modal-delete-btn">Удалить из библиотеки</button>`
        : `<button class="secondary-button add-library-modal-btn">Добавить в библиотеку</button>`;

    return `
        <div class="winner-card">
            <div class="winner-poster">
                <img src="${escapeHtml(movieData.poster || placeholderPoster)}" alt="Постер ${escapeHtml(movieData.name)}">
                ${ratingBadge}
            </div>
            <div class="winner-details">
                <h2>${escapeHtml(movieData.name)}${movieData.year ? ` (${escapeHtml(movieData.year)})` : ''}</h2>
                <p class="meta-info">${escapeHtml(movieData.genres || 'н/д')} / ${escapeHtml(movieData.countries || 'н/д')}</p>
                <p class="description">${escapeHtml(movieData.description || 'Описание отсутствует.')}</p>
                
                ${movieData.kinopoisk_id ? `
                    <div class="magnet-form">
                        <label for="magnet-input">Magnet-ссылка:</label>
                        <input type="text" id="magnet-input" value="${escapeHtml(movieData.magnet_link || '')}" placeholder="Вставьте magnet-ссылку...">
                        <div class="magnet-actions">
                            <button class="action-button save-magnet-btn">Сохранить</button>
                            ${movieData.has_magnet ? '<button class="action-button-delete delete-magnet-btn">Удалить</button>' : ''}
                        </div>
                    </div>` : '<p class="meta-info">Kinopoisk ID не указан, работа с magnet-ссылкой недоступна.</p>'}
                
                <div class="library-modal-actions">
                    <button class="secondary-button modal-download-btn"${movieData.has_magnet ? '' : ' disabled'}>Скачать</button>
                    ${libraryButtonHTML}
                </div>

                <div class="slide-to-delete-container ${movieData.is_on_client ? '' : 'disabled'}" data-torrent-hash="${escapeHtml(movieData.torrent_hash || '')}">
                    <div class="slide-to-delete-track">
                        <div class="slide-to-delete-fill"></div>
                        <span class="slide-to-delete-text">Удалить с клиента</span>
                        <div class="slide-to-delete-thumb">&gt;</div>
                    </div>
                </div>
            </div>
        </div>`;
}


// --- Основной класс для управления модальным окном ---

export class ModalManager {
    constructor(modalElement) {
        this.modal = modalElement;
        this.body = this.modal.querySelector('.modal-content > div'); // Первый div внутри .modal-content
        this.closeButton = this.modal.querySelector('.close-button');
        
        this.close = this.close.bind(this);
        this.handleOutsideClick = this.handleOutsideClick.bind(this);
        
        this.closeButton.addEventListener('click', this.close);
        this.modal.addEventListener('click', this.handleOutsideClick);
    }
    
    open() {
        this.modal.style.display = 'flex';
        document.body.classList.add('no-scroll');
        this.body.innerHTML = '<div class="loader"></div>';
    }

    close() {
        this.modal.style.display = 'none';
        document.body.classList.remove('no-scroll');
        this.body.innerHTML = '';
    }

    handleOutsideClick(event) {
        if (event.target === this.modal) {
            this.close();
        }
    }
    
    renderError(message) {
        this.body.innerHTML = `<p class="error-message">${escapeHtml(message)}</p>`;
    }
    
    /**
     * Рендерит содержимое для модального окна Истории.
     * @param {object} lotteryData - Полные данные о лотерее.
     * @param {object} actions - Обработчики событий.
     */
    renderHistoryModal(lotteryData, actions) {
        const winnerHTML = createWinnerCardHTML(lotteryData.result, false);
        const participantsHTML = createParticipantsHTML(lotteryData.movies, lotteryData.result.name);
        this.body.innerHTML = winnerHTML + participantsHTML;
        this.attachEventListeners(lotteryData.result, actions);
    }
    
    /**
     * Рендерит содержимое для модального окна Библиотеки.
     * @param {object} movieData - Данные о фильме.
     * @param {object} actions - Обработчики событий.
     */
    renderLibraryModal(movieData, actions) {
        this.body.innerHTML = createWinnerCardHTML(movieData, true);
        this.attachEventListeners(movieData, actions);
    }

    /**
     * Навешивает обработчики событий на интерактивные элементы внутри модального окна.
     * @param {object} movieData - Данные о фильме.
     * @param {object} actions - Объект с функциями-обработчиками.
     */
    attachEventListeners(movieData, actions) {
        // Кнопка "Сохранить magnet"
        const saveMagnetBtn = this.body.querySelector('.save-magnet-btn');
        if (saveMagnetBtn) {
            saveMagnetBtn.addEventListener('click', () => {
                const input = this.body.querySelector('#magnet-input');
                actions.onSaveMagnet(movieData.kinopoisk_id, input.value.trim());
            });
        }

        // Кнопка "Удалить magnet"
        const deleteMagnetBtn = this.body.querySelector('.delete-magnet-btn');
        if (deleteMagnetBtn) {
            deleteMagnetBtn.addEventListener('click', () => actions.onSaveMagnet(movieData.kinopoisk_id, ''));
        }

        // Кнопка "Добавить/Удалить из библиотеки"
        const addLibraryBtn = this.body.querySelector('.add-library-modal-btn');
        if (addLibraryBtn) {
            addLibraryBtn.addEventListener('click', () => actions.onAddToLibrary(movieData));
        }
        const deleteLibraryBtn = this.body.querySelector('.modal-delete-btn');
        if (deleteLibraryBtn) {
            deleteLibraryBtn.addEventListener('click', actions.onDeleteFromLibrary);
        }
        
        // Кнопка "Скачать"
        const downloadBtn = this.body.querySelector('.modal-download-btn');
        if (downloadBtn && !downloadBtn.disabled) {
            downloadBtn.addEventListener('click', actions.onDownload);
        }

        // Слайдер
        const slider = this.body.querySelector('.slide-to-delete-container');
        if (slider && !slider.classList.contains('disabled')) {
            initSlider(slider, () => {
                actions.onDeleteTorrent(slider.dataset.torrentHash);
            });
        }
    }
}