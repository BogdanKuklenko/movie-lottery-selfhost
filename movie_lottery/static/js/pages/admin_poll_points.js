import { buildPollApiUrl } from '../utils/polls.js';
import { formatDateTime as formatVladivostokDateTime } from '../utils/timeFormat.js';

const state = {
    page: 1,
    perPage: 25,
    sortBy: 'updated_at',
    sortOrder: 'desc',
    token: '',
    userId: '',
    pollId: '',
    deviceLabel: '',
    dateFrom: '',
    dateTo: ''
};

const elements = {};

// Modal state
const modalState = {
    userTransactionsModal: null,
    movieDetailsModal: null,
    currentVoterToken: null,
    // Для фильтрации транзакций
    allTransactions: [],
    summary: {},
    deviceLabel: '',
    userId: '',
    dateFilter: null,
};

// Кастомные бейджи
let customBadges = [];

function initElements() {
    elements.tableBody = document.getElementById('stats-table-body');
    elements.paginationInfo = document.getElementById('pagination-info');
    elements.prevPage = document.getElementById('prev-page');
    elements.nextPage = document.getElementById('next-page');
    elements.filtersForm = document.getElementById('filters-form');
    elements.resetFilters = document.getElementById('reset-filters');
    elements.perPageSelect = document.getElementById('per-page-select');
    elements.tokenFilter = document.getElementById('token-filter');
    elements.userIdFilter = document.getElementById('user-id-filter');
    elements.pollFilter = document.getElementById('poll-filter');
    elements.deviceFilter = document.getElementById('device-filter');
    elements.dateFrom = document.getElementById('date-from');
    elements.dateTo = document.getElementById('date-to');
    elements.messageBox = document.getElementById('admin-messages');
    elements.refreshButton = document.getElementById('refresh-table');
    elements.table = document.getElementById('stats-table');
    elements.pollSettingsForm = document.getElementById('poll-settings-form');
    elements.customVoteCost = document.getElementById('custom-vote-cost');
    elements.pollDurationHours = document.getElementById('poll-duration-hours');
    elements.pollDurationMinutes = document.getElementById('poll-duration-minutes');
    elements.winnerBadge = document.getElementById('winner-badge');
    elements.pollSettingsStatus = document.getElementById('poll-settings-status');
    elements.pollSettingsUpdated = document.getElementById('poll-settings-updated');
    
    // Modal elements
    elements.userTransactionsModal = document.getElementById('user-transactions-modal');
    elements.userTransactionsBody = document.getElementById('user-transactions-body');
    elements.userTransactionsClose = document.getElementById('user-transactions-close');
    elements.movieDetailsModal = document.getElementById('movie-details-modal');
    elements.movieDetailsBody = document.getElementById('movie-details-body');
    elements.movieDetailsClose = document.getElementById('movie-details-close');
}

function setMessage(text, type = '') {
    if (!elements.messageBox) return;
    elements.messageBox.textContent = text || '';
    elements.messageBox.className = `admin-messages ${type}`.trim();
}

function setLoadingState() {
    if (!elements.tableBody) return;
    elements.tableBody.innerHTML = `
        <tr>
            <td colspan="7">Загружаем данные…</td>
        </tr>
    `;
}

function setSettingsStatus(text, type = '') {
    if (!elements.pollSettingsStatus) return;
    elements.pollSettingsStatus.textContent = text || '';
    elements.pollSettingsStatus.className = `admin-hint ${type}`.trim();
}

function updateSettingsUpdatedAt(isoString) {
    if (!elements.pollSettingsUpdated) return;
    const formatted = isoString ? formatDateTime(isoString) : '—';
    elements.pollSettingsUpdated.textContent = `Обновлено: ${formatted}`;
}

