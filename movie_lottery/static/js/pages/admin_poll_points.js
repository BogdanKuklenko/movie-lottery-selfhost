const SECRET_STORAGE_KEY = 'movieLotteryAdminSecret';

const state = {
    page: 1,
    perPage: 25,
    sortBy: 'updated_at',
    sortOrder: 'desc',
    token: '',
    pollId: '',
    deviceLabel: '',
    dateFrom: '',
    dateTo: '',
    adminSecret: ''
};

const elements = {};

function initElements() {
    elements.tableBody = document.getElementById('stats-table-body');
    elements.paginationInfo = document.getElementById('pagination-info');
    elements.prevPage = document.getElementById('prev-page');
    elements.nextPage = document.getElementById('next-page');
    elements.filtersForm = document.getElementById('filters-form');
    elements.resetFilters = document.getElementById('reset-filters');
    elements.perPageSelect = document.getElementById('per-page-select');
    elements.tokenFilter = document.getElementById('token-filter');
    elements.pollFilter = document.getElementById('poll-filter');
    elements.deviceFilter = document.getElementById('device-filter');
    elements.dateFrom = document.getElementById('date-from');
    elements.dateTo = document.getElementById('date-to');
    elements.messageBox = document.getElementById('admin-messages');
    elements.refreshButton = document.getElementById('refresh-table');
    elements.secretForm = document.getElementById('admin-secret-form');
    elements.secretInput = document.getElementById('admin-secret-input');
    elements.rememberSecret = document.getElementById('remember-secret-checkbox');
    elements.table = document.getElementById('stats-table');
}

function restoreSecretFromStorage() {
    const initialSecret = window.adminConfig?.initialSecret || '';
    let storedSecret = '';
    try {
        storedSecret = localStorage.getItem(SECRET_STORAGE_KEY) || '';
    } catch (error) {
        storedSecret = '';
    }

    const secret = initialSecret || storedSecret;
    state.adminSecret = secret;
    if (elements.secretInput) {
        elements.secretInput.value = secret;
    }
    if (elements.rememberSecret && storedSecret) {
        elements.rememberSecret.checked = true;
    }
}

function persistSecret(value) {
    try {
        if (value && elements.rememberSecret?.checked) {
            localStorage.setItem(SECRET_STORAGE_KEY, value);
        } else {
            localStorage.removeItem(SECRET_STORAGE_KEY);
        }
    } catch (error) {
        console.warn('Не удалось сохранить секрет в localStorage', error);
    }
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
            <td colspan="6">Загружаем данные…</td>
        </tr>
    `;
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
    if (!isoString) return '—';
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) return '—';
    const options = { year: 'numeric', month: 'short', day: '2-digit' };
    if (withTime) {
        options.hour = '2-digit';
        options.minute = '2-digit';
    }
    return new Intl.DateTimeFormat('ru-RU', options).format(date);
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

function buildRow(item) {
    const votes = item.votes || [];
    const filteredPoints = item.filtered_points || 0;
    const votesBadge = votes.length
        ? `<span class="badge"><strong>${votes.length}</strong> голосов · ${filteredPoints >= 0 ? '+' : ''}${filteredPoints} pts</span>`
        : '<span class="badge">—</span>';
    const lastVote = votes.length ? votes[0].voted_at : null;

    return `
        <tr>
            <td>
                <div class="token-cell">
                    <code>${escapeHtml(item.voter_token)}</code>
                    <div class="details-actions">
                        <button type="button" class="copy-button" data-copy-token="${escapeHtml(item.voter_token)}">Скопировать</button>
                    </div>
                </div>
            </td>
            <td>${escapeHtml(item.device_label || '—')}</td>
            <td>${item.total_points ?? 0}</td>
            <td>
                <div>${formatDateTime(item.updated_at)}</div>
                <div class="admin-hint">Создан: ${formatDateTime(item.created_at, false)}</div>
            </td>
            <td>
                ${votesBadge}
                <div class="admin-hint">Последний голос: ${formatDateTime(lastVote)}</div>
            </td>
            <td>
                ${buildVotesMarkup(votes)}
            </td>
        </tr>
    `;
}

function renderTable(items = []) {
    if (!elements.tableBody) return;
    if (!items.length) {
        elements.tableBody.innerHTML = `
            <tr>
                <td colspan="6">По текущим фильтрам ничего не найдено.</td>
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

function buildHeaders() {
    const headers = { Accept: 'application/json' };
    if (state.adminSecret) {
        headers['X-Admin-Secret'] = state.adminSecret;
    }
    return headers;
}

function collectFiltersFromForm() {
    state.token = elements.tokenFilter?.value.trim() || '';
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
    if (state.pollId) params.set('poll_id', state.pollId);
    if (state.deviceLabel) params.set('device_label', state.deviceLabel);
    if (state.dateFrom) params.set('date_from', state.dateFrom);
    if (state.dateTo) params.set('date_to', state.dateTo);
    if (state.adminSecret) params.set('admin_secret', state.adminSecret);

    try {
        const response = await fetch(`/api/polls/voter-stats?${params.toString()}`, {
            headers: buildHeaders(),
            credentials: 'same-origin'
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'Не удалось загрузить статистику');
        }
        renderTable(data.items || []);
        updatePagination(data);
        updateSortIndicators();
    } catch (error) {
        console.error(error);
        setMessage(error.message || 'Не удалось получить данные', 'error');
        if (elements.tableBody) {
            elements.tableBody.innerHTML = `
                <tr>
                    <td colspan="6">${escapeHtml(error.message || 'Ошибка загрузки')}</td>
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

function handleSecretSubmit(event) {
    event.preventDefault();
    const secret = elements.secretInput?.value.trim() || '';
    state.adminSecret = secret;
    persistSecret(secret);
    setMessage('Секрет обновлён. Перезагружаем данные…', 'success');
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

function attachEvents() {
    elements.filtersForm?.addEventListener('submit', handleFiltersSubmit);
    elements.resetFilters?.addEventListener('click', handleResetFilters);
    elements.prevPage?.addEventListener('click', () => handlePagination(-1));
    elements.nextPage?.addEventListener('click', () => handlePagination(1));
    elements.refreshButton?.addEventListener('click', fetchStats);
    elements.table?.querySelector('thead')?.addEventListener('click', handleSort);
    elements.tableBody?.addEventListener('click', handleCopy);
    elements.secretForm?.addEventListener('submit', handleSecretSubmit);
    elements.perPageSelect?.addEventListener('change', (event) => {
        const value = parseInt(event.target.value, 10);
        if (!Number.isNaN(value)) {
            state.perPage = value;
            state.page = 1;
            fetchStats();
        }
    });
}

function bootstrap() {
    initElements();
    if (!elements.tableBody) return;
    restoreSecretFromStorage();
    attachEvents();
    fetchStats();
}

document.addEventListener('DOMContentLoaded', bootstrap);
