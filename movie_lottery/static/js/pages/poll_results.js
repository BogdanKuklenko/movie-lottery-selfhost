// movie_lottery/static/js/pages/poll_results.js

import { buildPollApiUrl, loadMyPolls } from '../utils/polls.js';
import { formatDateTimeShort as formatVladivostokDateTime } from '../utils/timeFormat.js';

document.addEventListener('DOMContentLoaded', async () => {
    const descriptionEl = document.getElementById('poll-results-description');
    const messageEl = document.getElementById('poll-results-message');
    const winnersSection = document.getElementById('poll-winners-section');
    const winnersContainer = document.getElementById('poll-winners');
    const winnersTitle = document.getElementById('poll-winners-title');
    const resultsList = document.getElementById('poll-results-list');
    const resultsLinkInput = document.getElementById('poll-results-link');
    const libraryLink = document.getElementById('open-library-link');
    const myPollsButton = document.getElementById('my-polls-btn');
    const myPollsBadge = document.getElementById('my-polls-badge');
    const hasMyPollsElements = Boolean(myPollsButton || myPollsBadge);

    if (myPollsButton) {
        myPollsButton.addEventListener('click', () => {
            window.location.href = '/library';
        });
    }

    const currentPollId = window.pollId;
    const currentPageUrl = `${window.location.origin}${window.location.pathname}`;

    if (currentPollId == null || currentPollId === '') {
        console.error('Идентификатор опроса не найден на странице.');
        showMessage('Не удалось определить, результаты какого опроса нужно показать. Попробуйте обновить страницу или открыть ссылку из приглашения снова.', 'error');
        return;
    }

    updateResultsLink(currentPageUrl);

    document.querySelectorAll('.copy-btn').forEach((button) => {
        button.addEventListener('click', async () => {
            const targetId = button.getAttribute('data-copy-target');
            const input = document.getElementById(targetId);
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

    if (libraryLink) {
        libraryLink.href = '/library';
        libraryLink.removeAttribute('target');
        libraryLink.removeAttribute('rel');
    }

    await loadResults();

    function handleErrorResponse(status, errorMessage) {
        if (status === 410) {
            showMessage('Опрос истёк. Результаты больше недоступны.', 'info');
        } else if (status === 404) {
            showMessage('Опрос не найден. Возможно, он был удалён.', 'error');
        } else {
            showMessage(errorMessage || 'Произошла неизвестная ошибка при загрузке результатов.', 'error');
        }
    }

    function renderResults(data) {
        const totalVotes = Number(data.total_votes) || 0;
        const movies = Array.isArray(data.movies) ? data.movies : [];
        const createdAt = data.created_at || null;
        const expiresAt = data.expires_at || null;

        descriptionEl.textContent = buildDescription({ totalVotes, moviesCount: movies.length, createdAt, expiresAt });

        const winnerMovies = movies.filter((movie) => movie.is_winner);
        if (winnerMovies.length > 0 && totalVotes > 0) {
            winnersSection.style.display = 'block';
            winnersTitle.textContent = winnerMovies.length > 1 ? 'Победители' : 'Победитель';
            winnersContainer.innerHTML = winnerMovies.map(renderWinnerCard).join('');
        } else {
            winnersSection.style.display = 'none';
        }

        if (resultsList) {
            resultsList.innerHTML = movies.map((movie, index) => renderResultsRow({ movie, index, totalVotes })).join('');
        }

        if (totalVotes === 0) {
            showMessage('Голосов пока нет. Поделитесь ссылкой на опрос, чтобы собрать ответы.', 'info');
        } else {
            hideMessage();
        }
    }

    function renderWinnerCard(movie) {
        const poster = movie.poster || 'https://via.placeholder.com/100x150.png?text=No+Image';
        const year = movie.year ? `<p>${escapeHtml(movie.year)}</p>` : '';
        const votesLabel = Number.isFinite(movie.votes) ? `<p class="vote-count">Голосов: ${movie.votes}</p>` : '';
        return `
            <div class="poll-winner">
                <img src="${poster}" alt="${escapeHtml(movie.name)}">
                <div class="poll-winner-info">
                    <h4>${escapeHtml(movie.name)}</h4>
                    ${year}
                    ${votesLabel}
                </div>
            </div>
        `;
    }

    function renderResultsRow({ movie, index, totalVotes }) {
        const poster = movie.poster || 'https://via.placeholder.com/80x120.png?text=No+Image';
        const votes = Number(movie.votes) || 0;
        const percent = totalVotes > 0 ? Math.round((votes / totalVotes) * 100) : 0;
        const position = index + 1;
        const winnerClass = movie.is_winner ? 'poll-results-item-winner' : '';
        const isBanned = movie.ban_status === 'active';
        const bannedClass = isBanned ? 'poll-results-item-banned' : '';

        let banBadgeHtml = '';
        if (isBanned) {
            let banText = 'Забанен';
            if (movie.ban_until) {
                const banUntilDate = formatVladivostokDateTime(movie.ban_until);
                banText = `Забанен до ${banUntilDate}`;
            }
            banBadgeHtml = `<span class="poll-results-ban-badge">${escapeHtml(banText)}</span>`;
        }

        return `
            <div class="poll-results-item ${winnerClass} ${bannedClass}">
                <div class="poll-results-position">${position}</div>
                <div class="poll-results-poster">
                    <img src="${poster}" alt="${escapeHtml(movie.name)}">
                </div>
                <div class="poll-results-info">
                    <div class="poll-results-title">
                        <h3>${escapeHtml(movie.name)}</h3>
                        ${banBadgeHtml}
                        <span class="poll-results-votes">${votes}&nbsp;гол. · ${percent}%</span>
                    </div>
                    <div class="poll-results-bar">
                        <span style="width: ${percent}%"></span>
                    </div>
                    ${movie.year ? `<p class="poll-results-meta">${escapeHtml(movie.year)}</p>` : ''}
                </div>
            </div>
        `;
    }

    function buildDescription({ totalVotes, moviesCount, createdAt, expiresAt }) {
        const parts = [];
        parts.push(`Фильмов в опросе: ${moviesCount}`);
        parts.push(`Проголосовало: ${totalVotes}`);
        if (createdAt) {
            const createdDateStr = formatVladivostokDateTime(createdAt);
            parts.push(`Создан: ${createdDateStr}`);
        }
        if (expiresAt) {
            const expiresDateStr = formatVladivostokDateTime(expiresAt);
            parts.push(`Действует до: ${expiresDateStr}`);
        }
        return parts.join(' · ');
    }

    function showMessage(text, type = 'info') {
        if (!messageEl) return;
        messageEl.textContent = text;
        messageEl.className = `poll-message poll-message-${type}`;
        messageEl.style.display = 'block';
    }

    function hideMessage() {
        if (!messageEl) return;
        messageEl.style.display = 'none';
    }

    function updateResultsLink(url) {
        if (!resultsLinkInput) {
            return;
        }
        resultsLinkInput.value = url || `${window.location.origin}${window.location.pathname}`;
    }

    async function loadResults() {
        hideMessage();

        if (hasMyPollsElements) {
            try {
                await loadMyPolls({
                    myPollsButton,
                    myPollsBadgeElement: myPollsBadge,
                });
            } catch (error) {
                console.warn('Не удалось обновить список "Мои опросы":', error);
            }
        }

        try {
            const response = await fetch(buildPollApiUrl(`/api/polls/${currentPollId}/results`), {
                credentials: 'include'
            });
            const payload = await response.json();

            if (!response.ok) {
                handleErrorResponse(response.status, payload?.error);
                return;
            }

            renderResults(payload);
        } catch (error) {
            console.error('Не удалось загрузить результаты опроса:', error);
            showMessage('Не удалось загрузить результаты опроса. Попробуйте обновить страницу позже.', 'error');
        }
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text == null ? '' : String(text);
        return div.innerHTML;
    }
});
