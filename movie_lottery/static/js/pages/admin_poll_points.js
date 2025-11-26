import { buildPollApiUrl } from '../utils/polls.js';

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
    elements.pollSettingsStatus = document.getElementById('poll-settings-status');
    elements.pollSettingsUpdated = document.getElementById('poll-settings-updated');
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
    const deviceLabel = item.device_label || '';
    const userId = item.user_id || '';

    const totalPoints = Number.isFinite(Number(item.total_points)) ? Number(item.total_points) : 0;

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
                <div class="updated-at" data-updated-at="${escapeHtml(item.updated_at || '')}">${formatDateTime(item.updated_at)}</div>
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

async function loadPollSettings() {
    if (!elements.customVoteCost) return;
    setSettingsStatus('Загружаем...');

    try {
        const response = await fetch(buildPollApiUrl('/api/polls/settings'), {
            credentials: 'include'
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(data.error || 'Не удалось загрузить настройки');
        }

        const cost = Number.parseInt(data.custom_vote_cost, 10);
        elements.customVoteCost.value = Number.isFinite(cost) ? cost : '';
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
        setSettingsStatus('Введите неотрицательное целое число', 'error');
        return;
    }

    setSettingsStatus('Сохраняем...');

    try {
        const response = await fetch(buildPollApiUrl('/api/polls/settings'), {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ custom_vote_cost: parsedCost }),
            credentials: 'include'
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(data.error || 'Не удалось сохранить настройки');
        }

        const cost = Number.parseInt(data.custom_vote_cost, 10);
        elements.customVoteCost.value = Number.isFinite(cost) ? cost : parsedCost;
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
        setMessage('Введите количество баллов.', 'error');
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
    setMessage('Сохраняем баллы…');

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
        setMessage('Баллы обновлены.', 'success');
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

function attachEvents() {
    elements.filtersForm?.addEventListener('submit', handleFiltersSubmit);
    elements.resetFilters?.addEventListener('click', handleResetFilters);
    elements.prevPage?.addEventListener('click', () => handlePagination(-1));
    elements.nextPage?.addEventListener('click', () => handlePagination(1));
    elements.refreshButton?.addEventListener('click', fetchStats);
    elements.pollSettingsForm?.addEventListener('submit', savePollSettings);
    elements.table?.querySelector('thead')?.addEventListener('click', handleSort);
    elements.tableBody?.addEventListener('click', handleCopy);
    elements.tableBody?.addEventListener('click', handleUserIdClick);
    elements.tableBody?.addEventListener('keydown', handleUserIdKeydown);
    elements.tableBody?.addEventListener('click', handleDeviceLabelClick);
    elements.tableBody?.addEventListener('keydown', handleDeviceLabelKeydown);
    elements.tableBody?.addEventListener('click', handlePointsClick);
    elements.tableBody?.addEventListener('keydown', handlePointsKeydown);
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
    attachEvents();
    loadPollSettings();
    fetchStats();
}

document.addEventListener('DOMContentLoaded', bootstrap);