function escapeHtml(value) {
    if (value === null || value === undefined) return '';
    return value
        .toString()
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function formatDateTime(isoString, withTime = true) {
    return formatVladivostokDateTime(isoString, withTime) || '—';
}

function buildVotesMarkup(votes = []) {
    if (!votes.length) {
        return '<p class="admin-hint">Нет голосов под выбранные фильтры.</p>';
    }

    const rows = votes.map((vote) => `
        <tr>
            <td><code>${escapeHtml(vote.poll_id)}</code></td>
            <td>${escapeHtml(vote.movie_name || '—')}</td>
            <td>${formatDateTime(vote.voted_at)}</td>
            <td>${vote.points_awarded > 0 ? '+' : ''}${vote.points_awarded}</td>
        </tr>
    `).join('');

    return `
        <details class="votes-list">
            <summary>Голоса (${votes.length})</summary>
            <table class="votes-table">
                <thead>
                    <tr>
                        <th>Poll</th>
                        <th>Фильм</th>
                        <th>Когда</th>
                        <th>Баллы</th>
                    </tr>
                </thead>
                <tbody>
                    ${rows}
                </tbody>
            </table>
        </details>
    `;
}

function buildTransactionsMarkup(voterToken, votes = []) {
    // Показываем кнопку открытия модального окна
    const voteCount = votes.length;
    const hasVotes = voteCount > 0;
    
    return `
        <div class="transactions-container" data-voter-token="${escapeHtml(voterToken)}">
            <button type="button" class="open-transactions-modal-btn cta-button secondary" data-voter-token="${escapeHtml(voterToken)}">
                📋 История
            </button>
            ${hasVotes ? `<p class="admin-hint">Голосов: ${voteCount}</p>` : ''}
        </div>
    `;
}

/**
 * Форматирует дату в читаемый вид для заголовка группы (например, "4 декабря 2025")
 */
function formatDateHeader(dateStr) {
    if (!dateStr) return '—';
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return '—';
    
    const options = { day: 'numeric', month: 'long', year: 'numeric' };
    return date.toLocaleDateString('ru-RU', options);
}

/**
 * Форматирует время из ISO строки (например, "10:30")
 */
function formatTime(isoString) {
    if (!isoString) return '—';
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return '—';
    return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
}

/**
 * Группирует транзакции по датам
 */
function groupTransactionsByDate(transactions) {
    const groups = {};
    
    for (const t of transactions) {
        if (!t.created_at) continue;
        
        // Извлекаем только дату (без времени)
        const dateKey = t.created_at.split('T')[0];
        
        if (!groups[dateKey]) {
            groups[dateKey] = {
                date: dateKey,
                transactions: [],
                totalEarned: 0,
                totalSpent: 0
            };
        }
        
        groups[dateKey].transactions.push(t);
        
        // Подсчитываем итоги за день
        if (t.is_credit) {
            groups[dateKey].totalEarned += Math.abs(t.amount || 0);
        } else {
            groups[dateKey].totalSpent += Math.abs(t.amount || 0);
        }
    }
    
    // Сортируем по дате (новые сверху)
    return Object.values(groups).sort((a, b) => b.date.localeCompare(a.date));
}

/**
 * Создаёт HTML для одной транзакции в модальном окне
 */
function renderTransactionBlock(t) {
    const icon = t.type_emoji || (t.is_credit ? '📥' : '📤');
    const typeLabel = t.type_label || t.transaction_type || 'Операция';
    const time = formatTime(t.created_at);
    
    // Формируем строку изменения баланса
    const balanceBefore = t.balance_before ?? 0;
    const balanceAfter = t.balance_after ?? 0;
    const amount = t.amount ?? 0;
    const amountSign = amount >= 0 ? '+' : '';
    const changeType = amount >= 0 ? 'Получено' : 'Потрачено';
    const amountClass = amount >= 0 ? 'amount-positive' : 'amount-negative';
    
    // Кликабельное название фильма (если есть)
    const movieNameHtml = t.movie_name 
        ? `<span class="tx-movie-link" data-movie-name="${escapeHtml(t.movie_name)}">📽️ «${escapeHtml(t.movie_name)}»</span>`
        : '';
    
    const pollHtml = t.poll_id 
        ? `<span class="tx-poll-id">Poll: <code>${escapeHtml(t.poll_id)}</code></span>` 
        : '';
    
    return `
        <div class="tx-block ${amountClass}">
            <div class="tx-header">
                <span class="tx-time">${time}</span>
                <span class="tx-type">${icon} ${escapeHtml(typeLabel)}</span>
            </div>
            <div class="tx-balance-change">
                <span class="tx-balance-before">Было: <strong>${balanceBefore}</strong></span>
                <span class="tx-arrow">→</span>
                <span class="tx-change ${amountClass}">${changeType}: <strong>${amountSign}${amount}</strong></span>
                <span class="tx-arrow">→</span>
                <span class="tx-balance-after">Стало: <strong>${balanceAfter}</strong></span>
            </div>
            ${movieNameHtml || pollHtml ? `
            <div class="tx-details">
                ${movieNameHtml}
                ${pollHtml}
            </div>
            ` : ''}
        </div>
    `;
}

/**
 * Создаёт HTML для группы транзакций за один день
 */
function renderDateGroup(group) {
    const dateHeader = formatDateHeader(group.date);
    const transactionsHtml = group.transactions.map(renderTransactionBlock).join('');
    
    // Итоги за день
    const dayStatsHtml = `
        <div class="day-stats">
            <span class="day-stat day-earned">+${group.totalEarned} pts</span>
            <span class="day-stat day-spent">-${group.totalSpent} pts</span>
        </div>
    `;
    
    return `
        <div class="tx-date-group">
            <div class="tx-date-header">
                <span class="tx-date-title">${dateHeader}</span>
                ${dayStatsHtml}
            </div>
            <div class="tx-date-content">
                ${transactionsHtml}
            </div>
        </div>
    `;
}

/**
 * Создаёт HTML для общей статистики пользователя
 */
function renderSummaryBlock(summary, voterToken, deviceLabel, userId, activeFilter = null) {
    const totalEarned = summary.total_earned || 0;
    const totalSpent = summary.total_spent || 0;
    const currentBalance = summary.current_balance || 0;
    const transactionCount = summary.transaction_count || 0;
    
    // Сокращаем токен для отображения
    const shortToken = voterToken ? `${voterToken.slice(0, 8)}...` : '—';
    
    // Формируем текст фильтра
    const filterBtnClass = activeFilter ? 'tx-filter-btn active' : 'tx-filter-btn';
    const filterTitle = activeFilter ? `Фильтр: ${formatDateHeader(activeFilter)}` : 'Фильтр по дате';
    
    return `
        <div class="tx-modal-header">
            <div class="tx-user-info">
                <span class="tx-user-token" title="${escapeHtml(voterToken)}">Пользователь: <code>${shortToken}</code></span>
                ${deviceLabel ? `<span class="tx-user-device">Устройство: ${escapeHtml(deviceLabel)}</span>` : ''}
                ${userId ? `<span class="tx-user-id">User ID: ${escapeHtml(userId)}</span>` : ''}
            </div>
        </div>
        <div class="tx-summary-card">
            <div class="tx-summary-title">СТАТИСТИКА</div>
            <div class="tx-summary-grid">
                <div class="tx-summary-item">
                    <span class="tx-summary-label">Всего получено:</span>
                    <span class="tx-summary-value amount-positive">+${totalEarned} pts</span>
                </div>
                <div class="tx-summary-item">
                    <span class="tx-summary-label">Всего потрачено:</span>
                    <span class="tx-summary-value amount-negative">-${totalSpent} pts</span>
                </div>
                <div class="tx-summary-item">
                    <span class="tx-summary-label">Текущий баланс:</span>
                    <span class="tx-summary-value tx-balance-current">${currentBalance} pts</span>
                </div>
                <div class="tx-summary-item">
                    <span class="tx-summary-label">Всего операций:</span>
                    <span class="tx-summary-value">${transactionCount}</span>
                </div>
            </div>
            ${activeFilter ? `<button type="button" class="tx-filter-clear" title="Сбросить фильтр">✕</button>` : ''}
            <button type="button" class="${filterBtnClass}" title="${filterTitle}">📅</button>
            <input type="date" class="tx-date-filter-input">
        </div>
    `;
}

/**
 * Открывает модальное окно с историей транзакций пользователя
 */
async function openUserTransactionsModal(voterToken) {
    if (!elements.userTransactionsModal || !elements.userTransactionsBody) return;
    
    modalState.currentVoterToken = voterToken;
    modalState.dateFilter = null; // Сбрасываем фильтр при открытии
    
    // Показываем модальное окно с загрузчиком
    elements.userTransactionsModal.style.display = 'flex';
    elements.userTransactionsModal.setAttribute('aria-hidden', 'false');
    elements.userTransactionsBody.innerHTML = '<div class="loader"></div>';
    document.body.style.overflow = 'hidden';
    
    try {
        const response = await fetch(buildPollApiUrl(`/api/polls/voter-stats/${encodeURIComponent(voterToken)}/transactions?per_page=100`), {
            credentials: 'include'
        });
        
        if (!response.ok) {
            throw new Error('Не удалось загрузить транзакции');
        }
        
        const data = await response.json();
        const transactions = data.transactions || [];
        const summary = data.summary || {};
        const deviceLabel = data.device_label || '';
        const userId = data.user_id || '';
        
        // current_balance приходит в корне ответа, добавляем в summary для удобства
        summary.current_balance = data.current_balance || 0;
        
        // Сохраняем данные для фильтрации
        modalState.allTransactions = transactions;
        modalState.summary = summary;
        modalState.deviceLabel = deviceLabel;
        modalState.userId = userId;
        
        renderTransactionsContent();
        
    } catch (error) {
        console.error('Ошибка загрузки транзакций:', error);
        elements.userTransactionsBody.innerHTML = `
            <p class="tx-error">Ошибка: ${escapeHtml(error.message)}</p>
        `;
    }
}

/**
 * Рендерит содержимое модального окна с учётом фильтра
 */
function renderTransactionsContent() {
    const { allTransactions, summary, deviceLabel, userId, dateFilter, currentVoterToken } = modalState;
    
    // Фильтруем транзакции по дате если есть фильтр
    let filteredTransactions = allTransactions;
    if (dateFilter) {
        filteredTransactions = allTransactions.filter(t => {
            if (!t.created_at) return false;
            return t.created_at.startsWith(dateFilter);
        });
    }
    
    // Пересчитываем статистику для отфильтрованных данных
    const displaySummary = dateFilter ? {
        total_earned: filteredTransactions.filter(t => t.amount > 0).reduce((sum, t) => sum + t.amount, 0),
        total_spent: Math.abs(filteredTransactions.filter(t => t.amount < 0).reduce((sum, t) => sum + t.amount, 0)),
        current_balance: summary.current_balance,
        transaction_count: filteredTransactions.length,
    } : summary;
    
    if (!filteredTransactions.length) {
        elements.userTransactionsBody.innerHTML = `
            ${renderSummaryBlock(displaySummary, currentVoterToken, deviceLabel, userId, dateFilter)}
            <p class="tx-empty">${dateFilter ? 'Нет операций за выбранную дату.' : 'Нет операций с баллами.'}</p>
        `;
    } else {
        // Группируем транзакции по датам
        const groups = groupTransactionsByDate(filteredTransactions);
        const groupsHtml = groups.map(renderDateGroup).join('');
        
        elements.userTransactionsBody.innerHTML = `
            ${renderSummaryBlock(displaySummary, currentVoterToken, deviceLabel, userId, dateFilter)}
            <div class="tx-groups">
                ${groupsHtml}
            </div>
        `;
    }
    
    // Подключаем обработчики фильтра
    attachFilterHandlers();
}

/**
 * Подключает обработчики для кнопки фильтра
 */
function attachFilterHandlers() {
    const filterBtn = elements.userTransactionsBody?.querySelector('.tx-filter-btn');
    const dateInput = elements.userTransactionsBody?.querySelector('.tx-date-filter-input');
    const clearBtn = elements.userTransactionsBody?.querySelector('.tx-filter-clear');
    
    if (filterBtn && dateInput) {
        filterBtn.addEventListener('click', () => {
            dateInput.showPicker?.() || dateInput.click();
        });
        
        dateInput.addEventListener('change', (e) => {
            const selectedDate = e.target.value;
            if (selectedDate) {
                modalState.dateFilter = selectedDate;
                renderTransactionsContent();
            }
        });
    }
    
    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            modalState.dateFilter = null;
            renderTransactionsContent();
        });
    }
}

