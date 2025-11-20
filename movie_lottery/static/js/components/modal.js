// F:\GPT\movie-lottery V2\movie_lottery\static\js\components\modal.js

import { initSlider } from './slider.js';
import { saveMagnetLink } from '../api/movies.js';
import { deleteTorrentFromClient } from '../api/torrents.js';
import { lockScroll, unlockScroll } from '../utils/scrollLock.js';

// --- Вспомогательные функции для рендеринга ---

// Стек открытых модальных окон для корректной работы истории и блокировки скролла
const modalStack = [];
let ignoreNextPopState = false;

function consumeIgnoreFlag() {
    if (ignoreNextPopState) {
        ignoreNextPopState = false;
        return true;
    }
    return false;
}

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

function formatDateTime(value) {
    if (!value) return '';
    const date = new Date(value);
    return date.toLocaleString('ru-RU');
}

function formatBanDuration(seconds) {
    const totalSeconds = Math.max(0, Math.floor(seconds || 0));
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const secs = totalSeconds % 60;
    return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

function renderBanInfo(movieData) {
    if (!movieData || movieData.ban_status === 'none') {
        return '';
    }

    if (movieData.ban_status === 'pending') {
        return `<div class="ban-info">⛔ Бан без срока</div>`;
    }

    if (movieData.ban_status === 'expired') {
        return `<div class="ban-info">⛔ Бан истёк и будет автоматически снят</div>`;
    }

    const untilText = movieData.ban_until ? `до ${formatDateTime(movieData.ban_until)}` : 'активен';
    const remaining = formatBanDuration(movieData.ban_remaining_seconds || 0);
    const appliedBy = movieData.ban_applied_by ? `<div class="ban-meta">Назначил: ${escapeHtml(movieData.ban_applied_by)}</div>` : '';
    const costValue = Number.parseInt(movieData.ban_cost, 10);
    const cost = Number.isFinite(costValue) ? `<div class="ban-meta">Стоимость: ${costValue}</div>` : '';

    return `
        <div class="ban-info">
            <div class="ban-header">⛔ Бан ${untilText} (${remaining})</div>
            ${appliedBy}
            ${cost}
        </div>
    `;
}

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

    const parsedPoints = Number(movieData.points);
    const pointsValue = Number.isFinite(parsedPoints) ? parsedPoints : 1;

    // Кнопка удаления из библиотеки или добавления в нее
    const libraryButtonHTML = isLibrary
        ? `<button class="danger-button modal-delete-btn">Удалить из библиотеки</button>`
        : `<button class="secondary-button add-library-modal-btn">Добавить в библиотеку</button>`;

    // Секция выбора бейджа (только для библиотеки)
    const badgeIcons = {
        'favorite': '⭐',
        'ban': '⛔',
        'watchlist': '👁️',
        'top': '🏆',
        'watched': '✅',
        'new': '🔥'
    };
    
    const badgeLabels = {
        'favorite': 'Любимое',
        'ban': 'Бан',
        'watchlist': 'Хочу посмотреть',
        'top': 'Топ',
        'watched': 'Просмотрено',
        'new': 'Новинка'
    };

    const badgeTypes = ['favorite', 'ban', 'watchlist', 'top', 'watched', 'new'];
    const currentBadge = movieData.badge || null;

    const badgeSectionHTML = isLibrary ? `
        <div class="movie-badge-section">
            <h4>Бейдж фильма</h4>
            <div class="badge-options-inline">
                ${badgeTypes.map(type => `
                    <div class="badge-option-inline ${currentBadge === type ? 'selected' : ''}" data-badge="${type}">
                        <span class="badge-icon">${badgeIcons[type]}</span>
                        <span class="badge-label">${badgeLabels[type]}</span>
                    </div>
                `).join('')}
            </div>
            ${currentBadge ? '<button class="secondary-button modal-remove-badge-btn" style="margin-top: 10px;">Убрать бейдж</button>' : ''}
        </div>
    ` : '';

    const pointsSectionHTML = isLibrary ? `
        <div class="movie-points-section">
            <h4>Баллы для фильма</h4>
            <div class="movie-points-form">
                <input type="number" id="movie-points-input" min="0" max="999" step="1" value="${escapeHtml(String(pointsValue))}">
                <button class="action-button save-points-btn" type="button">Сохранить</button>
            </div>
            <p class="movie-points-hint">По умолчанию каждому фильму присваивается 1 балл. Вы можете указать своё значение.</p>
        </div>
    ` : '';

    const parsedBanCostPerMonth = Number(movieData.ban_cost_per_month);
    const banCostPerMonthValue = Number.isFinite(parsedBanCostPerMonth) ? parsedBanCostPerMonth : null;
    const banCostPerMonthSectionHTML = isLibrary ? `
        <div class="movie-points-section">
            <h4>Цена за месяц исключения из опроса</h4>
            <div class="movie-points-form">
                <input type="number" id="movie-ban-cost-per-month-input" min="0" max="999" step="1" value="${banCostPerMonthValue !== null ? escapeHtml(String(banCostPerMonthValue)) : ''}" placeholder="По умолчанию: 1">
                <button class="action-button save-ban-cost-per-month-btn" type="button">Сохранить</button>
            </div>
            <p class="movie-points-hint">По умолчанию 1 балл за месяц. Вы можете указать своё значение.</p>
        </div>
    ` : '';

    const banSectionHTML = isLibrary ? renderBanInfo(movieData) : '';

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
                            <button class="action-button-rutracker search-rutracker-btn" title="Найти на RuTracker">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <circle cx="11" cy="11" r="8"></circle>
                                    <path d="m21 21-4.35-4.35"></path>
                                </svg>
                                RuTracker
                            </button>
                        </div>
                    </div>` : '<p class="meta-info">Kinopoisk ID не указан, работа с magnet-ссылкой недоступна.</p>'}

                ${pointsSectionHTML}
                ${banCostPerMonthSectionHTML}
                ${banSectionHTML}
                ${badgeSectionHTML}

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
        this.handlePopState = this.handlePopState.bind(this);

        this.closeButton.addEventListener('click', this.close);
        this.modal.addEventListener('click', this.handleOutsideClick);
    }

    open() {
        if (!modalStack.includes(this)) {
            modalStack.push(this);
        }
        this.modal.style.display = 'flex';
        if (modalStack.length === 1) {
            lockScroll();
        }
        this.body.innerHTML = '<div class="loader"></div>';

        window.addEventListener('popstate', this.handlePopState);
        history.pushState({ modal: true }, '', window.location.href);
    }

    close(options = {}) {
        const { fromPopState = false } = options;

        const stackIndex = modalStack.indexOf(this);
        const wasTopModal = stackIndex === modalStack.length - 1;

        if (stackIndex !== -1) {
            modalStack.splice(stackIndex, 1);
        }

        this.modal.style.display = 'none';
        this.body.innerHTML = '';

        window.removeEventListener('popstate', this.handlePopState);

        if (modalStack.length === 0) {
            unlockScroll();
        }

        if (wasTopModal && !fromPopState) {
            ignoreNextPopState = true;

            const clearIgnoreFlag = () => {
                consumeIgnoreFlag();
                window.removeEventListener('popstate', clearIgnoreFlag);
            };

            window.addEventListener('popstate', clearIgnoreFlag);
            history.back();
        }
    }

    handleOutsideClick(event) {
        if (event.target === this.modal) {
            this.close();
        }
    }

    handlePopState() {
        if (consumeIgnoreFlag()) {
            return;
        }

        const isTopModal = modalStack[modalStack.length - 1] === this;
        if (isTopModal) {
            this.close({ fromPopState: true });
        }
    }

    renderCustomContent(htmlContent) {
        this.body.innerHTML = htmlContent;
    }
    
    renderError(message) {
        this.body.innerHTML = `<p class="error-message">${escapeHtml(message)}</p>`;
    }

    /**
     * Рендерит содержимое модального окна ожидания результата лотереи.
     * @param {object} lotteryData - Данные лотереи.
     */
    renderWaitingModal(lotteryData = {}) {
        const playUrl = lotteryData.play_url || '';
        const telegramShareUrl = lotteryData.telegram_share_url || (playUrl
            ? `https://t.me/share/url?url=${encodeURIComponent(playUrl)}&text=${encodeURIComponent('Посмотри розыгрыш фильма!')}`
            : '');

        this.body.innerHTML = `
            <div class="waiting-modal">
                <h2>Розыгрыш еще не завершен</h2>
                <p class="waiting-status">Информация о победителе появится позже.</p>
                ${playUrl ? `
                    <div class="waiting-link-block">
                        <label for="waiting-play-url">Ссылка на розыгрыш:</label>
                        <div class="waiting-link-row">
                            <input type="text" id="waiting-play-url" class="waiting-play-url" value="${escapeHtml(playUrl)}" readonly>
                            <button type="button" class="action-button waiting-copy-btn">Скопировать</button>
                        </div>
                        <button type="button" class="secondary-button waiting-share-btn" data-share-url="${escapeHtml(telegramShareUrl)}"${telegramShareUrl ? '' : ' disabled'}>Поделиться в Telegram</button>
                    </div>
                ` : '<p class="waiting-status">Ссылка на розыгрыш недоступна.</p>'}
            </div>
        `;

        if (playUrl) {
            this.initializeWaitingActions(playUrl, telegramShareUrl);
        }
    }

    /**
     * Инициализирует обработчики действий в модальном окне ожидания.
     * @param {string} playUrl - Ссылка на страницу розыгрыша.
     * @param {string} telegramShareUrl - Ссылка для поделиться в Telegram.
     */
    initializeWaitingActions(playUrl, telegramShareUrl) {
        const copyBtn = this.body.querySelector('.waiting-copy-btn');
        if (copyBtn) {
            copyBtn.addEventListener('click', async () => {
                try {
                    await navigator.clipboard.writeText(playUrl);
                    if (typeof showToast === 'function') {
                        showToast('Ссылка скопирована в буфер обмена.', 'success');
                    }
                } catch (error) {
                    const input = this.body.querySelector('#waiting-play-url');
                    if (input && typeof input.select === 'function') {
                        input.select();
                        if (typeof document.execCommand === 'function') {
                            document.execCommand('copy');
                        }
                    }
                    if (typeof showToast === 'function') {
                        showToast('Не удалось автоматически скопировать ссылку. Скопируйте ее вручную.', 'error');
                    }
                }
            });
        }

        const shareBtn = this.body.querySelector('.waiting-share-btn');
        if (shareBtn && telegramShareUrl) {
            shareBtn.addEventListener('click', (event) => {
                event.preventDefault();
                window.open(telegramShareUrl, '_blank', 'noopener');
                if (typeof showToast === 'function') {
                    showToast('Открылось окно Telegram для отправки ссылки.', 'info');
                }
            });
        }
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

        // Кнопка "Найти на RuTracker"
        const searchRutrackerBtn = this.body.querySelector('.search-rutracker-btn');
        if (searchRutrackerBtn) {
            searchRutrackerBtn.addEventListener('click', () => {
                // Формируем поисковый запрос на английском: "Название год"
                const searchBase = movieData.search_name || movieData.name || '';
                const searchQuery = `${searchBase}${movieData.year ? ' ' + movieData.year : ''}`.trim();
                
                // Кодируем запрос для URL
                const encodedQuery = encodeURIComponent(searchQuery);
                
                // Формируем URL RuTracker (используем несколько зеркал)
                const rutrackerUrls = [
                    `https://rutracker.org/forum/tracker.php?nm=${encodedQuery}`,
                    `https://rutracker.net/forum/tracker.php?nm=${encodedQuery}`
                ];
                
                // Открываем первое зеркало в новой вкладке
                window.open(rutrackerUrls[0], '_blank');
                
                // Показываем уведомление
                if (window.showToast) {
                    window.showToast(`Открыт поиск на RuTracker: "${searchQuery}"`, 'info');
                }
            });
        }

        // Управление бейджами (только для библиотеки)
        const badgeOptions = this.body.querySelectorAll('.badge-option-inline');
        if (badgeOptions.length > 0 && actions.onSetBadge) {
            badgeOptions.forEach(option => {
                option.addEventListener('click', async () => {
                    const badgeType = option.dataset.badge;
                    await actions.onSetBadge(movieData.id, badgeType);
                });
            });
        }

        const savePointsBtn = this.body.querySelector('.save-points-btn');
        const pointsInput = this.body.querySelector('#movie-points-input');
        if (savePointsBtn && pointsInput && actions.onSavePoints) {
            const originalLabel = savePointsBtn.textContent;

            const handleSavePoints = async () => {
                const parsed = Number(pointsInput.value);
                if (!Number.isFinite(parsed)) {
                    if (window.showToast) {
                        window.showToast('Введите корректное число баллов.', 'error');
                    }
                    return;
                }

                savePointsBtn.disabled = true;
                savePointsBtn.textContent = 'Сохранение...';

                try {
                    await actions.onSavePoints(movieData.id, Math.round(parsed));
                } finally {
                    savePointsBtn.disabled = false;
                    savePointsBtn.textContent = originalLabel;
                }
            };

            savePointsBtn.addEventListener('click', (event) => {
                event.preventDefault();
                handleSavePoints();
            });

            pointsInput.addEventListener('keydown', (event) => {
                if (event.key === 'Enter') {
                    event.preventDefault();
                    handleSavePoints();
                }
            });
        }

        const saveBanCostPerMonthBtn = this.body.querySelector('.save-ban-cost-per-month-btn');
        const banCostPerMonthInput = this.body.querySelector('#movie-ban-cost-per-month-input');
        if (saveBanCostPerMonthBtn && banCostPerMonthInput && actions.onSaveBanCostPerMonth) {
            const originalLabel = saveBanCostPerMonthBtn.textContent;

            const handleSaveBanCostPerMonth = async () => {
                const value = banCostPerMonthInput.value.trim();
                let parsed = null;
                if (value !== '') {
                    parsed = Number(value);
                    if (!Number.isFinite(parsed)) {
                        if (window.showToast) {
                            window.showToast('Введите корректное число или оставьте пустым для значения по умолчанию.', 'error');
                        }
                        return;
                    }
                    parsed = Math.round(parsed);
                    if (parsed < 0 || parsed > 999) {
                        if (window.showToast) {
                            window.showToast('Цена должна быть в диапазоне от 0 до 999.', 'error');
                        }
                        return;
                    }
                    if (parsed === 0) {
                        parsed = null; // 0 означает сброс к значению по умолчанию
                    }
                }

                saveBanCostPerMonthBtn.disabled = true;
                saveBanCostPerMonthBtn.textContent = 'Сохранение...';

                try {
                    await actions.onSaveBanCostPerMonth(movieData.id, parsed);
                } finally {
                    saveBanCostPerMonthBtn.disabled = false;
                    saveBanCostPerMonthBtn.textContent = originalLabel;
                }
            };

            saveBanCostPerMonthBtn.addEventListener('click', (event) => {
                event.preventDefault();
                handleSaveBanCostPerMonth();
            });

            banCostPerMonthInput.addEventListener('keydown', (event) => {
                if (event.key === 'Enter') {
                    event.preventDefault();
                    handleSaveBanCostPerMonth();
                }
            });
        }

        const removeBadgeBtn = this.body.querySelector('.modal-remove-badge-btn');
        if (removeBadgeBtn && actions.onRemoveBadge) {
            removeBadgeBtn.addEventListener('click', async () => {
                await actions.onRemoveBadge(movieData.id);
            });
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