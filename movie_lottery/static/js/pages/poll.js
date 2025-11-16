// movie_lottery/static/js/pages/poll.js

import { buildPollApiUrl } from '../utils/polls.js';

document.addEventListener('DOMContentLoaded', async () => {
    const pollGrid = document.getElementById('poll-grid');
    const pollMessage = document.getElementById('poll-message');
    const pollDescription = document.getElementById('poll-description');
    const pollResultsBlock = document.getElementById('poll-results-block');
    const pollResultsLink = document.getElementById('poll-results-link');
    const voteConfirmModal = document.getElementById('vote-confirm-modal');
    const voteConfirmBtn = document.getElementById('vote-confirm-btn');
    const voteCancelBtn = document.getElementById('vote-cancel-btn');
    const voteConfirmPoster = document.getElementById('vote-confirm-poster');
    const voteConfirmTitle = document.getElementById('vote-confirm-title');
    const voteConfirmYear = document.getElementById('vote-confirm-year');

    const TEXTS = {
        ru: {
            pointsTitle: 'Ваши баллы',
            pointsStatusEmpty: 'Баллы ещё не начислены',
            pointsStatusUpdated: (points) => `Всего начислено ${points}.`,
            pointsBadgeEmpty: '—',
            pointsBadgeReady: 'OK',
            pointsBadgeError: 'ERR',
            pointsProgressDefault: 'Начисляем баллы…',
            pointsProgressEarned: (points) => `+${points} за голос`,
            historyTitle: 'История начислений',
            historyEmpty: 'Баллы ещё не начислены',
            historyVoteEntry: (points) => `+${points} за голосование`,
            toastPointsEarned: (points) => `+${points} баллов за голос`,
            toastPointsError: 'Не удалось обновить баланс баллов',
            pointsUnavailable: 'Баллы недоступны. Попробуйте обновить страницу позже.',
        },
    };

    const locale = 'ru';
    const T = TEXTS[locale];

    const pointsBalanceCard = document.getElementById('points-widget');
    const pointsBalanceLabel = document.getElementById('points-balance-label');
    const pointsBalanceValue = document.getElementById('points-balance-value');
    const pointsBalanceStatus = document.getElementById('points-balance-status');
    const pointsStateBadge = document.getElementById('points-state-badge');
    const pointsProgress = document.getElementById('points-progress');
    const pointsProgressBar = document.getElementById('points-progress-bar');
    const pointsProgressLabel = document.getElementById('points-progress-label');
    const pointsHistoryTitle = document.getElementById('points-history-title');
    const pointsHistoryList = document.getElementById('points-history-list');
    const pointsHistoryEmpty = document.getElementById('points-history-empty');
    const pointsHistoryCount = document.getElementById('points-history-count');

    let selectedMovie = null;
    let historyEntries = 0;
    let progressTimeoutId = null;
    const publicResultsUrl = `/p/${pollId}/results`;

    if (pollResultsLink) {
        pollResultsLink.href = publicResultsUrl;
    }
    if (pollResultsBlock) {
        pollResultsBlock.hidden = false;
    }

    initializePointsWidget();

    // Загружаем данные опроса
    try {
        const response = await fetch(buildPollApiUrl(`/api/polls/${pollId}`), {
            credentials: 'include'
        });

        if (!response.ok) {
            const error = await response.json();
            showMessage(error.error || 'Опрос не найден', 'error');
            markPointsAsUnavailable();
            return;
        }

        const pollData = await response.json();
        updatePointsBalance(pollData.points_balance);

        // Если пользователь уже голосовал, сразу показываем результаты
        if (pollData.has_voted) {
            window.location.href = publicResultsUrl;
            return;
        }

        // Отображаем фильмы
        renderMovies(pollData.movies);
        pollDescription.textContent = `Выберите один фильм из ${pollData.movies.length}. Проголосовало: ${pollData.total_votes}`;

    } catch (error) {
        console.error('Ошибка загрузки опроса:', error);
        showMessage('Не удалось загрузить опрос', 'error');
        markPointsAsUnavailable();
    }

    function renderMovies(movies) {
        pollGrid.innerHTML = '';
        
        movies.forEach(movie => {
            const movieCard = document.createElement('div');
            movieCard.className = 'poll-movie-card';
            movieCard.dataset.movieId = movie.id;
            
            movieCard.innerHTML = `
                <img src="${movie.poster || 'https://via.placeholder.com/200x300.png?text=No+Image'}" alt="${escapeHtml(movie.name)}">
                <div class="poll-movie-info">
                    <h3>${escapeHtml(movie.name)}</h3>
                    <p class="movie-year">${escapeHtml(movie.year || '')}</p>
                    ${movie.genres ? `<p class="movie-genres">${escapeHtml(movie.genres)}</p>` : ''}
                    ${movie.rating_kp ? `<p class="movie-rating">⭐ ${movie.rating_kp.toFixed(1)}</p>` : ''}
                </div>
            `;

            movieCard.addEventListener('click', () => {
                openVoteConfirmation(movie);
            });

            pollGrid.appendChild(movieCard);
        });
    }

    function openVoteConfirmation(movie) {
        selectedMovie = movie;
        voteConfirmPoster.src = movie.poster || 'https://via.placeholder.com/200x300.png?text=No+Image';
        voteConfirmTitle.textContent = movie.name;
        voteConfirmYear.textContent = movie.year || '';
        voteConfirmModal.style.display = 'flex';
    }

    function closeVoteConfirmation() {
        voteConfirmModal.style.display = 'none';
        selectedMovie = null;
    }

    voteCancelBtn.addEventListener('click', closeVoteConfirmation);

    voteConfirmBtn.addEventListener('click', async () => {
        if (!selectedMovie) return;

        voteConfirmBtn.disabled = true;
        voteConfirmBtn.textContent = 'Отправка...';

        try {
            const response = await fetch(buildPollApiUrl(`/api/polls/${pollId}/vote`), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ movie_id: selectedMovie.id }),
                credentials: 'include'
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || 'Не удалось проголосовать');
            }

            // Закрываем модальное окно
            closeVoteConfirmation();

            // Показываем сообщение об успехе
            showMessage(result.message, 'success');

            handlePointsAfterVote(result);

            // Скрываем сетку фильмов
            pollGrid.style.display = 'none';
            pollDescription.textContent = 'Спасибо за участие! Перенаправляем к результатам…';

            setTimeout(() => {
                window.location.href = publicResultsUrl;
            }, 1500);

        } catch (error) {
            console.error('Ошибка голосования:', error);
            showMessage(error.message, 'error');
            voteConfirmBtn.disabled = false;
            voteConfirmBtn.textContent = 'Да, проголосовать';
        }
    });

    function showMessage(text, type = 'info') {
        pollMessage.textContent = text;
        pollMessage.className = `poll-message poll-message-${type}`;
        pollMessage.style.display = 'block';
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function initializePointsWidget() {
        if (!pointsBalanceLabel || !pointsBalanceStatus || !pointsStateBadge || !pointsProgressLabel || !pointsHistoryTitle || !pointsHistoryEmpty) {
            return;
        }
        pointsBalanceLabel.textContent = T.pointsTitle;
        pointsBalanceStatus.textContent = T.pointsStatusEmpty;
        pointsStateBadge.textContent = T.pointsBadgeEmpty;
        pointsProgressLabel.textContent = T.pointsProgressDefault;
        pointsHistoryTitle.textContent = T.historyTitle;
        pointsHistoryEmpty.textContent = T.historyEmpty;
        updateHistoryCounter();
    }

    function updatePointsBalance(balance) {
        if (!pointsBalanceCard || !pointsBalanceValue || !pointsBalanceStatus || !pointsStateBadge) {
            return;
        }

        if (typeof balance !== 'number' || Number.isNaN(balance)) {
            markPointsAsUnavailable();
            return;
        }

        pointsBalanceCard.classList.remove('points-balance-card-error');
        pointsStateBadge.textContent = T.pointsBadgeReady;
        pointsBalanceValue.textContent = balance;
        pointsBalanceStatus.textContent = T.pointsStatusUpdated(formatPoints(balance));
    }

    function markPointsAsUnavailable() {
        if (!pointsBalanceCard || !pointsStateBadge || !pointsBalanceStatus) return;
        pointsBalanceCard.classList.add('points-balance-card-error');
        pointsStateBadge.textContent = T.pointsBadgeError;
        pointsBalanceStatus.textContent = T.pointsUnavailable;
    }

    function handlePointsAfterVote(result) {
        const awarded = Number(result.points_awarded);
        const newBalance = Number(result.points_balance);

        if (!Number.isFinite(awarded) || !Number.isFinite(newBalance)) {
            showToast(T.toastPointsError, 'error');
            markPointsAsUnavailable();
            return;
        }

        updatePointsBalance(newBalance);
        showToast(T.toastPointsEarned(awarded), 'success', { duration: 4000 });
        addHistoryEntry(awarded, T.historyVoteEntry(awarded));
        playPointsProgress(awarded);
    }

    function addHistoryEntry(points, description) {
        if (!pointsHistoryList) return;
        const item = document.createElement('li');
        item.className = 'points-history-item';
        const timestamp = new Date();
        const formattedPoints = `+${points}`;
        item.innerHTML = `
            <span class="points-history-value">${formattedPoints}</span>
            <div class="points-history-meta">
                <p>${escapeHtml(description)}</p>
                <time datetime="${timestamp.toISOString()}">${formatHistoryTime(timestamp)}</time>
            </div>
        `;
        pointsHistoryList.prepend(item);
        historyEntries += 1;
        if (pointsHistoryEmpty) {
            pointsHistoryEmpty.style.display = 'none';
        }
        updateHistoryCounter();
    }

    function updateHistoryCounter() {
        if (!pointsHistoryCount) return;
        pointsHistoryCount.textContent = historyEntries;
        if (pointsHistoryEmpty) {
            pointsHistoryEmpty.style.display = historyEntries ? 'none' : 'block';
        }
    }

    function playPointsProgress(points) {
        if (!pointsProgress || !pointsProgressBar) return;
        if (progressTimeoutId) {
            clearTimeout(progressTimeoutId);
        }
        pointsProgress.hidden = false;
        pointsProgressBar.style.width = '0%';
        pointsProgressLabel.textContent = T.pointsProgressEarned(points);
        requestAnimationFrame(() => {
            pointsProgressBar.style.width = '100%';
        });
        progressTimeoutId = setTimeout(() => {
            pointsProgress.hidden = true;
            pointsProgressBar.style.width = '0%';
            pointsProgressLabel.textContent = T.pointsProgressDefault;
        }, 1600);
    }

    function formatPoints(value) {
        const absValue = Math.abs(value);
        const decl = declOfNum(absValue, ['балл', 'балла', 'баллов']);
        return `${value} ${decl}`;
    }

    function declOfNum(number, titles) {
        const cases = [2, 0, 1, 1, 1, 2];
        return titles[(number % 100 > 4 && number % 100 < 20) ? 2 : cases[(number % 10 < 5) ? number % 10 : 5]];
    }

    function formatHistoryTime(date) {
        try {
            return new Intl.DateTimeFormat(locale, {
                hour: '2-digit',
                minute: '2-digit',
                day: '2-digit',
                month: '2-digit',
            }).format(date);
        } catch (e) {
            return date.toLocaleTimeString();
        }
    }

    // Закрытие модального окна по клику вне его
    voteConfirmModal.addEventListener('click', (e) => {
        if (e.target === voteConfirmModal) {
            closeVoteConfirmation();
        }
    });
});