/**
 * Закрывает модальное окно транзакций пользователя
 */
function closeUserTransactionsModal() {
    if (!elements.userTransactionsModal) return;
    
    elements.userTransactionsModal.style.display = 'none';
    elements.userTransactionsModal.setAttribute('aria-hidden', 'true');
    modalState.currentVoterToken = null;
    
    // Восстанавливаем скролл если нет открытых модальных окон
    if (!elements.movieDetailsModal || elements.movieDetailsModal.style.display !== 'flex') {
        document.body.style.overflow = '';
    }
}

/**
 * Открывает модальное окно с деталями фильма из библиотеки
 */
async function openMovieDetailsModal(movieName) {
    if (!elements.movieDetailsModal || !elements.movieDetailsBody) return;
    
    // Показываем модальное окно с загрузчиком
    elements.movieDetailsModal.style.display = 'flex';
    elements.movieDetailsModal.setAttribute('aria-hidden', 'false');
    elements.movieDetailsBody.innerHTML = '<div class="loader"></div>';
    
    try {
        const response = await fetch(buildPollApiUrl(`/api/library/search?name=${encodeURIComponent(movieName)}`), {
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (!response.ok || !data.success) {
            throw new Error(data.message || 'Фильм не найден в библиотеке');
        }
        
        const movie = data.movie;
        
        // Рендерим карточку фильма (упрощённая версия)
        const posterUrl = movie.poster || 'https://via.placeholder.com/200x300.png?text=No+Image';
        const rating = movie.rating_kp ? parseFloat(movie.rating_kp).toFixed(1) : null;
        const ratingClass = rating >= 7 ? 'rating-high' : rating >= 5 ? 'rating-medium' : 'rating-low';
        
        elements.movieDetailsBody.innerHTML = `
            <div class="movie-card-modal">
                <div class="movie-poster-wrap">
                    <img src="${escapeHtml(posterUrl)}" alt="${escapeHtml(movie.name)}">
                    ${rating ? `<div class="rating-badge rating-${ratingClass}">${rating}</div>` : ''}
                </div>
                <div class="movie-info">
                    <h2>${escapeHtml(movie.name)}${movie.year ? ` (${movie.year})` : ''}</h2>
                    <p class="movie-meta">${escapeHtml(movie.genres || 'н/д')} / ${escapeHtml(movie.countries || 'н/д')}</p>
                    <p class="movie-description">${escapeHtml(movie.description || 'Описание отсутствует.')}</p>
                    ${movie.ban_status && movie.ban_status !== 'none' ? `<div class="ban-info">⛔ Фильм забанен</div>` : ''}
                    ${movie.has_local_trailer ? `<div class="trailer-info">🎬 Трейлер доступен</div>` : ''}
                </div>
            </div>
        `;
        
    } catch (error) {
        console.error('Ошибка загрузки фильма:', error);
        elements.movieDetailsBody.innerHTML = `
            <p class="tx-error">Фильм «${escapeHtml(movieName)}» не найден в библиотеке.</p>
            <p class="admin-hint">Возможно, фильм был удалён или ещё не добавлен.</p>
        `;
    }
}

/**
 * Закрывает модальное окно деталей фильма
 */
function closeMovieDetailsModal() {
    if (!elements.movieDetailsModal) return;
    
    elements.movieDetailsModal.style.display = 'none';
    elements.movieDetailsModal.setAttribute('aria-hidden', 'true');
}

function buildRow(item) {
    const votes = item.votes || [];
    const filteredPoints = item.filtered_points || 0;
    const votesBadge = votes.length
        ? `<span class="badge"><strong>${votes.length}</strong> голосов · ${filteredPoints >= 0 ? '+' : ''}${filteredPoints} pts</span>`
        : '<span class="badge">—</span>';
    const lastVote = votes.length ? votes[0].voted_at : null;
    const deviceLabel = item.device_label || '';
    const userId = item.user_id || '';

    const totalPoints = Number.isFinite(Number(item.total_points)) ? Number(item.total_points) : 0;
    const rawEarned = item.points_earned_total ?? item.points_accrued_total;
    const earnedPoints = Number.isFinite(Number(rawEarned)) ? Number(rawEarned) : 0;

    return `
        <tr>
            <td>
                <div class="token-cell">
                    <code>${escapeHtml(item.voter_token)}</code>
                    <div class="details-actions">
                        <button type="button" class="copy-button" data-copy-token="${escapeHtml(item.voter_token)}">Скопировать</button>
                        <button type="button" class="delete-button" data-delete-token="${escapeHtml(item.voter_token)}">Удалить</button>
                    </div>
                </div>
            </td>
            <td>
                <div class="user-id-cell" data-voter-token="${escapeHtml(item.voter_token)}">
                    <input
                        type="text"
                        class="user-id-input"
                        value="${escapeHtml(userId)}"
                        data-initial-value="${escapeHtml(userId)}"
                        placeholder="Без user ID"
                        maxlength="128"
                        disabled
                    />
                    <button type="button" class="user-id-toggle" data-mode="view">Редактировать</button>
                </div>
            </td>
            <td>
                <div class="device-label-cell" data-voter-token="${escapeHtml(item.voter_token)}">
                    <input
                        type="text"
                        class="device-label-input"
                        value="${escapeHtml(deviceLabel)}"
                        data-initial-value="${escapeHtml(deviceLabel)}"
                        placeholder="Без метки"
                        maxlength="255"
                        disabled
                    />
                    <button type="button" class="device-label-toggle" data-mode="view">Редактировать</button>
                </div>
            </td>
            <td>
                <div class="points-cell" data-voter-token="${escapeHtml(item.voter_token)}">
                    <input
                        type="number"
                        inputmode="numeric"
                        step="1"
                        class="points-input"
                        value="${escapeHtml(totalPoints)}"
                        data-initial-value="${escapeHtml(totalPoints)}"
                        disabled
                    />
                    <button type="button" class="points-toggle" data-mode="view">Редактировать</button>
                </div>
            </td>
            <td>
                <div class="accrued-points-cell" data-voter-token="${escapeHtml(item.voter_token)}">
                    <input
                        type="number"
                        inputmode="numeric"
                        step="1"
                        class="accrued-points-input"
                        value="${escapeHtml(earnedPoints)}"
                        data-initial-value="${escapeHtml(earnedPoints)}"
                        disabled
                    />
                    <button type="button" class="accrued-points-toggle" data-mode="view">Редактировать</button>
                </div>
            </td>
            <td>
                <div class="updated-at" data-updated-at="${escapeHtml(item.updated_at || '')}">${formatDateTime(item.updated_at)}</div>
                <div class="admin-hint">Создан: ${formatDateTime(item.created_at, false)}</div>
            </td>
            <td>
                ${buildTransactionsMarkup(item.voter_token, votes)}
            </td>
        </tr>
    `;
}

function renderTable(items = []) {
    if (!elements.tableBody) return;
    if (!items.length) {
        elements.tableBody.innerHTML = `
            <tr>
                <td colspan="7">По текущим фильтрам ничего не найдено.</td>
            </tr>
        `;
        return;
    }

    elements.tableBody.innerHTML = items.map(buildRow).join('');
}

function updatePagination(meta) {
    if (!elements.paginationInfo) return;
    const { page, pages, total } = meta;
    elements.paginationInfo.textContent = `Страница ${page} из ${pages || 1}. Всего записей: ${total}`;
    if (elements.prevPage) {
        elements.prevPage.disabled = page <= 1;
    }
    if (elements.nextPage) {
        elements.nextPage.disabled = Boolean(pages) && page >= pages;
    }
}

function updateSortIndicators() {
    if (!elements.table) return;
    const headers = elements.table.querySelectorAll('th[data-sort]');
    headers.forEach((th) => {
        if (th.dataset.sort === state.sortBy) {
            th.dataset.order = state.sortOrder === 'asc' ? '↑' : '↓';
            th.classList.add('sorted');
        } else {
            th.dataset.order = '';
            th.classList.remove('sorted');
        }
    });
}

function buildHeaders(extra = {}) {
    return { Accept: 'application/json', ...extra };
}

function collectFiltersFromForm() {
    state.token = elements.tokenFilter?.value.trim() || '';
    state.userId = elements.userIdFilter?.value.trim() || '';
    state.pollId = elements.pollFilter?.value.trim() || '';
    state.deviceLabel = elements.deviceFilter?.value.trim() || '';
    state.dateFrom = elements.dateFrom?.value || '';
    state.dateTo = elements.dateTo?.value || '';
}

function validateDates() {
    if (state.dateFrom && state.dateTo && state.dateFrom > state.dateTo) {
        setMessage('Дата начала должна быть раньше даты окончания.', 'error');
        return false;
    }
    return true;
}

async function loadCustomBadges() {
    try {
        const response = await fetch(buildPollApiUrl('/api/custom-badges'), {
            credentials: 'include'
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            console.error('Не удалось загрузить кастомные бейджи:', data.error);
            return;
        }

        customBadges = data.badges || [];
        
        // Добавляем кастомные бейджи в select
        if (elements.winnerBadge && customBadges.length > 0) {
            // Удаляем старые кастомные опции (если были)
            const existingCustomOptions = elements.winnerBadge.querySelectorAll('option[data-custom="true"]');
            existingCustomOptions.forEach(opt => opt.remove());
            
            // Добавляем новые
            for (const badge of customBadges) {
                const option = document.createElement('option');
                option.value = badge.badge_key;
                option.textContent = `${badge.emoji} ${badge.name}`;
                option.dataset.custom = 'true';
                elements.winnerBadge.appendChild(option);
            }
        }
    } catch (error) {
        console.error('Ошибка загрузки кастомных бейджей:', error);
    }
}

async function loadPollSettings() {
    if (!elements.customVoteCost) return;
    setSettingsStatus('Загружаем...');

    try {
        // Загружаем кастомные бейджи параллельно с настройками
        await loadCustomBadges();
        
        const response = await fetch(buildPollApiUrl('/api/polls/settings'), {
            credentials: 'include'
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(data.error || 'Не удалось загрузить настройки');
        }

        const cost = Number.parseInt(data.custom_vote_cost, 10);
        elements.customVoteCost.value = Number.isFinite(cost) ? cost : '';

        // Конвертируем минуты в часы и минуты для отображения
        const totalMinutes = Number.parseInt(data.poll_duration_minutes, 10);
        if (Number.isFinite(totalMinutes)) {
            const hours = Math.floor(totalMinutes / 60);
            const minutes = totalMinutes % 60;
            if (elements.pollDurationHours) {
                elements.pollDurationHours.value = hours;
            }
            if (elements.pollDurationMinutes) {
                elements.pollDurationMinutes.value = minutes;
            }
        } else {
            // По умолчанию 24 часа
            if (elements.pollDurationHours) elements.pollDurationHours.value = 24;
            if (elements.pollDurationMinutes) elements.pollDurationMinutes.value = 0;
        }

        // Устанавливаем значение бейджа победителя
        if (elements.winnerBadge) {
            elements.winnerBadge.value = data.winner_badge || '';
        }

        updateSettingsUpdatedAt(data.updated_at);
        setSettingsStatus('Настройки загружены');
    } catch (error) {
        console.error(error);
        setSettingsStatus(error.message || 'Не удалось загрузить настройки', 'error');
    }
}

async function savePollSettings(event) {
    event.preventDefault();
    if (!elements.customVoteCost) return;

    const parsedCost = Number.parseInt(elements.customVoteCost.value, 10);
    if (!Number.isFinite(parsedCost) || parsedCost < 0) {
        setSettingsStatus('Стоимость голоса: введите неотрицательное целое число', 'error');
        return;
    }

    // Вычисляем общее количество минут из часов и минут
    const parsedHours = elements.pollDurationHours 
        ? Number.parseInt(elements.pollDurationHours.value, 10) 
        : 0;
    const parsedMins = elements.pollDurationMinutes 
        ? Number.parseInt(elements.pollDurationMinutes.value, 10) 
        : 0;
    
    const hours = Number.isFinite(parsedHours) && parsedHours >= 0 ? parsedHours : 0;
    const mins = Number.isFinite(parsedMins) && parsedMins >= 0 && parsedMins < 60 ? parsedMins : 0;
    const totalMinutes = hours * 60 + mins;
    
    if (totalMinutes < 1) {
        setSettingsStatus('Время жизни опроса: минимум 1 минута', 'error');
        return;
    }
    if (totalMinutes > 5256000) {
        setSettingsStatus('Время жизни опроса: максимум 10 лет', 'error');
        return;
    }

    // Получаем значение бейджа победителя
    const winnerBadge = elements.winnerBadge ? elements.winnerBadge.value : null;

    setSettingsStatus('Сохраняем...');

    try {
        const payload = { custom_vote_cost: parsedCost };
        // Отправляем общее количество минут
        payload.poll_duration_minutes = totalMinutes;
        // Отправляем winner_badge (пустая строка означает "не менять бейдж")
        if (winnerBadge !== null) {
            payload.winner_badge = winnerBadge;
        }

        const response = await fetch(buildPollApiUrl('/api/polls/settings'), {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            credentials: 'include'
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(data.error || 'Не удалось сохранить настройки');
        }

        const cost = Number.parseInt(data.custom_vote_cost, 10);
        elements.customVoteCost.value = Number.isFinite(cost) ? cost : parsedCost;

        // Конвертируем минуты в часы и минуты для отображения
        const savedMinutes = Number.parseInt(data.poll_duration_minutes, 10);
        if (Number.isFinite(savedMinutes)) {
            const savedHours = Math.floor(savedMinutes / 60);
            const savedMins = savedMinutes % 60;
            if (elements.pollDurationHours) {
                elements.pollDurationHours.value = savedHours;
            }
            if (elements.pollDurationMinutes) {
                elements.pollDurationMinutes.value = savedMins;
            }
        }

        // Обновляем значение бейджа победителя
        if (elements.winnerBadge) {
            elements.winnerBadge.value = data.winner_badge || '';
        }

        updateSettingsUpdatedAt(data.updated_at);
        setSettingsStatus('Настройки сохранены', 'success');
    } catch (error) {
        console.error(error);
        setSettingsStatus(error.message || 'Не удалось сохранить настройки', 'error');
    }
}

async function fetchStats() {
    setLoadingState();
    setMessage('');

    const params = new URLSearchParams({
        page: state.page,
        per_page: state.perPage,
        sort_by: state.sortBy,
        sort_order: state.sortOrder
    });

    if (state.token) params.set('token', state.token);
    if (state.userId) params.set('user_id', state.userId);
    if (state.pollId) params.set('poll_id', state.pollId);
    if (state.deviceLabel) params.set('device_label', state.deviceLabel);
    if (state.dateFrom) params.set('date_from', state.dateFrom);
    if (state.dateTo) params.set('date_to', state.dateTo);
    try {
        const response = await fetch(buildPollApiUrl(`/api/polls/voter-stats?${params.toString()}`), {
            headers: buildHeaders(),
            credentials: 'include'
        });

        if (!response.ok) {
            let errorDetail = '';
            try {
                const errorData = await response.json();
                if (typeof errorData === 'string') {
                    errorDetail = errorData;
                } else {
                    errorDetail = errorData?.error || errorData?.message || '';
                }
            } catch (jsonError) {
                try {
                    errorDetail = (await response.text())?.trim();
                } catch (textError) {
                    errorDetail = '';
                }
            }
            const statusText = response.statusText ? ` (${response.statusText})` : '';
            const errorMessage = `Сервер вернул ${response.status}${statusText}${errorDetail ? `: ${errorDetail}` : ''}`;
            throw new Error(errorMessage);
        }

        let data;
        try {
            data = await response.json();
        } catch (jsonError) {
            let rawText = '';
            try {
                rawText = (await response.text())?.trim();
            } catch (textError) {
                rawText = '';
            }
            const errorMessage = rawText
                ? `Не удалось распарсить ответ сервера: ${rawText}`
                : 'Не удалось распарсить ответ сервера.';
            throw new Error(errorMessage);
        }
        renderTable(data.items || []);
        updatePagination(data);
        updateSortIndicators();
    } catch (error) {
        console.error('Ошибка загрузки статистики', error);
        const userMessage = error?.message?.trim() || 'Не удалось получить данные';
        setMessage(userMessage, 'error');
        if (elements.tableBody) {
            elements.tableBody.innerHTML = `
                <tr>
                    <td colspan="7">${escapeHtml(userMessage)}</td>
                </tr>
            `;
        }
    }
}

function handleFiltersSubmit(event) {
    event.preventDefault();
    collectFiltersFromForm();
    if (!validateDates()) return;
    state.page = 1;
    fetchStats();
}

function handleResetFilters() {
    if (elements.filtersForm) {
        elements.filtersForm.reset();
    }
    state.token = '';
    state.userId = '';
    state.pollId = '';
    state.deviceLabel = '';
    state.dateFrom = '';
    state.dateTo = '';
    state.perPage = 25;
    if (elements.perPageSelect) elements.perPageSelect.value = '25';
    state.page = 1;
    fetchStats();
}

function handlePagination(direction) {
    state.page += direction;
    if (state.page < 1) state.page = 1;
    fetchStats();
}

function handleSort(event) {
    const header = event.target.closest('th[data-sort]');
    if (!header) return;
    const sortKey = header.dataset.sort;
    if (!sortKey) return;
    if (state.sortBy === sortKey) {
        state.sortOrder = state.sortOrder === 'asc' ? 'desc' : 'asc';
    } else {
        state.sortBy = sortKey;
        state.sortOrder = 'desc';
    }
    state.page = 1;
    updateSortIndicators();
    fetchStats();
}

function handleCopy(event) {
    const button = event.target.closest('[data-copy-token]');
    if (!button) return;
    const token = button.dataset.copyToken;
    if (!token) return;
    navigator.clipboard.writeText(token)
        .then(() => setMessage('Токен скопирован.', 'success'))
        .catch(() => setMessage('Не удалось скопировать токен.', 'error'));
}

function handleDeleteClick(event) {
    const button = event.target.closest('[data-delete-token]');
    if (!button) return;
    const token = button.dataset.deleteToken;
    if (!token) return;
    openDeleteModal(token);
}

function openDeleteModal(token) {
    const modal = document.getElementById('delete-token-modal');
    const tokenEl = document.getElementById('delete-token-value');
    const secretInput = document.getElementById('delete-admin-secret');
    if (!modal || !tokenEl) return;
    tokenEl.textContent = token;
    modal.style.display = 'block';
    modal.setAttribute('aria-hidden', 'false');
    if (secretInput) {
        secretInput.value = '';
        secretInput.focus();
    }
    // store token on modal for later reference
    modal.dataset.targetToken = token;
}

function closeDeleteModal() {
    const modal = document.getElementById('delete-token-modal');
    if (!modal) return;
    modal.style.display = 'none';
    modal.setAttribute('aria-hidden', 'true');
    delete modal.dataset.targetToken;
}

async function confirmDeleteToken() {
    const modal = document.getElementById('delete-token-modal');
    const token = modal?.dataset?.targetToken;
    const secretInput = document.getElementById('delete-admin-secret');
    const secret = secretInput?.value || '';
    if (!token) return setMessage('Не указан токен для удаления', 'error');
    if (!secret) return setMessage('Введите админский секрет для подтверждения', 'error');

    try {
        const response = await fetch(buildPollApiUrl(`/api/polls/voter-stats/${encodeURIComponent(token)}`), {
            method: 'DELETE',
            headers: buildHeaders({ Authorization: `Bearer ${secret}` }),
            credentials: 'include',
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(data.error || 'Не удалось удалить токен');
        }
        setMessage('Токен успешно удалён', 'success');
        closeDeleteModal();
        fetchStats();
    } catch (err) {
        console.error(err);
        setMessage(err.message || 'Ошибка при удалении токена', 'error');
    }
}

function enterDeviceLabelEditing(container) {
    const input = container?.querySelector('.device-label-input');
    const button = container?.querySelector('.device-label-toggle');
    if (!input || !button) return;
    container.classList.add('is-editing');
    button.dataset.mode = 'editing';
    button.textContent = 'Сохранить';
    input.disabled = false;
    input.focus();
    input.setSelectionRange(input.value.length, input.value.length);
}

function exitDeviceLabelEditing(container, { resetValue = false } = {}) {
    const input = container?.querySelector('.device-label-input');
    const button = container?.querySelector('.device-label-toggle');
    if (!input || !button) return;
    container.classList.remove('is-editing');
    button.dataset.mode = 'view';
    button.textContent = 'Редактировать';
    if (resetValue) {
        input.value = input.dataset.initialValue || '';
    }
    input.disabled = true;
}

function enterPointsEditing(container) {
    const input = container?.querySelector('.points-input');
    const button = container?.querySelector('.points-toggle');
    if (!input || !button) return;
    container.classList.add('is-editing');
    button.dataset.mode = 'editing';
    button.textContent = 'Сохранить';
    input.disabled = false;
    input.focus();
    input.select();
}

function exitPointsEditing(container, { resetValue = false } = {}) {
    const input = container?.querySelector('.points-input');
    const button = container?.querySelector('.points-toggle');
    if (!input || !button) return;
    container.classList.remove('is-editing');
    button.dataset.mode = 'view';
    button.textContent = 'Редактировать';
    if (resetValue) {
        input.value = input.dataset.initialValue || '0';
    }
    input.disabled = true;
}

function enterAccruedPointsEditing(container) {
    const input = container?.querySelector('.accrued-points-input');
    const button = container?.querySelector('.accrued-points-toggle');
    if (!input || !button) return;
    container.classList.add('is-editing');
    button.dataset.mode = 'editing';
    button.textContent = 'Сохранить';
    input.disabled = false;
    input.focus();
    input.select();
}

function exitAccruedPointsEditing(container, { resetValue = false } = {}) {
    const input = container?.querySelector('.accrued-points-input');
    const button = container?.querySelector('.accrued-points-toggle');
    if (!input || !button) return;
    container.classList.remove('is-editing');
    button.dataset.mode = 'view';
    button.textContent = 'Редактировать';
    if (resetValue) {
        input.value = input.dataset.initialValue || '0';
    }
    input.disabled = true;
}

function enterUserIdEditing(container) {
    const input = container?.querySelector('.user-id-input');
    const button = container?.querySelector('.user-id-toggle');
    if (!input || !button) return;
    container.classList.add('is-editing');
    button.dataset.mode = 'editing';
    button.textContent = 'Сохранить';
    input.disabled = false;
    input.focus();
    input.setSelectionRange(input.value.length, input.value.length);
}

function exitUserIdEditing(container, { resetValue = false } = {}) {
    const input = container?.querySelector('.user-id-input');
    const button = container?.querySelector('.user-id-toggle');
    if (!input || !button) return;
    container.classList.remove('is-editing');
    button.dataset.mode = 'view';
    button.textContent = 'Редактировать';
    if (resetValue) {
        input.value = input.dataset.initialValue || '';
    }
    input.disabled = true;
}

function updateRowMeta(container, profile) {
    const row = container?.closest('tr');
    if (!row || !profile) return;
    const updatedAtElement = row.querySelector('[data-updated-at]');
    if (updatedAtElement && profile.updated_at) {
        updatedAtElement.dataset.updatedAt = profile.updated_at;
        updatedAtElement.textContent = formatDateTime(profile.updated_at);
    }
}

async function saveDeviceLabel(container) {
    const token = container?.dataset.voterToken;
    const input = container?.querySelector('.device-label-input');
    const button = container?.querySelector('.device-label-toggle');
    if (!token || !input || !button) return;

    const trimmed = input.value.trim();
    let normalized = trimmed ? trimmed.slice(0, 255) : null;
    if (normalized !== null && trimmed.length > 255) {
        input.value = normalized;
    }
    if (normalized === null) {
        input.value = '';
    }

    button.disabled = true;
    input.disabled = true;
    setMessage('Сохраняем метку устройства…');

    try {
        const response = await fetch(buildPollApiUrl(`/api/polls/voter-stats/${encodeURIComponent(token)}/device-label`), {
            method: 'PATCH',
            headers: buildHeaders({ 'Content-Type': 'application/json' }),
            credentials: 'include',
            body: JSON.stringify({ device_label: normalized })
        });

        if (!response.ok) {
            let errorDetail = '';
            try {
                const errorData = await response.json();
                if (typeof errorData === 'string') {
                    errorDetail = errorData;
                } else {
                    errorDetail = errorData?.error || errorData?.message || '';
                }
            } catch (jsonError) {
                try {
                    errorDetail = (await response.text())?.trim();
                } catch (textError) {
                    errorDetail = '';
                }
            }
            const statusText = response.statusText ? ` (${response.statusText})` : '';
            const errorMessage = `Сервер вернул ${response.status}${statusText}${errorDetail ? `: ${errorDetail}` : ''}`;
            throw new Error(errorMessage);
        }

        let data;
        try {
            data = await response.json();
        } catch (jsonError) {
            let rawText = '';
            try {
                rawText = (await response.text())?.trim();
            } catch (textError) {
                rawText = '';
            }
            const errorMessage = rawText
                ? `Не удалось распарсить ответ сервера: ${rawText}`
                : 'Не удалось распарсить ответ сервера.';
            throw new Error(errorMessage);
        }

        const newValue = data.device_label || '';
        input.value = newValue;
        input.dataset.initialValue = newValue;
        exitDeviceLabelEditing(container);
        setMessage('Метка устройства обновлена.', 'success');
        updateRowMeta(container, data);
    } catch (error) {
        console.error('Ошибка обновления метки устройства', error);
        const userMessage = error?.message?.trim() || 'Не удалось обновить метку устройства.';
        setMessage(userMessage, 'error');
        input.disabled = false;
        button.disabled = false;
        return;
    }

    button.disabled = false;
}

async function saveUserId(container) {
    const token = container?.dataset.voterToken;
    const input = container?.querySelector('.user-id-input');
    const button = container?.querySelector('.user-id-toggle');
    if (!token || !input || !button) return;

    const trimmed = input.value.trim();
    let normalized = trimmed ? trimmed.slice(0, 128) : null;
    if (normalized !== null && trimmed.length > 128) {
        input.value = normalized;
    }
    if (normalized === null) {
        input.value = '';
    }

    button.disabled = true;
    input.disabled = true;
    setMessage('Сохраняем user ID…');

    try {
        const response = await fetch(buildPollApiUrl(`/api/polls/voter-stats/${encodeURIComponent(token)}/user-id`), {
            method: 'PATCH',
            headers: buildHeaders({ 'Content-Type': 'application/json' }),
            credentials: 'include',
            body: JSON.stringify({ user_id: normalized })
        });

        if (!response.ok) {
            let errorDetail = '';
            try {
                const errorData = await response.json();
                if (typeof errorData === 'string') {
                    errorDetail = errorData;
                } else {
                    errorDetail = errorData?.error || errorData?.message || '';
                }
            } catch (jsonError) {
                try {
                    errorDetail = (await response.text())?.trim();
                } catch (textError) {
                    errorDetail = '';
                }
            }
            const statusText = response.statusText ? ` (${response.statusText})` : '';
            const errorMessage = `Сервер вернул ${response.status}${statusText}${errorDetail ? `: ${errorDetail}` : ''}`;
            throw new Error(errorMessage);
        }

        let data;
        try {
            data = await response.json();
        } catch (jsonError) {
            let rawText = '';
            try {
                rawText = (await response.text())?.trim();
            } catch (textError) {
                rawText = '';
            }
            const errorMessage = rawText
                ? `Не удалось распарсить ответ сервера: ${rawText}`
                : 'Не удалось распарсить ответ сервера.';
            throw new Error(errorMessage);
        }

        const newValue = data.user_id || '';
        input.value = newValue;
        input.dataset.initialValue = newValue;
        exitUserIdEditing(container);
        setMessage('User ID обновлен.', 'success');
        updateRowMeta(container, data);
    } catch (error) {
        console.error('Ошибка обновления user ID', error);
        const userMessage = error?.message?.trim() || 'Не удалось обновить user ID.';
        setMessage(userMessage, 'error');
        input.disabled = false;
        button.disabled = false;
        return;
    }

    button.disabled = false;
}

async function savePoints(container) {
    const token = container?.dataset.voterToken;
    const input = container?.querySelector('.points-input');
    const button = container?.querySelector('.points-toggle');
    if (!token || !input || !button) return;

    const trimmed = input.value.trim();
    if (trimmed === '') {
        setMessage('Введите баланс баллов.', 'error');
        input.focus();
        return;
    }

    const parsed = Number(trimmed);
    if (!Number.isFinite(parsed) || !Number.isInteger(parsed)) {
        setMessage('Баллы должны быть целым числом.', 'error');
        input.focus();
        return;
    }

    const normalized = parsed;

    button.disabled = true;
    input.disabled = true;
    setMessage('Сохраняем баланс баллов…');

    try {
        const response = await fetch(buildPollApiUrl(`/api/polls/voter-stats/${encodeURIComponent(token)}/points`), {
            method: 'PATCH',
            headers: buildHeaders({ 'Content-Type': 'application/json' }),
            credentials: 'include',
            body: JSON.stringify({ total_points: normalized })
        });

        if (!response.ok) {
            let errorDetail = '';
            try {
                const errorData = await response.json();
                if (typeof errorData === 'string') {
                    errorDetail = errorData;
                } else {
                    errorDetail = errorData?.error || errorData?.message || '';
                }
            } catch (jsonError) {
                try {
                    errorDetail = (await response.text())?.trim();
                } catch (textError) {
                    errorDetail = '';
                }
            }
            const statusText = response.statusText ? ` (${response.statusText})` : '';
            const errorMessage = `Сервер вернул ${response.status}${statusText}${errorDetail ? `: ${errorDetail}` : ''}`;
            throw new Error(errorMessage);
        }

        let data;
        try {
            data = await response.json();
        } catch (jsonError) {
            let rawText = '';
            try {
                rawText = (await response.text())?.trim();
            } catch (textError) {
                rawText = '';
            }
            const errorMessage = rawText
                ? `Не удалось распарсить ответ сервера: ${rawText}`
                : 'Не удалось распарсить ответ сервера.';
            throw new Error(errorMessage);
        }

        const newValue = Number.isFinite(Number(data.total_points)) ? Number(data.total_points) : 0;
        input.value = newValue;
        input.dataset.initialValue = String(newValue);
        exitPointsEditing(container);
        setMessage('Баланс баллов обновлен.', 'success');
        updateRowMeta(container, data);
    } catch (error) {
        console.error('Ошибка обновления баллов', error);
        const userMessage = error?.message?.trim() || 'Не удалось обновить баллы.';
        setMessage(userMessage, 'error');
        input.disabled = false;
        button.disabled = false;
        return;
    }

    button.disabled = false;
}

async function saveAccruedPoints(container) {
    const token = container?.dataset.voterToken;
    const input = container?.querySelector('.accrued-points-input');
    const button = container?.querySelector('.accrued-points-toggle');
    if (!token || !input || !button) return;

    const trimmed = input.value.trim();
    if (trimmed === '') {
        setMessage('Введите накопленные баллы.', 'error');
        input.focus();
        return;
    }

    const parsed = Number(trimmed);
    if (!Number.isFinite(parsed) || !Number.isInteger(parsed)) {
        setMessage('Накопленные баллы должны быть целым числом.', 'error');
        input.focus();
        return;
    }

    const normalized = parsed;

    button.disabled = true;
    input.disabled = true;
    setMessage('Сохраняем накопленные баллы…');

    try {
        const response = await fetch(buildPollApiUrl(`/api/polls/voter-stats/${encodeURIComponent(token)}/points-accrued`), {
            method: 'PATCH',
            headers: buildHeaders({ 'Content-Type': 'application/json' }),
            credentials: 'include',
            body: JSON.stringify({ points_accrued_total: normalized })
        });

        if (!response.ok) {
            let errorDetail = '';
            try {
                const errorData = await response.json();
                if (typeof errorData === 'string') {
                    errorDetail = errorData;
                } else {
                    errorDetail = errorData?.error || errorData?.message || '';
                }
            } catch (jsonError) {
                try {
                    errorDetail = (await response.text())?.trim();
                } catch (textError) {
                    errorDetail = '';
                }
            }
            const statusText = response.statusText ? ` (${response.statusText})` : '';
            const errorMessage = `Сервер вернул ${response.status}${statusText}${errorDetail ? `: ${errorDetail}` : ''}`;
            throw new Error(errorMessage);
        }

        let data;
        try {
            data = await response.json();
        } catch (jsonError) {
            let rawText = '';
            try {
                rawText = (await response.text())?.trim();
            } catch (textError) {
                rawText = '';
            }
            const errorMessage = rawText
                ? `Не удалось распарсить ответ сервера: ${rawText}`
                : 'Не удалось распарсить ответ сервера.';
            throw new Error(errorMessage);
        }

        const rawEarned = data.points_earned_total ?? data.points_accrued_total;
        const newValue = Number.isFinite(Number(rawEarned)) ? Number(rawEarned) : 0;
        input.value = newValue;
        input.dataset.initialValue = String(newValue);
        exitAccruedPointsEditing(container);
        setMessage('Накопленные баллы обновлены.', 'success');
        updateRowMeta(container, data);
    } catch (error) {
        console.error('Ошибка обновления накопленных баллов', error);
        const userMessage = error?.message?.trim() || 'Не удалось обновить накопленные баллы.';
        setMessage(userMessage, 'error');
        input.disabled = false;
        button.disabled = false;
        return;
    }

    button.disabled = false;
}

function handleDeviceLabelClick(event) {
    const button = event.target.closest('.device-label-toggle');
    if (!button) return;
    const container = button.closest('.device-label-cell');
    if (!container) return;
    if (button.dataset.mode === 'editing') {
        saveDeviceLabel(container);
    } else {
        enterDeviceLabelEditing(container);
    }
}

function handleDeviceLabelKeydown(event) {
    const input = event.target.closest('.device-label-input');
    if (!input) return;
    const container = input.closest('.device-label-cell');
    const button = container?.querySelector('.device-label-toggle');
    if (!container || !button) return;
    if (event.key === 'Enter' && button.dataset.mode === 'editing') {
        event.preventDefault();
        saveDeviceLabel(container);
    } else if (event.key === 'Escape') {
        event.preventDefault();
        exitDeviceLabelEditing(container, { resetValue: true });
    }
}

function handleUserIdClick(event) {
    const button = event.target.closest('.user-id-toggle');
    if (!button) return;
    const container = button.closest('.user-id-cell');
    if (!container) return;
    if (button.dataset.mode === 'editing') {
        saveUserId(container);
    } else {
        enterUserIdEditing(container);
    }
}

function handleUserIdKeydown(event) {
    const input = event.target.closest('.user-id-input');
    if (!input) return;
    const container = input.closest('.user-id-cell');
    const button = container?.querySelector('.user-id-toggle');
    if (!container || !button) return;
    if (event.key === 'Enter' && button.dataset.mode === 'editing') {
        event.preventDefault();
        saveUserId(container);
    } else if (event.key === 'Escape') {
        event.preventDefault();
        exitUserIdEditing(container, { resetValue: true });
    }
}

function handlePointsClick(event) {
    const button = event.target.closest('.points-toggle');
    if (!button) return;
    const container = button.closest('.points-cell');
    if (!container) return;
    if (button.dataset.mode === 'editing') {
        savePoints(container);
    } else {
        enterPointsEditing(container);
    }
}

function handlePointsKeydown(event) {
    const input = event.target.closest('.points-input');
    if (!input) return;
    const container = input.closest('.points-cell');
    const button = container?.querySelector('.points-toggle');
    if (!container || !button) return;
    if (event.key === 'Enter' && button.dataset.mode === 'editing') {
        event.preventDefault();
        savePoints(container);
    } else if (event.key === 'Escape') {
        event.preventDefault();
        exitPointsEditing(container, { resetValue: true });
    }
}

function handleAccruedPointsClick(event) {
    const button = event.target.closest('.accrued-points-toggle');
    if (!button) return;
    const container = button.closest('.accrued-points-cell');
    if (!container) return;
    if (button.dataset.mode === 'editing') {
        saveAccruedPoints(container);
    } else {
        enterAccruedPointsEditing(container);
    }
}

function handleAccruedPointsKeydown(event) {
    const input = event.target.closest('.accrued-points-input');
    if (!input) return;
    const container = input.closest('.accrued-points-cell');
    const button = container?.querySelector('.accrued-points-toggle');
    if (!container || !button) return;
    if (event.key === 'Enter' && button.dataset.mode === 'editing') {
        event.preventDefault();
        saveAccruedPoints(container);
    } else if (event.key === 'Escape') {
        event.preventDefault();
        exitAccruedPointsEditing(container, { resetValue: true });
    }
}

function handleTransactionsClick(event) {
    // Открытие модального окна транзакций
    const btn = event.target.closest('.open-transactions-modal-btn');
    if (btn) {
        const voterToken = btn.dataset.voterToken;
        if (voterToken) {
            openUserTransactionsModal(voterToken);
        }
        return;
    }
}

function handleMovieLinkClick(event) {
    // Клик на название фильма в модальном окне транзакций
    const movieLink = event.target.closest('.tx-movie-link');
    if (movieLink) {
        const movieName = movieLink.dataset.movieName;
        if (movieName) {
            openMovieDetailsModal(movieName);
        }
    }
}

function attachEvents() {
    elements.filtersForm?.addEventListener('submit', handleFiltersSubmit);
    elements.resetFilters?.addEventListener('click', handleResetFilters);
    elements.prevPage?.addEventListener('click', () => handlePagination(-1));
    elements.nextPage?.addEventListener('click', () => handlePagination(1));
    elements.refreshButton?.addEventListener('click', fetchStats);
    elements.pollSettingsForm?.addEventListener('submit', savePollSettings);
    elements.table?.querySelector('thead')?.addEventListener('click', handleSort);
    elements.tableBody?.addEventListener('click', handleCopy);
    elements.tableBody?.addEventListener('click', handleDeleteClick);
    elements.tableBody?.addEventListener('click', handleUserIdClick);
    elements.tableBody?.addEventListener('keydown', handleUserIdKeydown);
    elements.tableBody?.addEventListener('click', handleDeviceLabelClick);
    elements.tableBody?.addEventListener('keydown', handleDeviceLabelKeydown);
    elements.tableBody?.addEventListener('click', handlePointsClick);
    elements.tableBody?.addEventListener('keydown', handlePointsKeydown);
    elements.tableBody?.addEventListener('click', handleAccruedPointsClick);
    elements.tableBody?.addEventListener('keydown', handleAccruedPointsKeydown);
    elements.tableBody?.addEventListener('click', handleTransactionsClick);
    elements.perPageSelect?.addEventListener('change', (event) => {
        const value = parseInt(event.target.value, 10);
        if (!Number.isNaN(value)) {
            state.perPage = value;
            state.page = 1;
            fetchStats();
        }
    });

    // Modal buttons for delete confirmation
    const deleteConfirm = document.getElementById('delete-confirm');
    const deleteCancel = document.getElementById('delete-cancel');
    deleteConfirm?.addEventListener('click', confirmDeleteToken);
    deleteCancel?.addEventListener('click', closeDeleteModal);
    
    // User transactions modal events
    elements.userTransactionsClose?.addEventListener('click', closeUserTransactionsModal);
    elements.userTransactionsModal?.addEventListener('click', (event) => {
        // Закрытие по клику на overlay
        if (event.target === elements.userTransactionsModal) {
            closeUserTransactionsModal();
        }
        // Клик на название фильма
        handleMovieLinkClick(event);
    });
    
    // Movie details modal events
    elements.movieDetailsClose?.addEventListener('click', closeMovieDetailsModal);
    elements.movieDetailsModal?.addEventListener('click', (event) => {
        // Закрытие по клику на overlay
        if (event.target === elements.movieDetailsModal) {
            closeMovieDetailsModal();
        }
    });
    
    // Закрытие модальных окон по Escape
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            // Закрываем в порядке: сначала модалку фильма, потом транзакций
            if (elements.movieDetailsModal?.style.display === 'flex') {
                closeMovieDetailsModal();
            } else if (elements.userTransactionsModal?.style.display === 'flex') {
                closeUserTransactionsModal();
            }
        }
    });
}

function bootstrap() {
    initElements();
    if (!elements.tableBody) return;
    attachEvents();
    loadPollSettings();
    fetchStats();
}

document.addEventListener('DOMContentLoaded', bootstrap);
