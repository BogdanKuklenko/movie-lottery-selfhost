// F:\GPT\movie-lottery V2\movie_lottery\static\js\pages\library.js

import { ModalManager, setModalCustomBadges } from '../components/modal.js';
import * as movieApi from '../api/movies.js';
import { downloadTorrentToClient, deleteTorrentFromClient } from '../api/torrents.js';
import { buildPollApiUrl, loadMyPolls } from '../utils/polls.js';
import { formatDate as formatVladivostokDate, formatDateTimeShort as formatVladivostokDateTime } from '../utils/timeFormat.js';

const escapeHtml = (unsafeValue) => {
    const value = unsafeValue == null ? '' : String(unsafeValue);
    return value
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
};

const parseMoviePoints = (value) => {
    const parsed = Number.parseInt(value, 10);
    if (Number.isNaN(parsed)) {
        return 1;
    }
    return Math.min(999, Math.max(0, parsed));
};

function formatDate(isoString) {
    return formatVladivostokDate(isoString);
}

function formatDateTime(isoString) {
    return formatVladivostokDateTime(isoString);
}

function formatDurationShort(seconds) {
    const totalSeconds = Math.max(0, Math.floor(seconds));
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const secs = totalSeconds % 60;
    return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

const BAN_STATE_POLL_INTERVAL_MS = 30000;

/**
 * Динамически переключает иконку "копировать"/"искать" на карточке.
 * @param {HTMLElement} card - Элемент карточки.
 * @param {boolean} hasMagnet - Есть ли magnet-ссылка.
 */
function toggleDownloadIcon(card, hasMagnet) {
    const actionButtons = card.querySelector('.action-buttons');
    if (!actionButtons) return;

    const copyButton = actionButtons.querySelector('.copy-magnet-button');
    const searchButton = actionButtons.querySelector('.search-rutracker-button');
    if (copyButton) copyButton.remove();
    if (searchButton) searchButton.remove();

    const newButton = document.createElement('button');
    newButton.type = 'button';
    
    if (hasMagnet) {
        newButton.className = 'icon-button copy-magnet-button';
        newButton.title = 'Скопировать magnet-ссылку';
        newButton.setAttribute('aria-label', 'Скопировать magnet-ссылку');
        newButton.innerHTML = `<svg class="icon-svg icon-copy" viewBox="0 0 24 24"><use href="#icon-copy"></use></svg>`;
    } else {
        newButton.className = 'icon-button search-rutracker-button';
        newButton.title = 'Найти на RuTracker';
        newButton.setAttribute('aria-label', 'Найти на RuTracker');
        newButton.innerHTML = `<svg class="icon-svg icon-search" viewBox="0 0 24 24"><use href="#icon-search"></use></svg>`;
    }
    
    actionButtons.prepend(newButton);
}

document.addEventListener('DOMContentLoaded', async () => {
    const gallery = document.querySelector('.library-gallery');
    const modalElement = document.getElementById('library-modal');

    if (!gallery || !modalElement) return;

    const modal = new ModalManager(modalElement);
    const closeModalIfOpen = () => {
        if (modalElement.style.display === 'flex') {
            modal.close();
        }
    };

    // --- Система уведомлений о запланированных фильмах ---
    const POSTPONE_OPTIONS = [
        { label: '1 час', minutes: 60 },
        { label: '3 часа', minutes: 180 },
        { label: '1 день', minutes: 1440 },
        { label: '3 дня', minutes: 4320 },
        { label: '1 неделя', minutes: 10080 }
    ];

    async function checkScheduleNotifications() {
        try {
            const response = await fetch('/api/schedules/notifications');
            const data = await response.json();
            
            if (data.success && data.notifications && data.notifications.length > 0) {
                // Показываем уведомления по очереди
                showScheduleNotification(data.notifications, 0);
            }
        } catch (error) {
            console.error('Ошибка проверки уведомлений:', error);
        }
    }

    function showScheduleNotification(notifications, index) {
        if (index >= notifications.length) return;
        
        const notification = notifications[index];
        const movie = notification.movie;
        if (!movie) {
            showScheduleNotification(notifications, index + 1);
            return;
        }
        
        const posterUrl = movie.poster_url || movie.poster || 'https://via.placeholder.com/150x225.png?text=?';
        const movieTitle = movie.name + (movie.year ? ` (${movie.year})` : '');
        const scheduledDate = new Date(notification.scheduled_date).toLocaleDateString('ru-RU', {
            day: 'numeric',
            month: 'long',
            year: 'numeric'
        });
        
        const postponeOptions = POSTPONE_OPTIONS.map(opt => 
            `<option value="${opt.minutes}">${opt.label}</option>`
        ).join('');
        
        const notificationHtml = `
            <div class="schedule-notification">
                <h2>🎬 Время смотреть!</h2>
                <div class="notification-movie">
                    <img src="${escapeHtml(posterUrl)}" alt="${escapeHtml(movie.name)}" class="notification-poster">
                    <div class="notification-info">
                        <h3>${escapeHtml(movieTitle)}</h3>
                        <p class="notification-date">Запланировано на: ${scheduledDate}</p>
                    </div>
                </div>
                <div class="notification-actions">
                    <div class="postpone-group">
                        <select id="postpone-select" class="postpone-select">
                            ${postponeOptions}
                        </select>
                        <button type="button" class="secondary-button postpone-btn" data-schedule-id="${notification.id}">
                            Отложить
                        </button>
                    </div>
                    <button type="button" class="cta-button confirm-btn" data-schedule-id="${notification.id}">
                        ✅ Просмотрено
                    </button>
                    <button type="button" class="danger-button-small dismiss-btn" data-schedule-id="${notification.id}">
                        Удалить
                    </button>
                </div>
                ${notifications.length > 1 ? `<p class="notification-counter">Уведомление ${index + 1} из ${notifications.length}</p>` : ''}
            </div>
        `;
        
        modal.open();
        modal.renderCustomContent(notificationHtml);
        
        const modalBody = modal.body;
        
        // Обработчик "Отложить"
        const postponeBtn = modalBody.querySelector('.postpone-btn');
        const postponeSelect = modalBody.querySelector('#postpone-select');
        if (postponeBtn && postponeSelect) {
            postponeBtn.addEventListener('click', async () => {
                const minutes = parseInt(postponeSelect.value, 10);
                const scheduleId = postponeBtn.dataset.scheduleId;
                
                postponeBtn.disabled = true;
                postponeBtn.textContent = 'Откладываем...';
                
                try {
                    const resp = await fetch(`/api/schedules/${scheduleId}/postpone`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ minutes })
                    });
                    const result = await resp.json();
                    
                    if (resp.ok) {
                        showToast(result.message || 'Уведомление отложено', 'success');
                        modal.close();
                        // Показываем следующее уведомление
                        setTimeout(() => showScheduleNotification(notifications, index + 1), 300);
                    } else {
                        showToast(result.message || 'Ошибка', 'error');
                        postponeBtn.disabled = false;
                        postponeBtn.textContent = 'Отложить';
                    }
                } catch (error) {
                    showToast('Ошибка при откладывании', 'error');
                    postponeBtn.disabled = false;
                    postponeBtn.textContent = 'Отложить';
                }
            });
        }
        
        // Обработчик "Просмотрено"
        const confirmBtn = modalBody.querySelector('.confirm-btn');
        if (confirmBtn) {
            confirmBtn.addEventListener('click', async () => {
                const scheduleId = confirmBtn.dataset.scheduleId;
                
                confirmBtn.disabled = true;
                confirmBtn.textContent = 'Подтверждаем...';
                
                try {
                    const resp = await fetch(`/api/schedules/${scheduleId}/confirm`, {
                        method: 'PUT'
                    });
                    const result = await resp.json();
                    
                    if (resp.ok) {
                        showToast('Просмотр подтверждён! 🎉', 'success');
                        modal.close();
                        // Показываем следующее уведомление
                        setTimeout(() => showScheduleNotification(notifications, index + 1), 300);
                    } else {
                        showToast(result.message || 'Ошибка', 'error');
                        confirmBtn.disabled = false;
                        confirmBtn.textContent = '✅ Просмотрено';
                    }
                } catch (error) {
                    showToast('Ошибка при подтверждении', 'error');
                    confirmBtn.disabled = false;
                    confirmBtn.textContent = '✅ Просмотрено';
                }
            });
        }
        
        // Обработчик "Удалить"
        const dismissBtn = modalBody.querySelector('.dismiss-btn');
        if (dismissBtn) {
            dismissBtn.addEventListener('click', async () => {
                const scheduleId = dismissBtn.dataset.scheduleId;
                
                dismissBtn.disabled = true;
                
                try {
                    const resp = await fetch(`/api/schedules/${scheduleId}`, {
                        method: 'DELETE'
                    });
                    const result = await resp.json();
                    
                    if (resp.ok) {
                        showToast('Таймер удалён', 'info');
                        modal.close();
                        // Показываем следующее уведомление
                        setTimeout(() => showScheduleNotification(notifications, index + 1), 300);
                    } else {
                        showToast(result.message || 'Ошибка', 'error');
                        dismissBtn.disabled = false;
                    }
                } catch (error) {
                    showToast('Ошибка при удалении', 'error');
                    dismissBtn.disabled = false;
                }
            });
        }
    }

    // Проверяем уведомления при загрузке страницы
    checkScheduleNotifications();

    // --- Функционал выбора фильмов и создания опросов ---
    const toggleSelectModeBtn = document.getElementById('toggle-select-mode-btn');
    const selectionPanel = document.getElementById('selection-panel');
    const selectionCount = document.getElementById('selection-count');
    const createPollBtn = document.getElementById('create-poll-from-selection-btn');
    const cancelSelectionBtn = document.getElementById('cancel-selection-btn');
    const myPollsBtn = document.getElementById('my-polls-btn');
    const myPollsBadge = document.getElementById('my-polls-badge');

    let selectionMode = false;
    let selectedMovies = new Set();

    const isCardBanned = (card) => {
        if (!card) return false;
        const status = card.dataset.banStatus || 'none';
        return status === 'active' || status === 'pending';
    };

    const enforceSelectionRestrictionsForCard = (card) => {
        if (!card) return;
        const checkbox = card.querySelector('.movie-checkbox');
        if (!checkbox) return;

        const banned = isCardBanned(card);
        checkbox.disabled = banned;

        if (banned && checkbox.checked) {
            checkbox.checked = false;
            selectedMovies.delete(card.dataset.movieId);
        }

        card.classList.toggle('selection-blocked', selectionMode && banned);

        if (selectionMode) {
            updateSelectionUI();
        }
    };

    const enforceSelectionRestrictionsForAll = () => {
        document.querySelectorAll('.library-card').forEach(card => enforceSelectionRestrictionsForCard(card));
        updateSelectionUI();
    };

    // Проверяем и загружаем "Мои опросы"
    const refreshMyPolls = () => loadMyPolls({
        myPollsButton: myPollsBtn,
        myPollsBadgeElement: myPollsBadge,
    });
    await refreshMyPolls();

    function toggleSelectionMode() {
        selectionMode = !selectionMode;
        selectedMovies.clear();
        updateSelectionUI();

        const checkboxes = document.querySelectorAll('.movie-checkbox');
        checkboxes.forEach(cb => {
            cb.style.display = selectionMode ? 'block' : 'none';
            cb.checked = false;
        });

        enforceSelectionRestrictionsForAll();

        if (selectionMode) {
            toggleSelectModeBtn.textContent = 'Отменить выбор';
            selectionPanel.style.display = 'flex';
            gallery.classList.add('selection-mode');
        } else {
            toggleSelectModeBtn.textContent = 'Выбрать фильмы';
            selectionPanel.style.display = 'none';
            gallery.classList.remove('selection-mode');
        }
    }

    function updateSelectionUI() {
        selectionCount.textContent = `Выбрано: ${selectedMovies.size}`;
        createPollBtn.disabled = selectedMovies.size < 2 || selectedMovies.size > 25;
    }

    toggleSelectModeBtn.addEventListener('click', toggleSelectionMode);
    cancelSelectionBtn.addEventListener('click', toggleSelectionMode);

    // Обработка выбора фильмов через чекбоксы
    gallery.addEventListener('change', (e) => {
        if (e.target.classList.contains('movie-checkbox')) {
            const movieId = e.target.dataset.movieId;
            if (e.target.checked) {
                selectedMovies.add(movieId);
            } else {
                selectedMovies.delete(movieId);
            }
            updateSelectionUI();
        }
    });

    // Создание опроса из выбранных фильмов
    createPollBtn.addEventListener('click', async () => {
        if (selectedMovies.size < 2 || selectedMovies.size > 25) return;

        createPollBtn.disabled = true;
        createPollBtn.textContent = 'Создание...';

        const moviesData = [];
        selectedMovies.forEach(movieId => {
            const card = document.querySelector(`[data-movie-id="${movieId}"]`);
            if (card) {
                moviesData.push({
                    kinopoisk_id: card.dataset.kinopoiskId || null,
                    name: card.dataset.movieName,
                    search_name: card.dataset.movieSearchName || null,
                    poster: card.dataset.moviePoster || null,
                    year: card.dataset.movieYear || null,
                    description: card.dataset.movieDescription || null,
                    rating_kp: card.dataset.movieRating ? parseFloat(card.dataset.movieRating) : null,
                    genres: card.dataset.movieGenres || null,
                    countries: card.dataset.movieCountries || null,
                    points: parseMoviePoints(card.dataset.moviePoints),
                });
            }
        });

        try {
            const response = await fetch(buildPollApiUrl('/api/polls/create'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ movies: moviesData }),
                credentials: 'include'
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Не удалось создать опрос');
            }

            // Показываем модальное окно с результатом
            showPollCreatedModal({
                pollUrl: data.poll_url,
                resultsUrl: data.results_url,
            });

            // Сбрасываем выбор
            toggleSelectionMode();

            // Обновляем кнопку "Мои опросы"
            await refreshMyPolls();

        } catch (error) {
            showToast(error.message, 'error');
            createPollBtn.disabled = false;
            createPollBtn.textContent = 'Создать опрос';
        }
    });

    function showPollCreatedModal({ pollUrl, resultsUrl }) {
        const modalContent = `
            <h2>Опрос создан!</h2>
            <p>Поделитесь этой ссылкой с друзьями:</p>
            <div class="link-box">
                <input type="text" id="poll-share-link" value="${escapeHtml(pollUrl)}" readonly>
                <button class="copy-btn" data-copy-target="poll-share-link">Копировать</button>
            </div>
            <p class="poll-info">Сохраните ссылку на страницу результатов — по ней любой участник сможет открыть текущее распределение голосов.</p>
            <div class="link-box">
                <input type="text" id="poll-results-link" value="${escapeHtml(resultsUrl || '')}" readonly>
                <button class="copy-btn" data-copy-target="poll-results-link">Копировать</button>
            </div>
            ${resultsUrl ? `<a href="${escapeHtml(resultsUrl)}" class="secondary-button" target="_blank" rel="noopener">Открыть страницу результатов</a>` : ''}
            <a href="https://t.me/share/url?url=${encodeURIComponent(pollUrl)}&text=${encodeURIComponent('Приглашаю принять участие в опросе')}"
               class="action-button-tg" target="_blank">
                Поделиться в Telegram
            </a>
            <p class="poll-info">Результаты появятся в "Мои опросы" после первого голоса</p>
        `;
        const isModalOpen = modalElement.style.display === 'flex';

        if (!isModalOpen) {
            modal.open();
        }

        modal.renderCustomContent(modalContent);

        const modalBody = modal.body;
        if (!modalBody) return;

        modalBody.querySelectorAll('a[target="_blank"]').forEach((link) => {
            link.addEventListener('click', closeModalIfOpen);
        });

        modalBody.querySelectorAll('.copy-btn').forEach((button) => {
            button.addEventListener('click', async () => {
                const targetId = button.getAttribute('data-copy-target');
                const input = modalBody.querySelector(`#${targetId}`);
                if (!input || !input.value) return;

                try {
                    // Современный способ копирования через Clipboard API
                    await navigator.clipboard.writeText(input.value);
                    showToast('Ссылка скопирована!', 'success');
                } catch {
                    // Fallback для старых браузеров
                    input.select();
                    input.setSelectionRange(0, input.value.length);
                    try {
                        document.execCommand('copy');
                        showToast('Ссылка скопирована!', 'success');
                    } catch {
                        showToast('Не удалось скопировать ссылку', 'error');
                    }
                }
            });
        });
    }

    myPollsBtn.addEventListener('click', () => {
        showMyPollsModal();
    });

    async function showMyPollsModal() {
        const allPolls = await refreshMyPolls();

        if (allPolls.length === 0) {
            modal.open();
            modal.renderCustomContent('<h2>Мои опросы</h2><p>У вас пока нет активных опросов с голосами.</p>');
            return;
        }

        // Сортируем по дате создания (новые первые)
        allPolls.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

        let pollsHtml = '<h2>Мои опросы</h2>';
        
        allPolls.forEach(poll => {
            const createdDate = formatVladivostokDateTime(poll.created_at);
            const expiresDate = poll.expires_at ? formatVladivostokDateTime(poll.expires_at) : '';
            const primaryWinner = poll.winners[0] || {};
            const winnerNameAttr = escapeHtml(primaryWinner.name || '');
            const winnerYearAttr = escapeHtml(primaryWinner.year || '');
            const winnerSearchNameAttr = escapeHtml(primaryWinner.search_name || '');
            const winnerCountriesAttr = escapeHtml(primaryWinner.countries || '');
            const isExpired = Boolean(poll.is_expired);
            const statusBadge = isExpired
                ? '<span class="poll-status poll-status-expired">Опрос завершён</span>'
                : '<span class="poll-status poll-status-active">Опрос активен</span>';
            const winnersHtml = poll.winners.map(w => `
                <div class="poll-winner">
                    <img src="${w.poster || 'https://via.placeholder.com/100x150.png?text=No+Image'}" alt="${w.name}">
                    <div class="poll-winner-info">
                        <h4>${w.name}</h4>
                        <p>${w.year || ''}</p>
                        <p class="vote-count">Голосов: ${w.votes}</p>
                    </div>
                </div>
            `).join('');

            const bannedMovies = poll.banned_movies || [];
            const bannedHtml = bannedMovies.length > 0 ? `
                <div class="poll-banned-movies">
                    <p class="poll-banned-title">Забаненные фильмы:</p>
                    ${bannedMovies.map(m => {
                        const banUntilText = m.ban_until ? ` до ${formatVladivostokDateTime(m.ban_until)}` : '';
                        return `
                            <div class="poll-banned-item">
                                <img src="${m.poster || 'https://via.placeholder.com/40x60.png?text=No'}" alt="${escapeHtml(m.name)}">
                                <div class="poll-banned-info">
                                    <span class="poll-banned-name">${escapeHtml(m.name)}</span>
                                    ${m.year ? `<span class="poll-banned-year">${escapeHtml(m.year)}</span>` : ''}
                                    <span class="poll-banned-badge">Забанен${banUntilText}</span>
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
            ` : '';

            pollsHtml += `
                <div class="poll-result-item">
                    <div class="poll-result-header">
                        <div class="poll-result-header-row">
                            <h3>Опрос от ${createdDate}</h3>
                            ${statusBadge}
                        </div>
                        <p>
                            Всего голосов: ${poll.total_votes} | Фильмов: ${poll.movies_count}
                            ${expiresDate ? `| Действует до: ${expiresDate}` : ''}
                        </p>
                    </div>
                    <div class="poll-winners">
                        ${poll.winners.length > 1 ? '<p><strong>Победители (равное количество голосов):</strong></p>' : '<p><strong>Победитель:</strong></p>'}
                        ${winnersHtml}
                    </div>
                    ${bannedHtml}
                    ${poll.winners.length > 1 ? `
                        <button class="secondary-button create-poll-from-winners" data-winners='${JSON.stringify(poll.winners)}'>
                            Создать опрос из победителей
                        </button>
                    ` : ''}
                    <div class="poll-actions">
                        <button class="secondary-button search-winner-btn" data-movie-name="${winnerNameAttr}" data-movie-year="${winnerYearAttr}" data-movie-search-name="${winnerSearchNameAttr}" data-movie-countries="${winnerCountriesAttr}">
                            Найти на RuTracker
                        </button>
                        <a href="${poll.poll_url}" class="secondary-button" target="_blank">Открыть опрос</a>
                        ${poll.results_url ? `<a href="${poll.results_url}" class="secondary-button" target="_blank" rel="noopener">Результаты</a>` : ''}
                    </div>
                    <a href="https://t.me/share/url?url=${encodeURIComponent(poll.poll_url)}&text=${encodeURIComponent('Приглашаю принять участие в опросе')}"
                       class="action-button-tg" target="_blank">
                        Поделиться в Telegram
                    </a>
                </div>
            `;
        });

        modal.open();
        modal.renderCustomContent(pollsHtml);

        const modalBody = modal.body;
        if (modalBody) {
            modalBody.querySelectorAll('.poll-result-item a').forEach(link => {
                link.addEventListener('click', closeModalIfOpen);
            });
        }

        // Отмечаем все опросы как просмотренные
        const viewedPolls = JSON.parse(localStorage.getItem('viewedPolls') || '{}');
        allPolls.forEach(poll => {
            viewedPolls[poll.poll_id] = true;
        });
        localStorage.setItem('viewedPolls', JSON.stringify(viewedPolls));

        // Скрываем индикатор
        myPollsBadge.style.display = 'none';

        // Добавляем обработчики для кнопок RuTracker
        document.querySelectorAll('.search-winner-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const movieName = e.target.dataset.movieName;
                const movieYear = e.target.dataset.movieYear;
                const movieSearchName = e.target.dataset.movieSearchName;
                const movieCountries = e.target.dataset.movieCountries || '';
                // Определяем, русский ли это контент (Россия или СССР)
                const countries = movieCountries.toLowerCase();
                const isRussian = countries.includes('россия') || countries.includes('ссср');
                // Для русского контента — русское название, для иностранного — английское (если есть)
                const searchQuery = isRussian
                    ? `${movieName || movieSearchName}${movieYear ? ' ' + movieYear : ''}`
                    : `${movieSearchName || movieName}${movieYear ? ' ' + movieYear : ''}`;
                const encodedQuery = encodeURIComponent(searchQuery);
                const rutrackerUrl = `https://rutracker.net/forum/tracker.php?nm=${encodedQuery}`;
                closeModalIfOpen();
                window.open(rutrackerUrl, '_blank');
                showToast(`Открыт поиск на RuTracker: "${searchQuery}"`, 'info');
            });
        });

        // Обработчик для создания опроса из победителей
        document.querySelectorAll('.create-poll-from-winners').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const winners = JSON.parse(e.target.dataset.winners);

                btn.disabled = true;
                btn.textContent = 'Создание...';
                let reopenedWithResult = false;

                try {
                    const response = await fetch(buildPollApiUrl('/api/polls/create'), {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ movies: winners }),
                        credentials: 'include'
                    });

                    const data = await response.json();

                    if (!response.ok) {
                        throw new Error(data.error || 'Не удалось создать опрос');
                    }

                    closeModalIfOpen();
                    reopenedWithResult = true;

                    showPollCreatedModal({
                        pollUrl: data.poll_url,
                        resultsUrl: data.results_url,
                    });
                    await refreshMyPolls();

                } catch (error) {
                    showToast(error.message, 'error');
                } finally {
                    btn.disabled = false;
                    btn.textContent = 'Создать опрос из победителей';
                    if (!reopenedWithResult) {
                        closeModalIfOpen();
                    }
                }
            });
        });
    }

    // Периодически проверяем новые результаты опросов
    setInterval(refreshMyPolls, 10000); // Каждые 10 секунд

    // --- Конец функционала опросов ---

    // --- Функционал "Опрос по бейджу" ---
    const badgePollBtn = document.getElementById('badge-poll-btn');
    const badgePollDropdown = document.querySelector('.badge-poll-dropdown');
    const badgePollMenu = document.getElementById('badge-poll-menu');
    const badgePollOptions = document.querySelectorAll('.badge-poll-option');

    // Загружаем статистику по бейджам
    async function loadBadgeStats() {
        try {
            const response = await fetch('/api/library/badges/stats');
            if (!response.ok) throw new Error('Не удалось загрузить статистику');
            
            const stats = await response.json();
            
            // Обновляем счетчики и состояние кнопок (стандартные бейджи)
            badgePollOptions.forEach(option => {
                const badgeType = option.dataset.badge;
                const count = stats[badgeType] || 0;
                const countElement = option.querySelector('.badge-count');
                if (countElement) {
                    countElement.textContent = `(${count})`;
                }
                
                // Активируем только если фильмов >= 2
                option.disabled = count < 2;
            });

            // Обновляем счетчики для кастомных бейджей в меню опросов
            const customPollContainer = document.getElementById('badge-poll-custom-badges');
            if (customPollContainer) {
                customPollContainer.querySelectorAll('.badge-poll-option-custom').forEach(option => {
                    const badgeType = option.dataset.badge;
                    const count = stats[badgeType] || 0;
                    const countElement = option.querySelector('.badge-count');
                    if (countElement) {
                        countElement.textContent = `(${count})`;
                    }
                    option.disabled = count < 2;
                });
            }
        } catch (error) {
            console.error('Ошибка загрузки статистики бейджей:', error);
        }
    }

    // Загружаем статистику при загрузке страницы
    loadBadgeStats();

    // Открытие/закрытие выпадающего меню
    badgePollBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        badgePollDropdown.classList.toggle('active');
        loadBadgeStats(); // Обновляем статистику при открытии
    });

    // Закрытие при клике вне меню
    document.addEventListener('click', (e) => {
        if (!badgePollDropdown.contains(e.target)) {
            badgePollDropdown.classList.remove('active');
        }
    });

    // Создание опроса по бейджу
    badgePollOptions.forEach(option => {
        option.addEventListener('click', async (e) => {
            e.preventDefault();
            if (option.disabled) return;

            const badgeType = option.dataset.badge;
            const badgeName = option.querySelector('.badge-name').textContent;
            const badgeIcon = option.querySelector('.badge-icon').textContent;

            // Закрываем меню
            badgePollDropdown.classList.remove('active');

            // Показываем модальное окно подтверждения
            const confirmHtml = `
                <h2>Создать опрос по бейджу</h2>
                <div style="text-align: center; margin: 20px 0;">
                    <span style="font-size: 48px;">${badgeIcon}</span>
                    <h3 style="margin: 10px 0;">${badgeName}</h3>
                </div>
                <p>Вы действительно хотите создать опрос со всеми фильмами, имеющими бейдж "${badgeName}"?</p>
                <p style="font-size: 14px; color: #adb5bd; margin-top: 10px;">
                    Опрос будет доступен друзьям по ссылке в течение 24 часов.
                </p>
                <div style="display: flex; gap: 10px; margin-top: 20px;">
                    <button class="secondary-button" id="cancel-badge-poll" style="flex: 1; padding: 15px; margin: 0;">Отмена</button>
                    <button class="cta-button" id="confirm-badge-poll" style="flex: 1; padding: 15px; margin: 0;">Создать опрос</button>
                </div>
            `;

            modal.open();
            modal.renderCustomContent(confirmHtml);

            // Обработка кнопок подтверждения
            const confirmBtn = document.getElementById('confirm-badge-poll');
            const cancelBtn = document.getElementById('cancel-badge-poll');

            cancelBtn.addEventListener('click', () => {
                modal.close();
            });

            confirmBtn.addEventListener('click', async () => {
                confirmBtn.disabled = true;
                confirmBtn.textContent = 'Создание...';

                try {
                    // Получаем фильмы с выбранным бейджем
                    const response = await fetch(`/api/library/badges/${badgeType}/movies`);
                    const data = await response.json();

                    if (!response.ok) {
                        throw new Error(data.error || 'Не удалось получить фильмы');
                    }

                    // Показываем уведомление, если список был ограничен до 25
                    if (data.limited) {
                        showToast(`Внимание: в опрос добавлены только первые 25 фильмов из ${data.total}`, 'warning');
                    }

                    // Создаём опрос
                    const createResponse = await fetch(buildPollApiUrl('/api/polls/create'), {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ movies: data.movies }),
                        credentials: 'include'
                    });

                    const createData = await createResponse.json();

                    if (!createResponse.ok) {
                        throw new Error(createData.error || 'Не удалось создать опрос');
                    }

                    showPollCreatedModal({
                        pollUrl: createData.poll_url,
                        resultsUrl: createData.results_url,
                    });

                    // Обновляем кнопку "Мои опросы"
                    await refreshMyPolls();

                    showToast(`Опрос "${badgeName}" успешно создан!`, 'success');

                } catch (error) {
                    showToast(error.message, 'error');
                } finally {
                    confirmBtn.disabled = false;
                    confirmBtn.textContent = 'Создать опрос';
                }
            });
        });
    });

    // --- Конец функционала "Опрос по бейджу" ---

    // --- Функционал фильтрации по бейджам ---
    const badgeFilters = document.querySelectorAll('.badge-filter');
    let currentFilter = 'all';

    // Обновляем счетчики фильтров
    async function updateBadgeFilterStats() {
        try {
            const response = await fetch('/api/library/badges/stats');
            if (!response.ok) throw new Error('Не удалось загрузить статистику');
            
            const stats = await response.json();
            
            // Подсчитываем общее количество фильмов и фильмы без бейджа
            const allCards = document.querySelectorAll('.library-card');
            const totalMovies = allCards.length;
            
            let moviesWithBadges = 0;
            Object.values(stats).forEach(count => {
                moviesWithBadges += count;
            });
            
            const noBadgeCount = totalMovies - moviesWithBadges;
            
            // Обновляем счетчики (стандартные фильтры)
            badgeFilters.forEach(filter => {
                const badgeType = filter.dataset.badge;
                const countElement = filter.querySelector('.badge-filter-count');
                
                if (countElement) {
                    let count = 0;
                    if (badgeType === 'all') {
                        count = totalMovies;
                    } else if (badgeType === 'none') {
                        count = noBadgeCount;
                    } else {
                        count = stats[badgeType] || 0;
                    }
                    countElement.textContent = `(${count})`;
                }
            });

            // Обновляем счетчики для кастомных фильтров
            const customFiltersContainer = document.getElementById('badge-filters-custom-container');
            if (customFiltersContainer) {
                customFiltersContainer.querySelectorAll('.badge-filter').forEach(filter => {
                    const badgeType = filter.dataset.badge;
                    const countElement = filter.querySelector('.badge-filter-count');
                    if (countElement) {
                        const count = stats[badgeType] || 0;
                        countElement.textContent = `(${count})`;
                    }
                });
            }
        } catch (error) {
            console.error('Ошибка загрузки статистики фильтров:', error);
        }
    }

    // Фильтрация карточек фильмов
    function applyBadgeFilter(filterType) {
        currentFilter = filterType;
        const allCards = document.querySelectorAll('.library-card');
        let visibleCount = 0;
        
        allCards.forEach(card => {
            const cardBadge = card.dataset.badge || '';
            let shouldShow = false;
            
            if (filterType === 'all') {
                shouldShow = true;
            } else if (filterType === 'none') {
                shouldShow = cardBadge === '';
            } else {
                shouldShow = cardBadge === filterType;
            }
            
            if (shouldShow) {
                card.style.display = '';
                visibleCount++;
            } else {
                card.style.display = 'none';
            }
        });
        
        // Показываем/скрываем сообщение о пустой библиотеке
        const emptyMessage = document.querySelector('.library-empty-message');
        if (emptyMessage) {
            emptyMessage.style.display = visibleCount === 0 ? 'block' : 'none';
            if (visibleCount === 0 && filterType !== 'all') {
                emptyMessage.textContent = 'Фильмов с выбранным бейджем не найдено.';
            } else if (visibleCount === 0) {
                emptyMessage.textContent = 'В библиотеке пока нет фильмов.';
            }
        }
    }

    // Обработчики кликов на фильтры
    badgeFilters.forEach(filter => {
        filter.addEventListener('click', () => {
            const filterType = filter.dataset.badge;
            
            // Обновляем активное состояние
            badgeFilters.forEach(f => f.classList.remove('active'));
            // Снимаем active с кастомных фильтров
            const customFiltersContainer = document.getElementById('badge-filters-custom-container');
            if (customFiltersContainer) {
                customFiltersContainer.querySelectorAll('.badge-filter').forEach(f => f.classList.remove('active'));
            }
            filter.classList.add('active');
            
            // Применяем фильтр
            applyBadgeFilter(filterType);
        });
    });

    // Загружаем статистику фильтров при загрузке страницы
    updateBadgeFilterStats();

    // --- Конец функционала фильтрации по бейджам ---

    // --- Функционал быстрого просмотра постера ---
    let posterPreviewOverlay = null;
    let isLongPress = false;
    let longPressTimer = null;
    let currentPreviewCard = null;
    const LONG_PRESS_DURATION = 300; // мс для определения длинного нажатия

    function createPosterPreview(posterUrl) {
        // Создаем overlay если его еще нет
        if (!posterPreviewOverlay) {
            posterPreviewOverlay = document.createElement('div');
            posterPreviewOverlay.className = 'poster-preview-overlay';
            document.body.appendChild(posterPreviewOverlay);
        }

        // Создаем изображение
        const img = document.createElement('img');
        img.className = 'poster-preview-image';
        img.src = posterUrl;
        img.alt = 'Постер фильма';

        // Очищаем и добавляем новое изображение
        posterPreviewOverlay.innerHTML = '';
        posterPreviewOverlay.appendChild(img);

        // Показываем overlay
        requestAnimationFrame(() => {
            posterPreviewOverlay.classList.add('active');
        });
    }

    function closePosterPreview() {
        if (posterPreviewOverlay && posterPreviewOverlay.classList.contains('active')) {
            posterPreviewOverlay.classList.remove('active');
            // Удаляем содержимое после анимации
            setTimeout(() => {
                if (posterPreviewOverlay) {
                    posterPreviewOverlay.innerHTML = '';
                }
            }, 200);
        }
        isLongPress = false;
        currentPreviewCard = null;
        if (longPressTimer) {
            clearTimeout(longPressTimer);
            longPressTimer = null;
        }
    }

    // Обработчик для карточек фильмов
    function initPosterPreview() {
        const movieCards = document.querySelectorAll('.library-card');

        movieCards.forEach(card => {
            const img = card.querySelector('img');
            if (!img) return;

            // Удаляем старые обработчики если есть
            img.removeEventListener('mousedown', img._posterMouseDown);
            img.removeEventListener('mouseup', img._posterMouseUp);
            img.removeEventListener('mouseleave', img._posterMouseLeave);
            img.removeEventListener('dragstart', img._posterDragStart);

            // Блокируем перетаскивание постера
            img.setAttribute('draggable', 'false');
            img._posterDragStart = (e) => e.preventDefault();

            // Mousedown - начинаем отсчет для длинного нажатия
            img._posterMouseDown = (e) => {
                // Только левая кнопка мыши
                if (e.button !== 0) return;
                
                const posterUrl = card.dataset.moviePoster;
                if (!posterUrl || posterUrl === 'https://via.placeholder.com/200x300.png?text=No+Image') {
                    return; // Позволяем обычному клику работать
                }

                currentPreviewCard = card;
                
                // Запускаем таймер для длинного нажатия
                longPressTimer = setTimeout(() => {
                    isLongPress = true;
                    createPosterPreview(posterUrl);
                    // Предотвращаем клик только при длинном нажатии
                    e.preventDefault();
                }, LONG_PRESS_DURATION);
            };

            // Mouseup - отменяем или закрываем
            img._posterMouseUp = (e) => {
                if (longPressTimer) {
                    clearTimeout(longPressTimer);
                    longPressTimer = null;
                }

                if (isLongPress) {
                    e.preventDefault();
                    e.stopPropagation();
                    closePosterPreview();
                }
                // Если не было длинного нажатия - позволяем обычному клику сработать
            };

            // Mouseleave - отменяем превью только если еще не было длинного нажатия
            img._posterMouseLeave = () => {
                if (longPressTimer) {
                    clearTimeout(longPressTimer);
                    longPressTimer = null;
                }
                // Не закрываем превью, если оно уже открыто (isLongPress = true)
                // Превью будет закрыто только при mouseup
            };

            img.addEventListener('mousedown', img._posterMouseDown);
            img.addEventListener('mouseup', img._posterMouseUp);
            img.addEventListener('mouseleave', img._posterMouseLeave);
            img.addEventListener('dragstart', img._posterDragStart);
        });
    }

    // Глобальные обработчики для закрытия превью
    document.addEventListener('mouseup', (e) => {
        if (isLongPress && e.button === 0) {
            e.preventDefault();
            closePosterPreview();
        }
    });

    // Инициализируем при загрузке
    initPosterPreview();

    // Переинициализируем после изменений в DOM (например, после удаления фильма)
    const originalToggleDownloadIcon = toggleDownloadIcon;
    window.toggleDownloadIcon = function(...args) {
        originalToggleDownloadIcon(...args);
        // Небольшая задержка для обновления DOM
        setTimeout(initPosterPreview, 100);
    };

    // --- Конец функционала быстрого просмотра постера ---

    function getBanRemainingSeconds(card) {
        if (!card) return 0;
        if (card.dataset.banUntil) {
            const untilMs = new Date(card.dataset.banUntil).getTime();
            return Math.max(0, Math.floor((untilMs - Date.now()) / 1000));
        }

        const raw = Number.parseInt(card.dataset.banRemaining || '0', 10);
        if (Number.isNaN(raw)) return 0;
        return Math.max(0, raw);
    }

    function renderBanStatus(card) {
        if (!card) return;

        const status = card.dataset.banStatus || 'none';
        let overlay = card.querySelector('.ban-overlay');
        let pill = card.querySelector('.ban-status-chip');

        if (status !== 'active' && status !== 'pending') {
            if (overlay) overlay.remove();
            if (pill) pill.remove();
            card.classList.remove('is-banned');
            return;
        }

        if (!overlay) {
            overlay = document.createElement('div');
            overlay.className = 'ban-overlay';
            overlay.innerHTML = `
                <div class="ban-overlay-content">
                    <span class="ban-overlay-badge">ban</span>
                    <span class="ban-overlay-timer"></span>
                </div>
            `;
            card.appendChild(overlay);
        }

        const timerEl = overlay.querySelector('.ban-overlay-timer');
        const remaining = getBanRemainingSeconds(card);
        if (status === 'active') {
            card.dataset.banRemaining = String(remaining);
            timerEl.textContent = formatDurationShort(remaining);
        } else {
            timerEl.textContent = '∞';
        }

        if (pill) {
            pill.remove();
        }

        overlay.classList.add('visible');
        card.classList.add('is-banned');
    }

    function updateTrailerVisuals(card) {
        if (!card) return;
        const hasTrailer = card.dataset.hasLocalTrailer === 'true';
        const trailerButton = card.querySelector('.trailer-button');
        const trailerPill = card.querySelector('.trailer-pill');

        if (trailerButton) {
            const label = hasTrailer ? 'Изменить трейлер' : 'Добавить трейлер';
            trailerButton.textContent = label;
            trailerButton.title = label;
            trailerButton.setAttribute('aria-label', label);
        }

        if (trailerPill) {
            trailerPill.style.display = hasTrailer ? 'block' : 'none';
        }
    }

    function applyApiMovieDataToCard(card, movieData) {
        if (!card || !movieData) return false;
        const previousBadge = card.dataset.badge || '';

        card.dataset.moviePoints = movieData.points != null ? String(movieData.points) : card.dataset.moviePoints;
        card.dataset.badge = movieData.badge || '';
        card.dataset.banStatus = movieData.ban_status || 'none';
        card.dataset.banUntil = movieData.ban_until || '';
        card.dataset.banRemaining = (movieData.ban_remaining_seconds ?? '').toString();
        card.dataset.banAppliedBy = movieData.ban_applied_by || '';
        card.dataset.banCost = movieData.ban_cost != null ? movieData.ban_cost.toString() : '';
        // Если ban_cost_per_month null или undefined, не устанавливаем data-атрибут (будет использоваться значение по умолчанию 1)
        if (movieData.ban_cost_per_month != null && movieData.ban_cost_per_month !== undefined) {
            card.dataset.banCostPerMonth = movieData.ban_cost_per_month.toString();
        } else {
            delete card.dataset.banCostPerMonth;
        }

        if (Object.prototype.hasOwnProperty.call(movieData, 'has_magnet')) {
            card.dataset.hasMagnet = movieData.has_magnet ? 'true' : 'false';
            toggleDownloadIcon(card, movieData.has_magnet);
        }
        if (Object.prototype.hasOwnProperty.call(movieData, 'magnet_link')) {
            card.dataset.magnetLink = movieData.magnet_link || '';
        }
        if (Object.prototype.hasOwnProperty.call(movieData, 'torrent_hash')) {
            card.dataset.torrentHash = movieData.torrent_hash || '';
        }

        if (Object.prototype.hasOwnProperty.call(movieData, 'has_local_trailer')) {
            card.dataset.hasLocalTrailer = movieData.has_local_trailer ? 'true' : 'false';
            updateTrailerVisuals(card);
        }

        if (Object.prototype.hasOwnProperty.call(movieData, 'trailer_view_cost')) {
            if (movieData.trailer_view_cost != null && movieData.trailer_view_cost !== undefined) {
                card.dataset.trailerViewCost = movieData.trailer_view_cost.toString();
            } else {
                delete card.dataset.trailerViewCost;
            }
        }

        updateBadgeOnCard(card, movieData.badge || null, movieData, { skipStats: true });
        enforceSelectionRestrictionsForCard(card);
        return previousBadge !== (movieData.badge || '');
    }

    async function refreshLibraryData({ silent = false } = {}) {
        try {
            const movies = await movieApi.loadLibraryMovies();
            let shouldRefreshFilters = false;
            movies.forEach(movie => {
                const card = document.querySelector(`[data-movie-id="${movie.id}"]`);
                if (card) {
                    const badgeChanged = applyApiMovieDataToCard(card, movie);
                    shouldRefreshFilters = shouldRefreshFilters || badgeChanged;
                }
            });

            if (shouldRefreshFilters) {
                updateBadgeFilterStats();
                applyBadgeFilter(currentFilter);
            } else {
                document.querySelectorAll('.library-card').forEach(renderBanStatus);
            }
        } catch (error) {
            if (!silent) {
                console.error('Не удалось обновить библиотеку:', error);
                showToast('Не удалось обновить данные библиотеки', 'error');
            }
        }
    }

    function updateBanTimers() {
        let needsServerRefresh = false;

        document.querySelectorAll('.gallery-item').forEach(card => {
            const status = card.dataset.banStatus || 'none';

            if (status === 'active') {
                const remaining = getBanRemainingSeconds(card);
                card.dataset.banRemaining = String(remaining);
                if (remaining <= 0) {
                    needsServerRefresh = true;
                }
            }

            renderBanStatus(card);
        });

        if (needsServerRefresh) {
            refreshLibraryData({ silent: true });
        }
    }

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
            badge: ds.badge || null,
            points: parseMoviePoints(ds.moviePoints),
            ban_status: ds.banStatus || 'none',
            ban_until: ds.banUntil || null,
            ban_remaining_seconds: Number.parseInt(ds.banRemaining || '0', 10) || 0,
            ban_applied_by: ds.banAppliedBy || '',
            ban_cost: ds.banCost ? Number.parseInt(ds.banCost, 10) : null,
            ban_cost_per_month: ds.banCostPerMonth ? Number.parseInt(ds.banCostPerMonth, 10) : null,
            has_local_trailer: ds.hasLocalTrailer === 'true',
            trailer_view_cost: ds.trailerViewCost ? Number.parseInt(ds.trailerViewCost, 10) : null,
        };
    };

    // --- Функционал управления бейджами ---
    const badgeModal = document.getElementById('badge-selector-modal');
    const badgeOptions = badgeModal.querySelectorAll('.badge-option');
    const removeBadgeBtn = badgeModal.querySelector('.remove-badge-btn');
    const cancelBadgeBtn = badgeModal.querySelector('.cancel-badge-btn');
    let currentBadgeCard = null;

    const standardBadgeIcons = {
        'favorite': '⭐',
        'ban': '⛔',
        'watchlist': '👁️',
        'top': '🏆',
        'watched': '✅',
        'new': '🔥'
    };

    // Хранилище кастомных бейджей
    let customBadges = [];

    // Получение иконки бейджа (включая кастомные)
    function getBadgeIcon(badgeType) {
        if (!badgeType) return '';
        if (standardBadgeIcons[badgeType]) {
            return standardBadgeIcons[badgeType];
        }
        // Проверяем кастомные бейджи
        if (badgeType.startsWith('custom_')) {
            const customBadge = customBadges.find(b => b.badge_key === badgeType);
            return customBadge ? customBadge.emoji : '🏷️';
        }
        return '';
    }

    // Получение названия бейджа (включая кастомные)
    function getBadgeName(badgeType) {
        const standardNames = {
            'favorite': 'Любимое',
            'ban': 'Бан',
            'watchlist': 'Хочу посмотреть',
            'top': 'Топ',
            'watched': 'Просмотрено',
            'new': 'Новинка'
        };
        if (!badgeType) return '';
        if (standardNames[badgeType]) {
            return standardNames[badgeType];
        }
        if (badgeType.startsWith('custom_')) {
            const customBadge = customBadges.find(b => b.badge_key === badgeType);
            return customBadge ? customBadge.name : 'Кастомный';
        }
        return '';
    }

    // Загрузка кастомных бейджей
    async function loadCustomBadges() {
        try {
            const response = await fetch('/api/custom-badges');
            if (!response.ok) throw new Error('Не удалось загрузить кастомные бейджи');
            const data = await response.json();
            customBadges = data.badges || [];
            // Обновляем кастомные бейджи в модальном окне
            setModalCustomBadges(customBadges);
            renderCustomBadgesUI();
            updateAllCustomBadgeIcons();
        } catch (error) {
            console.error('Ошибка загрузки кастомных бейджей:', error);
        }
    }

    // Обновление иконок кастомных бейджей на всех карточках
    function updateAllCustomBadgeIcons() {
        document.querySelectorAll('.library-card').forEach(card => {
            const badge = card.dataset.badge;
            if (badge && badge.startsWith('custom_')) {
                const badgeElement = card.querySelector('.movie-badge');
                if (badgeElement) {
                    badgeElement.textContent = getBadgeIcon(badge);
                }
            }
        });
    }

    // Рендеринг UI для кастомных бейджей
    function renderCustomBadgesUI() {
        renderCustomBadgesInSelector();
        renderCustomBadgesInFilters();
        renderCustomBadgesInPollMenu();
    }

    // Рендеринг кастомных бейджей в селекторе
    function renderCustomBadgesInSelector() {
        const container = document.getElementById('badge-options-custom');
        if (!container) return;

        container.innerHTML = customBadges.map(badge => `
            <div class="badge-option badge-option-custom" data-badge="${badge.badge_key}">
                <span class="badge-icon">${badge.emoji}</span>
                <span class="badge-label">${badge.name}</span>
                <button type="button" class="badge-delete-btn" data-badge-id="${badge.id}" title="Удалить бейдж">×</button>
            </div>
        `).join('');

        // Добавляем обработчики для кастомных опций
        container.querySelectorAll('.badge-option-custom').forEach(option => {
            option.addEventListener('click', async (e) => {
                // Игнорируем клик по кнопке удаления
                if (e.target.classList.contains('badge-delete-btn')) return;
                
                if (!currentBadgeCard) return;
                const badgeType = option.dataset.badge;
                const movieId = currentBadgeCard.dataset.movieId;

                try {
                    const result = await setBadge(movieId, badgeType);
                    updateBadgeOnCard(currentBadgeCard, badgeType, result);
                    showToast('Бейдж установлен', 'success');
                    closeBadgeSelector();
                    loadBadgeStats();
                } catch (error) {
                    // Ошибка уже обработана в setBadge
                }
            });
        });

        // Добавляем обработчики для кнопок удаления
        container.querySelectorAll('.badge-delete-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const badgeId = btn.dataset.badgeId;
                if (!confirm('Удалить этот бейдж? Он будет снят со всех фильмов.')) return;

                try {
                    const response = await fetch(`/api/custom-badges/${badgeId}`, { method: 'DELETE' });
                    const data = await response.json();
                    if (!response.ok) throw new Error(data.message || 'Не удалось удалить бейдж');
                    
                    showToast('Бейдж удалён', 'success');
                    await loadCustomBadges();
                    updateBadgeFilterStats();
                    loadBadgeStats();
                } catch (error) {
                    showToast(error.message, 'error');
                }
            });
        });
    }

    // Рендеринг кастомных бейджей в панели фильтров
    function renderCustomBadgesInFilters() {
        const container = document.getElementById('badge-filters-custom-container');
        if (!container) return;

        container.innerHTML = customBadges.map(badge => `
            <button class="badge-filter" data-badge="${badge.badge_key}">
                <span class="badge-filter-icon">${badge.emoji}</span>
                <span class="badge-filter-name">${badge.name}</span>
                <span class="badge-filter-count">(0)</span>
            </button>
        `).join('');

        // Добавляем обработчики для кастомных фильтров
        container.querySelectorAll('.badge-filter').forEach(filter => {
            filter.addEventListener('click', () => {
                const badgeType = filter.dataset.badge;
                badgeFilters.forEach(f => f.classList.remove('active'));
                container.querySelectorAll('.badge-filter').forEach(f => f.classList.remove('active'));
                filter.classList.add('active');
                currentFilter = badgeType;
                applyBadgeFilter(currentFilter);
            });
        });
    }

    // Рендеринг кастомных бейджей в меню опросов
    function renderCustomBadgesInPollMenu() {
        const container = document.getElementById('badge-poll-custom-badges');
        if (!container) return;

        container.innerHTML = customBadges.map(badge => `
            <button class="badge-poll-option badge-poll-option-custom" data-badge="${badge.badge_key}" disabled>
                <span class="badge-icon">${badge.emoji}</span>
                <span class="badge-name">${badge.name}</span>
                <span class="badge-count">(0)</span>
            </button>
        `).join('');

        // Добавляем обработчики для кастомных опций опроса
        container.querySelectorAll('.badge-poll-option-custom').forEach(option => {
            option.addEventListener('click', async (e) => {
                e.preventDefault();
                if (option.disabled) return;

                const badgeType = option.dataset.badge;
                const badgeName = option.querySelector('.badge-name').textContent;
                const badgeIcon = option.querySelector('.badge-icon').textContent;

                badgePollDropdown.classList.remove('active');

                const confirmHtml = `
                    <h2>Создать опрос по бейджу</h2>
                    <div style="text-align: center; margin: 20px 0;">
                        <span style="font-size: 48px;">${badgeIcon}</span>
                        <h3 style="margin: 10px 0;">${badgeName}</h3>
                    </div>
                    <p>Вы действительно хотите создать опрос со всеми фильмами, имеющими бейдж "${badgeName}"?</p>
                    <p style="font-size: 14px; color: #adb5bd; margin-top: 10px;">
                        Опрос будет доступен друзьям по ссылке в течение 24 часов.
                    </p>
                    <div style="display: flex; gap: 10px; margin-top: 20px;">
                        <button class="secondary-button" id="cancel-badge-poll-custom" style="flex: 1; padding: 15px; margin: 0;">Отмена</button>
                        <button class="cta-button" id="confirm-badge-poll-custom" style="flex: 1; padding: 15px; margin: 0;">Создать опрос</button>
                    </div>
                `;

                modal.open();
                modal.renderCustomContent(confirmHtml);

                const confirmBtn = document.getElementById('confirm-badge-poll-custom');
                const cancelBtn = document.getElementById('cancel-badge-poll-custom');

                cancelBtn.addEventListener('click', () => modal.close());

                confirmBtn.addEventListener('click', async () => {
                    confirmBtn.disabled = true;
                    confirmBtn.textContent = 'Создание...';

                    try {
                        const response = await fetch(`/api/library/badges/${badgeType}/movies`);
                        const data = await response.json();

                        if (!response.ok) {
                            throw new Error(data.error || 'Не удалось получить фильмы');
                        }

                        const pollResponse = await fetch(buildPollApiUrl('/polls'), {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ movies: data.movies })
                        });

                        const pollData = await pollResponse.json();
                        if (!pollResponse.ok) {
                            throw new Error(pollData.error || 'Не удалось создать опрос');
                        }

                        showToast('Опрос успешно создан!', 'success');
                        await refreshMyPolls();
                        modal.close();
                    } catch (error) {
                        showToast(error.message, 'error');
                        confirmBtn.disabled = false;
                        confirmBtn.textContent = 'Создать опрос';
                    }
                });
            });
        });
    }

    // Инициализация формы создания бейджа
    function initBadgeCreateForm() {
        const toggleBtn = document.getElementById('badge-create-toggle-btn');
        const form = document.getElementById('badge-create-form');
        const emojiInput = document.getElementById('badge-create-emoji');
        const nameInput = document.getElementById('badge-create-name');
        const submitBtn = document.getElementById('badge-create-submit-btn');
        const cancelBtn = document.getElementById('badge-create-cancel-btn');

        if (!toggleBtn || !form) return;

        toggleBtn.addEventListener('click', () => {
            const isVisible = form.style.display !== 'none';
            form.style.display = isVisible ? 'none' : 'flex';
            toggleBtn.style.display = isVisible ? 'block' : 'none';
            if (!isVisible) {
                emojiInput.value = '';
                nameInput.value = '';
                emojiInput.focus();
            }
        });

        cancelBtn.addEventListener('click', () => {
            form.style.display = 'none';
            toggleBtn.style.display = 'block';
        });

        submitBtn.addEventListener('click', async () => {
            const emoji = emojiInput.value.trim();
            const name = nameInput.value.trim();

            if (!emoji) {
                showToast('Введите эмодзи', 'error');
                emojiInput.focus();
                return;
            }
            if (!name) {
                showToast('Введите название', 'error');
                nameInput.focus();
                return;
            }

            submitBtn.disabled = true;
            submitBtn.textContent = 'Создание...';

            try {
                const response = await fetch('/api/custom-badges', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ emoji, name })
                });

                const data = await response.json();
                if (!response.ok) throw new Error(data.message || 'Не удалось создать бейдж');

                showToast('Бейдж создан', 'success');
                form.style.display = 'none';
                toggleBtn.style.display = 'block';
                await loadCustomBadges();
                updateBadgeFilterStats();
            } catch (error) {
                showToast(error.message, 'error');
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = 'Создать';
            }
        });

        // Enter для создания
        nameInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                submitBtn.click();
            }
        });
    }

    // Инициализация формы создания бейджа
    initBadgeCreateForm();

    // Загружаем кастомные бейджи при старте и обновляем статистику после загрузки
    loadCustomBadges().then(() => {
        updateBadgeFilterStats();
    });

    // Для обратной совместимости
    const badgeIcons = standardBadgeIcons;

    function openBadgeSelector(card) {
        currentBadgeCard = card;
        const currentBadge = card.dataset.badge;

        // Снимаем выделение со всех опций (включая кастомные)
        badgeOptions.forEach(opt => opt.classList.remove('selected'));
        const customOptionsContainer = document.getElementById('badge-options-custom');
        if (customOptionsContainer) {
            customOptionsContainer.querySelectorAll('.badge-option-custom').forEach(opt => opt.classList.remove('selected'));
        }

        // Выделяем текущий бейдж, если есть
        if (currentBadge) {
            // Проверяем стандартные бейджи
            const selectedOption = Array.from(badgeOptions).find(opt => opt.dataset.badge === currentBadge);
            if (selectedOption) {
                selectedOption.classList.add('selected');
            } else if (customOptionsContainer) {
                // Проверяем кастомные бейджи
                const customOption = customOptionsContainer.querySelector(`[data-badge="${currentBadge}"]`);
                if (customOption) customOption.classList.add('selected');
            }
        }

        badgeModal.classList.add('active');
    }

    function closeBadgeSelector() {
        badgeModal.classList.remove('active');
        currentBadgeCard = null;
    }

    async function setBadge(movieId, badgeType, extraPayload = {}) {
        try {
            const response = await fetch(`/api/library/${movieId}/badge`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ badge: badgeType, ...extraPayload })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || 'Не удалось установить бейдж');
            }

            return data;
        } catch (error) {
            showToast(error.message, 'error');
            throw error;
        }
    }

    async function removeBadge(movieId) {
        try {
            const response = await fetch(`/api/library/${movieId}/badge`, {
                method: 'DELETE'
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || 'Не удалось удалить бейдж');
            }

            return data;
        } catch (error) {
            showToast(error.message, 'error');
            throw error;
        }
    }

    function updateBadgeOnCard(card, badgeType, payload = {}, options = {}) {
        const { skipStats = false } = options;
        card.dataset.badge = badgeType || '';
        if (badgeType === 'ban') {
            card.dataset.banStatus = payload.ban_status || 'active';
            card.dataset.banUntil = payload.ban_until || '';
            card.dataset.banRemaining = (payload.ban_remaining_seconds ?? '').toString();
            card.dataset.banAppliedBy = payload.ban_applied_by || '';
            card.dataset.banCost = payload.ban_cost != null ? payload.ban_cost.toString() : '';
            card.dataset.banCostPerMonth = payload.ban_cost_per_month != null ? payload.ban_cost_per_month.toString() : '';
        } else {
            card.dataset.banStatus = 'none';
            card.dataset.banUntil = '';
            card.dataset.banRemaining = '';
            card.dataset.banAppliedBy = '';
            card.dataset.banCost = '';
            // ban_cost_per_month не сбрасываем, так как это настройка фильма, а не бана
        }

        let badgeElement = card.querySelector('.movie-badge');

        if (badgeType) {
            if (!badgeElement) {
                badgeElement = document.createElement('div');
                badgeElement.className = 'movie-badge';
                card.appendChild(badgeElement);
            }
            badgeElement.dataset.badgeType = badgeType;
            badgeElement.textContent = getBadgeIcon(badgeType);
        } else if (badgeElement) {
            badgeElement.remove();
        }

        // После обновления бейджа пересчитываем статистику и сохраняем текущий фильтр
        if (!skipStats) {
            updateBadgeFilterStats();
            applyBadgeFilter(currentFilter);
        }
        renderBanStatus(card);
        enforceSelectionRestrictionsForCard(card);
    }

    // Обработчик клика по опциям бейджа
    badgeOptions.forEach(option => {
        option.addEventListener('click', async () => {
            if (!currentBadgeCard) return;

            const badgeType = option.dataset.badge;
            const movieId = currentBadgeCard.dataset.movieId;

            try {
                const result = await setBadge(movieId, badgeType);
                updateBadgeOnCard(currentBadgeCard, badgeType, result);
                showToast('Бейдж установлен', 'success');
                closeBadgeSelector();
                // Обновляем статистику бейджей
                loadBadgeStats();
            } catch (error) {
                // Ошибка уже обработана в setBadge
            }
        });
    });

    // Обработчик кнопки "Убрать бейдж"
    removeBadgeBtn.addEventListener('click', async () => {
        if (!currentBadgeCard) return;

        const movieId = currentBadgeCard.dataset.movieId;

        try {
            const result = await removeBadge(movieId);
            updateBadgeOnCard(currentBadgeCard, null, result);
            showToast('Бейдж удалён', 'success');
            closeBadgeSelector();
            // Обновляем статистику бейджей
            loadBadgeStats();
        } catch (error) {
            // Ошибка уже обработана в removeBadge
        }
    });

    // Обработчик кнопки "Отмена"
    cancelBadgeBtn.addEventListener('click', () => {
        closeBadgeSelector();
    });

    // Закрытие по клику вне модального окна
    badgeModal.addEventListener('click', (e) => {
        if (e.target === badgeModal) {
            closeBadgeSelector();
        }
    });

    // --- Конец функционала управления бейджами ---

    const notify = (message, type = 'info') => {
        if (typeof showToast === 'function') {
            showToast(message, type);
        } else {
            const logger = type === 'error' ? console.error : console.log;
            logger(message);
        }
    };

    const handleOpenModal = (card) => {
        const movieData = getMovieDataFromCard(card);
        const isModalAlreadyOpen = modalElement.style.display === 'flex';

        modalElement.dataset.activeCardId = card.dataset.movieId || '';

        if (!isModalAlreadyOpen) {
            modal.open();
        } else {
            modal.renderCustomContent('<div class="loader"></div>');
        }

        const actions = {
            onSaveMagnet: async (kinopoiskId, magnetLink) => {
                const result = await movieApi.saveMagnetLink(kinopoiskId, magnetLink);
                notify(result.message, 'success');
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
                    notify(data.message, data.success ? 'success' : 'error');
                });
            },
            onSetBadge: async (movieId, badgeType) => {
                try {
                    const result = await setBadge(movieId, badgeType);
                    updateBadgeOnCard(card, badgeType, result);
                    notify('Бейдж установлен', 'success');
                    handleOpenModal(card);
                } catch (error) {
                    // Ошибка уже обработана в setBadge
                }
            },
            onRemoveBadge: async (movieId) => {
                try {
                    const result = await removeBadge(movieId);
                    updateBadgeOnCard(card, null, result);
                    notify('Бейдж удалён', 'success');
                    handleOpenModal(card);
                } catch (error) {
                    // Ошибка уже обработана в removeBadge
                }
            },
            onSavePoints: async (movieId, newPoints) => {
                try {
                    const result = await movieApi.updateLibraryMoviePoints(movieId, newPoints);
                    if (result.success) {
                        card.dataset.moviePoints = String(result.points);
                        notify(result.message || 'Баллы обновлены', 'success');
                        handleOpenModal(card);
                    } else {
                        notify(result.message || 'Не удалось обновить баллы', 'error');
                    }
                } catch (error) {
                    notify(error.message || 'Не удалось обновить баллы', 'error');
                }
            },
            onSaveBanCostPerMonth: async (movieId, banCostPerMonth) => {
                try {
                    const result = await movieApi.updateLibraryMovieBanCostPerMonth(movieId, banCostPerMonth);
                    if (result.success) {
                        if (result.ban_cost_per_month !== null && result.ban_cost_per_month !== undefined) {
                            card.dataset.banCostPerMonth = String(result.ban_cost_per_month);
                        } else {
                            delete card.dataset.banCostPerMonth;
                        }
                        notify(result.message || 'Цена за месяц бана обновлена', 'success');
                        handleOpenModal(card);
                    } else {
                        notify(result.message || 'Не удалось обновить цену за месяц бана', 'error');
                    }
                } catch (error) {
                    notify(error.message || 'Не удалось обновить цену за месяц бана', 'error');
                }
            },
            onDownload: async () => {
                try {
                    const result = await downloadTorrentToClient({
                        magnetLink: card.dataset.magnetLink,
                        title: movieData.name,
                    });
                    const status = result.success ? 'success' : 'info';
                    notify(result.message || 'Операция выполнена.', status);
                    if (result.success) {
                        card.classList.add('has-torrent-on-client');
                        card.dataset.torrentHash = result.torrent_hash || card.dataset.torrentHash || '';
                        handleOpenModal(card);
                    }
                } catch (error) {
                    notify(error.message || 'Не удалось отправить торрент в клиент.', 'error');
                }
            },
            onDeleteTorrent: async (torrentHash) => {
                try {
                    const result = await deleteTorrentFromClient(torrentHash);
                    const status = result.success ? 'success' : 'info';
                    notify(result.message || 'Операция выполнена.', status);
                    if (result.success) {
                        card.classList.remove('has-torrent-on-client');
                        card.dataset.torrentHash = '';
                        handleOpenModal(card);
                    }
                } catch (error) {
                    notify(error.message || 'Не удалось удалить торрент с клиента.', 'error');
                }
            },
            onUploadTrailer: async (movieId, file) => {
                try {
                    const response = await movieApi.uploadLocalTrailer(movieId, file);
                    if (response?.movie) {
                        applyApiMovieDataToCard(card, response.movie);
                        updateBadgeFilterStats();
                        renderBanStatus(card);
                    }
                    notify('Трейлер сохранён.', 'success');
                    handleOpenModal(card);
                } catch (error) {
                    notify(error.message || 'Не удалось загрузить трейлер.', 'error');
                    throw error;
                }
            },
            onSaveTrailerViewCost: async (movieId, trailerViewCost) => {
                try {
                    const result = await movieApi.updateLibraryMovieTrailerViewCost(movieId, trailerViewCost);
                    if (result.success) {
                        if (result.trailer_view_cost !== null && result.trailer_view_cost !== undefined) {
                            card.dataset.trailerViewCost = String(result.trailer_view_cost);
                        } else {
                            delete card.dataset.trailerViewCost;
                        }
                        notify(result.message || 'Цена за просмотр трейлера обновлена', 'success');
                        handleOpenModal(card);
                    } else {
                        notify(result.message || 'Не удалось обновить цену за просмотр трейлера', 'error');
                    }
                } catch (error) {
                    notify(error.message || 'Не удалось обновить цену за просмотр трейлера', 'error');
                }
            },
            // Расписание/таймеры
            onLoadSchedules: async (movieId) => {
                // Загрузка выполняется в ModalManager
                return true;
            },
            onAddSchedule: async (movieId, date) => {
                try {
                    const response = await fetch(`/api/library/${movieId}/schedule`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ scheduled_date: date })
                    });
                    const result = await response.json();
                    if (!response.ok) {
                        throw new Error(result.message || 'Не удалось добавить таймер');
                    }
                    notify(result.message || 'Таймер добавлен', 'success');
                    return result;
                } catch (error) {
                    notify(error.message || 'Не удалось добавить таймер', 'error');
                    throw error;
                }
            },
            onRemoveSchedule: async (scheduleId) => {
                try {
                    const response = await fetch(`/api/schedules/${scheduleId}`, {
                        method: 'DELETE'
                    });
                    const result = await response.json();
                    if (!response.ok) {
                        throw new Error(result.message || 'Не удалось удалить таймер');
                    }
                    notify(result.message || 'Таймер удалён', 'success');
                    return result;
                } catch (error) {
                    notify(error.message || 'Не удалось удалить таймер', 'error');
                    throw error;
                }
            }
        };

        modal.renderLibraryModal(movieData, actions);
    };

    // АВТОПОИСК МАГНЕТ-ССЫЛОК ОТКЛЮЧЕН
    // Пользователь вручную вводит магнет-ссылки через модальное окно
    // Кнопка RuTracker для поиска на сайте сохранена

    gallery.addEventListener('click', (event) => {
        const card = event.target.closest('.gallery-item');
        if (!card) return;

        const { movieId, kinopoiskId, movieName, movieYear, movieSearchName, movieCountries, hasMagnet, magnetLink } = card.dataset;
        const button = event.target.closest('.icon-button');
        const checkbox = event.target.closest('.movie-checkbox');
        const badgeControlBtn = event.target.closest('.badge-control-btn');

        // Если клик по чекбоксу, не открываем модальное окно
        if (checkbox) {
            event.stopPropagation();
            return;
        }

        // Если клик по кнопке управления бейджами
        if (badgeControlBtn) {
            event.stopPropagation();
            openBadgeSelector(card);
            return;
        }

        if (button) {
            event.stopPropagation();
            if (button.classList.contains('delete-button')) {
                movieApi.deleteLibraryMovie(movieId).then(data => {
                    if (data.success) card.remove();
                    showToast(data.message, data.success ? 'success' : 'error');
                });
            } else if (button.classList.contains('search-rutracker-button')) {
                // Определяем, русский ли это контент (Россия или СССР)
                const countries = (movieCountries || '').toLowerCase();
                const isRussian = countries.includes('россия') || countries.includes('ссср');
                // Для русского контента — русское название, для иностранного — английское (если есть)
                const searchQuery = isRussian
                    ? `${movieName || movieSearchName}${movieYear ? ' ' + movieYear : ''}`
                    : `${movieSearchName || movieName}${movieYear ? ' ' + movieYear : ''}`;
                const encodedQuery = encodeURIComponent(searchQuery);
                const rutrackerUrl = `https://rutracker.net/forum/tracker.php?nm=${encodedQuery}`;
                window.open(rutrackerUrl, '_blank');
                showToast(`Открыт поиск на RuTracker: "${searchQuery}"`, 'info');
                } else if (button.classList.contains('copy-magnet-button')) {
                    // Копируем magnet-ссылку в буфер обмена
                    if (hasMagnet === 'true' && magnetLink) {
                        navigator.clipboard.writeText(magnetLink).then(() => {
                            showToast('Magnet-ссылка скопирована в буфер обмена', 'success');
                        }).catch(() => {
                            showToast('Не удалось скопировать ссылку', 'error');
                        });
                    }
                }
        } else {
            handleOpenModal(card);
        }
    });

    document.querySelectorAll('.date-badge').forEach(badge => {
        badge.textContent = formatDate(badge.dataset.date);
    });

    document.querySelectorAll('.gallery-item').forEach(card => {
        renderBanStatus(card);
        updateTrailerVisuals(card);
    });
    enforceSelectionRestrictionsForAll();
    refreshLibraryData({ silent: true });
    setInterval(updateBanTimers, 1000);
    setInterval(() => refreshLibraryData({ silent: true }), BAN_STATE_POLL_INTERVAL_MS);

    // --- Функция обновления библиотеки из браузерного расширения ---
    // Вызывается расширением через chrome.scripting.executeScript
    window.refreshLibraryFromExtension = async (movieData) => {
        console.log('🎬 Movie Lottery Extension: Обновление библиотеки...');
        
        if (movieData && movieData.name) {
            // Показываем уведомление о добавленном фильме
            const message = movieData.is_new 
                ? `Фильм «${movieData.name}» добавлен в библиотеку!`
                : `Фильм «${movieData.name}» обновлён в библиотеке`;
            showToast(message, 'success');
        }
        
        // Небольшая задержка перед перезагрузкой для отображения toast
        setTimeout(() => {
            // Перезагружаем страницу для отображения нового фильма
            // Сохраняем позицию скролла
            const scrollPos = window.scrollY;
            sessionStorage.setItem('libraryScrollPos', scrollPos.toString());
            window.location.reload();
        }, 1500);
    };

    // Восстанавливаем позицию скролла после перезагрузки
    const savedScrollPos = sessionStorage.getItem('libraryScrollPos');
    if (savedScrollPos) {
        sessionStorage.removeItem('libraryScrollPos');
        window.scrollTo(0, parseInt(savedScrollPos, 10));
    }
});