// movie_lottery/static/js/pages/poll.js

import { buildPollApiUrl } from '../utils/polls.js';
import { fetchMovieInfo } from '../api/movies.js';
import { lockScroll, unlockScroll } from '../utils/scrollLock.js';

document.addEventListener('DOMContentLoaded', async () => {
    const pollGrid = document.getElementById('poll-grid');
    const pollMessage = document.getElementById('poll-message');
    const pollDescription = document.getElementById('poll-description');
    const voteConfirmModal = document.getElementById('vote-confirm-modal');
    const voteConfirmBtn = document.getElementById('vote-confirm-btn');
    const voteCancelBtn = document.getElementById('vote-cancel-btn');
    const voteConfirmPoster = document.getElementById('vote-confirm-poster');
    const voteConfirmTitle = document.getElementById('vote-confirm-title');
    const voteConfirmYear = document.getElementById('vote-confirm-year');
    const voteConfirmPoints = document.getElementById('vote-confirm-points');
    const votedMovieWrapper = document.getElementById('voted-movie-wrapper');
    const votedMovieCard = document.getElementById('voted-movie-card');
    const banModal = document.getElementById('ban-modal');
    const banConfirmBtn = document.getElementById('ban-confirm-btn');
    const banCancelBtn = document.getElementById('ban-cancel-btn');
    const banDaysInput = document.getElementById('ban-days-input');
    const banModalDescription = document.getElementById('ban-modal-description');
    const banModalError = document.getElementById('ban-modal-error');
    const pollWinnerBanner = document.getElementById('poll-winner-banner');

    const TEXTS = {
        ru: {
            pointsTitle: 'Ваши баллы',
            pointsStatusEmpty: 'Баллы ещё не начислены',
            pointsStatusUpdated: (points) => `Всего начислено ${points}`,
            pointsBadgeEmpty: '—',
            pointsBadgeError: '—',
            pointsProgressDefault: 'Начисляем баллы…',
            pointsProgressEarned: (points) => `+${points} за голос`,
            toastPointsEarned: (points) => `+${points} баллов за голос`,
            toastPointsDeducted: (points) => `−${points} баллов списано`,
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

    const customVoteBtn = document.getElementById('custom-vote-btn');
    const customVoteWarning = document.getElementById('custom-vote-insufficient');
    const customVoteModal = document.getElementById('custom-vote-modal');
    const customVoteInput = document.getElementById('custom-vote-input');
    const customVoteSearchBtn = document.getElementById('custom-vote-search-btn');
    const customVoteSubmitBtn = document.getElementById('custom-vote-submit');
    const customVoteCancelBtn = document.getElementById('custom-vote-cancel');
    const customVoteStatus = document.getElementById('custom-vote-status');
    const customVoteStatusLoading = document.getElementById('custom-vote-status-loading');
    const customVoteStatusEmpty = document.getElementById('custom-vote-status-empty');
    const customVoteStatusError = document.getElementById('custom-vote-status-error');
    const customVoteErrorText = document.getElementById('custom-vote-error-text');
    const customVoteResult = document.getElementById('custom-vote-result');
    const customVotePoster = document.getElementById('custom-vote-poster');
    const customVoteTitle = document.getElementById('custom-vote-title');
    const customVoteYear = document.getElementById('custom-vote-year');
    const customVoteRating = document.getElementById('custom-vote-rating');
    const customVoteCostDescription = document.getElementById('custom-vote-cost-description');
    const customVoteDescription = document.getElementById('custom-vote-description');
    const pollConfigNode = document.getElementById('poll-config');

    let selectedMovie = null;
    let progressTimeoutId = null;
    let hasVoted = false;
    let votedMovie = null;
    let votedMoviePointsDelta = null;
    let isVoteModalOpen = false;
    let customVoteMovie = null;
    let customVoteQuery = '';
    let customVoteCost = 0;
    let isCustomVoteModalOpen = false;
    let isCustomVoteLoading = false;
    let isCustomVoteSubmitting = false;
    let pointsBalance = null;
    let pointsEarnedTotal = null;
    let voterToken = null;
    let moviesList = [];
    let banTargetMovie = null;
    let isBanModalOpen = false;
    let pollClosedByBan = false;
    let forcedWinner = null;
    const PLACEHOLDER_POSTER = 'https://via.placeholder.com/200x300.png?text=No+Image';

    const modalHistoryStack = [];
    let ignoreModalPopState = false;

    initializePointsWidget();
    const initialCustomVoteCost = Number(pollConfigNode?.dataset.customVoteCost);
    if (Number.isFinite(initialCustomVoteCost)) {
        customVoteCost = initialCustomVoteCost;
    }
    updateCustomVoteCostLabels(customVoteCost);

    const getMoviePoints = (movie) => {
        const rawPoints = movie?.points;
        const parsed = Number.parseInt(rawPoints, 10);
        if (Number.isNaN(parsed)) {
            return 1;
        }
        return Math.min(999, Math.max(0, parsed));
    };

    const isMovieBanned = (movie) => {
        const status = String(movie?.ban_status || '').toLowerCase();
        return status === 'active' || status === 'pending';
    };

    const getActiveMovies = (movies) => {
        if (!Array.isArray(movies)) return [];
        return movies.filter(movie => !isMovieBanned(movie));
    };

    async function fetchPollData(options = {}) {
        const { skipVoteHandling = false, showErrors = true } = options;

        try {
            const response = await fetch(buildPollApiUrl(`/api/polls/${pollId}`), {
                credentials: 'include',
            });

            const pollData = await response.json();

            if (!response.ok) {
                const errorMessage = pollData?.error || 'Не удалось загрузить опрос';
                if (showErrors) {
                    showMessage(errorMessage, 'error');
                    markPointsAsUnavailable();
                }
                throw new Error(errorMessage);
            }

            applyPollData(pollData, { skipVoteHandling });
            return pollData;
        } catch (error) {
            console.error('Ошибка загрузки опроса:', error);
            if (showErrors) {
                showMessage('Не удалось загрузить опрос', 'error');
                markPointsAsUnavailable();
            }
            throw error;
        }
    }

    function applyPollData(pollData, { skipVoteHandling = false } = {}) {
        if (!pollData) return;

        voterToken = pollData.voter_token || voterToken;
        updatePointsBalance(pollData.points_balance, pollData.points_earned_total);
        customVoteCost = Number(pollData.custom_vote_cost) || customVoteCost;
        updateCustomVoteCostLabels(customVoteCost);
        moviesList = Array.isArray(pollData.movies) ? pollData.movies : [];
        pollClosedByBan = Boolean(pollData.closed_by_ban);
        forcedWinner = pollData.forced_winner || null;
        updateCustomVoteButtonState({
            balance: pollData.points_balance,
            can_vote_custom: pollData.can_vote_custom,
            hasVoted: pollData.has_voted,
        });

        renderMovies(moviesList);

        if (pollDescription && typeof pollData.total_votes === 'number') {
            pollDescription.textContent = `Выберите один фильм из ${moviesList.length}. Проголосовало: ${pollData.total_votes}`;
        }

        if (pollClosedByBan) {
            handlePollClosedByBan(forcedWinner);
        }

        if (!skipVoteHandling && pollData.has_voted) {
            hasVoted = true;
            if (pollData.voted_movie) {
                handleVotedState(pollData.voted_movie, pollData.voted_points_delta);
            } else {
                showMessage('Вы уже проголосовали в этом опросе.', 'info');
                updateVotingDisabledState(true);
            }
        }
    }

    try {
        await fetchPollData();
    } catch (error) {
        console.error('Ошибка загрузки опроса:', error);
    }

    function renderMovies(movies) {
        moviesList = Array.isArray(movies) ? movies : [];
        pollGrid.innerHTML = '';

        moviesList.forEach(movie => {
            const movieCard = document.createElement('div');
            movieCard.className = 'poll-movie-card';
            movieCard.dataset.movieId = movie.id;
            const isBanned = isMovieBanned(movie);
            const pointsValue = getMoviePoints(movie);
            const badgeValue = formatPointsBadge(pointsValue);
            const badgeTitle = pointsValue > 0
                ? `+${formatPoints(pointsValue)}`
                : 'Баллы не начисляются';
            const badgeClasses = ['poll-movie-points-badge'];
            if (pointsValue <= 0) {
                badgeClasses.push('poll-movie-points-badge-muted');
            }

            movieCard.innerHTML = `
                <div class="poll-movie-poster">
                    <img src="${movie.poster || PLACEHOLDER_POSTER}" alt="${escapeHtml(movie.name)}">
                    <span class="${badgeClasses.join(' ')}" title="${badgeTitle}">${badgeValue}</span>
                </div>
                <div class="poll-movie-info">
                    <h3>${escapeHtml(movie.name)}</h3>
                    <p class="movie-year">${escapeHtml(movie.year || '')}</p>
                    ${movie.genres ? `<p class="movie-genres">${escapeHtml(movie.genres)}</p>` : ''}
                    ${movie.rating_kp ? `<p class="movie-rating">⭐ ${movie.rating_kp.toFixed(1)}</p>` : ''}
                </div>
            `;

            const actions = document.createElement('div');
            actions.className = 'poll-movie-actions';
            const banBtn = document.createElement('button');
            banBtn.type = 'button';
            banBtn.className = 'secondary-button poll-ban-button';
            if (isBanned) {
                banBtn.classList.add('poll-ban-button-static');
                banBtn.textContent = buildBanLabel(movie);
                banBtn.setAttribute('aria-disabled', 'true');
            } else {
                banBtn.textContent = 'Исключить из опроса';
                banBtn.disabled = pollClosedByBan;
                banBtn.addEventListener('click', (event) => {
                    event.stopPropagation();
                    handleBanClick(movie);
                });
            }
            actions.appendChild(banBtn);
            movieCard.appendChild(actions);

            if (isBanned) {
                movieCard.classList.add('poll-movie-card-banned');
            }

            movieCard.addEventListener('click', () => {
                if (pollClosedByBan) {
                    renderWinnerBanner(forcedWinner || movie);
                    showMessage('Голосование завершено из-за банов.', 'info');
                    return;
                }
                if (isBanned) {
                    showToast('Фильм уже исключён из опроса.', 'info');
                    return;
                }
                if (hasVoted) {
                    const text = votedMovie
                        ? `Вы уже проголосовали за «${votedMovie.name}».`
                        : 'Вы уже проголосовали в этом опросе.';
                    showMessage(text, 'info');
                    return;
                }
                openVoteConfirmation(movie);
            });

            pollGrid.appendChild(movieCard);
        });

        highlightSelectedMovie(votedMovie ? votedMovie.id : null);
        updateVotingDisabledState(hasVoted);
    }

    function handleBanClick(movie) {
        if (!movie) return;
        if (pollClosedByBan) {
            renderWinnerBanner(forcedWinner || movie);
            showToast('Голосование завершено из-за банов.', 'info');
            return;
        }

        if (isMovieBanned(movie)) {
            showToast('Фильм уже исключён из опроса.', 'info');
            return;
        }

        const activeMovies = getActiveMovies(moviesList);
        if (activeMovies.length <= 1) {
            showToast('Нельзя забанить последний фильм.', 'error');
            return;
        }

        openBanModal(movie);
    }

    function openVoteConfirmation(movie) {
        if (pollClosedByBan) {
            renderWinnerBanner(forcedWinner || movie);
            showMessage('Голосование завершено из-за банов.', 'info');
            return;
        }

        if (isMovieBanned(movie)) {
            showToast('Фильм уже исключён из опроса.', 'info');
            return;
        }

        selectedMovie = movie;
        voteConfirmPoster.src = movie.poster || PLACEHOLDER_POSTER;
        voteConfirmTitle.textContent = movie.name;
        voteConfirmYear.textContent = movie.year || '';
        if (voteConfirmPoints) {
            const pointsValue = getMoviePoints(movie);
            voteConfirmPoints.textContent = pointsValue > 0
                ? `+${formatPoints(pointsValue)} за голос`
                : 'Баллы не начисляются';
        }
        if (!isVoteModalOpen) {
            lockScroll();
            isVoteModalOpen = true;
            pushModalHistory('vote');
        }
        voteConfirmModal.style.display = 'flex';
    }

    function closeVoteConfirmation(options = {}) {
        const { fromPopState = false } = options;
        const wasTracked = modalHistoryStack.includes('vote');
        voteConfirmModal.style.display = 'none';
        selectedMovie = null;
        if (isVoteModalOpen) {
            unlockScroll();
            isVoteModalOpen = false;
        }
        removeModalFromHistory('vote');

        if (!fromPopState && wasTracked) {
            ignoreModalPopState = true;
            history.back();
        }
    }

    function openBanModal(movie) {
        if (!banModal || !banDaysInput || !banModalDescription) return;
        banTargetMovie = movie;
        resetBanModal();
        const movieYear = movie?.year ? ` (${movie.year})` : '';
        banModalDescription.textContent = `Исключить «${movie?.name || 'Фильм'}»${movieYear} из опроса.`;
        banDaysInput.value = '1';
        banModal.style.display = 'flex';
        if (!isBanModalOpen) {
            lockScroll();
            isBanModalOpen = true;
            pushModalHistory('ban');
        }
        banDaysInput.focus();
    }

    function closeBanModal(options = {}) {
        const { fromPopState = false } = options;
        const wasTracked = modalHistoryStack.includes('ban');
        if (banModal) {
            banModal.style.display = 'none';
        }
        banTargetMovie = null;
        resetBanModal();
        if (isBanModalOpen) {
            unlockScroll();
            isBanModalOpen = false;
        }
        removeModalFromHistory('ban');

        if (!fromPopState && wasTracked) {
            ignoreModalPopState = true;
            history.back();
        }
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

            const votedMovieData = result.voted_movie || selectedMovie || null;
            if (votedMovieData) {
                handleVotedState(votedMovieData, result.points_awarded);
            }

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

    function decodeHtmlEntities(htmlString) {
        if (typeof htmlString !== 'string') {
            return '';
        }
        const parser = new DOMParser();
        const doc = parser.parseFromString(htmlString, 'text/html');
        return doc.documentElement.textContent || '';
    }

    function initializePointsWidget() {
        if (!pointsBalanceLabel || !pointsBalanceStatus || !pointsStateBadge || !pointsProgressLabel) {
            return;
        }
        pointsBalanceLabel.textContent = T.pointsTitle;
        pointsBalanceStatus.textContent = T.pointsStatusEmpty;
        hidePointsBadge();
        pointsProgressLabel.textContent = T.pointsProgressDefault;
    }

    function ensureModalPopStateListener() {
        window.addEventListener('popstate', handleModalPopState);
    }

    function removeModalPopStateListenerIfIdle() {
        if (modalHistoryStack.length === 0) {
            window.removeEventListener('popstate', handleModalPopState);
        }
    }

    function pushModalHistory(modalId) {
        if (!modalId) return;
        const alreadyTracked = modalHistoryStack.includes(modalId);
        if (!alreadyTracked) {
            modalHistoryStack.push(modalId);
            ensureModalPopStateListener();
            history.pushState({ modal: modalId }, '', window.location.href);
        }
    }

    function removeModalFromHistory(modalId) {
        const index = modalHistoryStack.lastIndexOf(modalId);
        if (index !== -1) {
            modalHistoryStack.splice(index, 1);
        }
        removeModalPopStateListenerIfIdle();
    }

    function handleModalPopState() {
        if (ignoreModalPopState) {
            ignoreModalPopState = false;
            return;
        }

        const modalId = modalHistoryStack.pop();
        if (!modalId) {
            removeModalPopStateListenerIfIdle();
            return;
        }

        if (modalId === 'vote') {
            closeVoteConfirmation({ fromPopState: true });
        } else if (modalId === 'custom') {
            closeCustomVoteModal({ fromPopState: true });
        } else if (modalId === 'ban') {
            closeBanModal({ fromPopState: true });
        }

        removeModalPopStateListenerIfIdle();
    }

    function resetBanModal() {
        if (banModalError) {
            banModalError.hidden = true;
            banModalError.textContent = '';
        }
        if (banConfirmBtn) {
            banConfirmBtn.disabled = false;
            banConfirmBtn.textContent = 'Исключить';
        }
        if (banDaysInput) {
            banDaysInput.value = '1';
        }
    }

    function setBanModalError(text = '') {
        if (!banModalError) return;
        banModalError.textContent = text;
        banModalError.hidden = !text;
    }

    function applyBanResult(movieId, payload = {}) {
        moviesList = moviesList.map((movie) => {
            if (movie.id !== movieId) return movie;
            return {
                ...movie,
                ban_until: payload.ban_until || movie.ban_until,
                ban_status: payload.ban_status || 'active',
                ban_remaining_seconds: payload.ban_remaining_seconds ?? movie.ban_remaining_seconds,
            };
        });
    }

    async function submitBan() {
        if (!banTargetMovie || !banConfirmBtn) return;
        if (!banDaysInput) return;

        const activeMovies = getActiveMovies(moviesList);
        if (activeMovies.length <= 1) {
            setBanModalError('Нельзя забанить последний фильм.');
            return;
        }

        const days = Number.parseInt(banDaysInput.value, 10);
        if (!Number.isFinite(days) || days <= 0) {
            setBanModalError('Укажите длительность не менее 1 дня.');
            return;
        }

        setBanModalError('');
        banConfirmBtn.disabled = true;
        banConfirmBtn.textContent = 'Исключаем...';

        try {
            const response = await fetch(buildPollApiUrl(`/api/polls/${pollId}/ban`), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ movie_id: banTargetMovie.id, days }),
            });

            const result = await response.json();
            if (!response.ok) {
                if (result?.forced_winner) {
                    forcedWinner = result.forced_winner;
                    handlePollClosedByBan(forcedWinner);
                }
                throw new Error(result.error || 'Не удалось исключить фильм');
            }

            closeBanModal();
            applyBanResult(banTargetMovie.id, result);
            renderMovies(moviesList);
            updatePointsBalance(result.points_balance);

            const banMessage = `«${banTargetMovie.name}» исключён на ${days} ${declOfNum(days, ['день', 'дня', 'дней'])}.`;
            showToast(banMessage, 'success');

            if (result.closed_by_ban) {
                forcedWinner = result.forced_winner || getActiveMovies(moviesList)[0] || banTargetMovie;
                handlePollClosedByBan(forcedWinner);
            }

            try {
                await fetchPollData({ skipVoteHandling: true, showErrors: false });
            } catch (refreshError) {
                console.error('Не удалось обновить состояние опроса после бана', refreshError);
            }
        } catch (error) {
            console.error('Ошибка бана фильма:', error);
            setBanModalError(error.message || 'Не удалось исключить фильм.');
            banConfirmBtn.disabled = false;
            banConfirmBtn.textContent = 'Исключить';
        }
    }

    function renderWinnerBanner(winnerMovie) {
        if (!pollWinnerBanner) return;
        if (!pollClosedByBan) {
            pollWinnerBanner.hidden = true;
            pollWinnerBanner.textContent = '';
            return;
        }

        const winnerName = winnerMovie?.name ? `«${winnerMovie.name}»${winnerMovie.year ? ` (${winnerMovie.year})` : ''}` : 'одного из фильмов';
        pollWinnerBanner.hidden = false;
        pollWinnerBanner.innerHTML = `Голосование завершено из-за банов. Победитель: <strong>${escapeHtml(winnerName)}</strong>.`;
    }

    function handlePollClosedByBan(winnerMovie) {
        pollClosedByBan = true;
        forcedWinner = winnerMovie || forcedWinner;
        renderWinnerBanner(forcedWinner);
        pollDescription.textContent = 'Голосование завершено из-за банов.';
        showMessage('Голосование завершено из-за банов.', 'info');
        updateCustomVoteButtonState();
        renderMovies(moviesList);
    }

    function getPointsEarnedStorageKey() {
        if (!voterToken) return null;
        return `voter-${voterToken}-points-earned-total`;
    }

    function readStoredPointsEarnedTotal() {
        const storageKey = getPointsEarnedStorageKey();
        if (!storageKey || typeof localStorage === 'undefined') return null;
        try {
            const storedValue = localStorage.getItem(storageKey);
            const parsed = Number(storedValue);
            return Number.isFinite(parsed) ? Math.max(0, parsed) : null;
        } catch (error) {
            console.warn('Не удалось прочитать сохранённые баллы', error);
            return null;
        }
    }

    function persistPointsEarnedTotal(value) {
        const storageKey = getPointsEarnedStorageKey();
        if (!storageKey || typeof localStorage === 'undefined') return;
        try {
            localStorage.setItem(storageKey, String(Math.max(0, value)));
        } catch (error) {
            console.warn('Не удалось сохранить накопленные баллы', error);
        }
    }

    function updatePointsBalance(balance, totalEarned) {
        if (!pointsBalanceCard || !pointsBalanceValue || !pointsBalanceStatus || !pointsStateBadge) {
            return;
        }

        if (typeof balance !== 'number' || Number.isNaN(balance)) {
            markPointsAsUnavailable();
            return;
        }

        pointsBalance = balance;
        initializePointsEarnedTotal(totalEarned);
        pointsBalanceCard.classList.remove('points-balance-card-error');
        hidePointsBadge();
        pointsBalanceValue.textContent = balance;
        updatePointsStatus();
        updateCustomVoteButtonState();
    }

    function markPointsAsUnavailable() {
        if (!pointsBalanceCard || !pointsStateBadge || !pointsBalanceStatus) return;
        pointsBalance = null;
        pointsBalanceCard.classList.add('points-balance-card-error');
        showPointsBadge(T.pointsBadgeError);
        pointsBalanceStatus.textContent = T.pointsUnavailable;
        updateCustomVoteButtonState();
    }

    function hidePointsBadge() {
        if (!pointsStateBadge) return;
        pointsStateBadge.textContent = '';
        pointsStateBadge.setAttribute('aria-hidden', 'true');
        pointsStateBadge.classList.add('points-state-badge-hidden');
    }

    function showPointsBadge(text) {
        if (!pointsStateBadge) return;
        pointsStateBadge.textContent = text;
        pointsStateBadge.removeAttribute('aria-hidden');
        pointsStateBadge.classList.remove('points-state-badge-hidden');
    }

    function initializePointsEarnedTotal(initialTotal) {
        if (pointsEarnedTotal !== null) return;
        const storedTotal = readStoredPointsEarnedTotal();
        if (Number.isFinite(storedTotal)) {
            pointsEarnedTotal = storedTotal;
            return;
        }
        const parsed = Number(initialTotal);
        pointsEarnedTotal = Number.isFinite(parsed) ? Math.max(0, parsed) : 0;
        persistPointsEarnedTotal(pointsEarnedTotal);
    }

    function updatePointsStatus() {
        if (!pointsBalanceStatus) return;
        const totalEarned = Number.isFinite(pointsEarnedTotal) ? pointsEarnedTotal : 0;
        pointsBalanceStatus.textContent = T.pointsStatusUpdated(totalEarned);
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

        if (awarded > 0) {
            initializePointsEarnedTotal();
            pointsEarnedTotal += awarded;
            persistPointsEarnedTotal(pointsEarnedTotal);
            updatePointsStatus();
        }

        if (awarded < 0) {
            showToast(T.toastPointsDeducted(Math.abs(awarded)), 'info', { duration: 4000 });
            updateCustomVoteButtonState();
            return;
        }

        showToast(T.toastPointsEarned(awarded), 'success', { duration: 4000 });
        playPointsProgress(awarded);
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

    function formatCustomVoteCostPhrase(cost, { capitalized = false } = {}) {
        const normalizedCost = Number.isFinite(cost) ? cost : 0;
        const phrase = normalizedCost > 0
            ? `будет списано ${formatPoints(normalizedCost)} за голосование`
            : 'баллы не списываются за голосование';
        if (!capitalized || !phrase) {
            return phrase;
        }
        return `${phrase.charAt(0).toUpperCase()}${phrase.slice(1)}`;
    }

    function formatPointsBadge(points) {
        if (!Number.isFinite(points) || points <= 0) {
            return '0';
        }
        return `+${points}`;
    }

    function buildBanLabel(movie) {
        if (!movie) return 'Уже исключён';
        const banUntil = movie.ban_until ? new Date(movie.ban_until) : null;
        if (banUntil && !Number.isNaN(banUntil.getTime())) {
            return `Исключён до ${banUntil.toLocaleDateString('ru-RU')}`;
        }
        return 'Уже исключён';
    }

    function updateCustomVoteCostLabels(cost = customVoteCost) {
        const capitalizedPhrase = formatCustomVoteCostPhrase(cost, { capitalized: true });
        const baseButtonLabel = 'Проголосовать за свой фильм';

        if (customVoteBtn) {
            customVoteBtn.textContent = baseButtonLabel;
            customVoteBtn.title = capitalizedPhrase || baseButtonLabel;
        }

        if (customVoteCostDescription && capitalizedPhrase) {
            customVoteCostDescription.textContent = `${capitalizedPhrase}.`;
        }
    }

    function declOfNum(number, titles) {
        const cases = [2, 0, 1, 1, 1, 2];
        return titles[(number % 100 > 4 && number % 100 < 20) ? 2 : cases[(number % 10 < 5) ? number % 10 : 5]];
    }

    function handleVotedState(movieData, pointsDelta) {
        hasVoted = true;
        votedMovie = movieData;
        const normalizedDelta = Number(pointsDelta);
        votedMoviePointsDelta = Number.isFinite(normalizedDelta) ? normalizedDelta : null;
        selectedMovie = null;
        pollDescription.textContent = 'Вы уже проголосовали в этом опросе.';
        if (pollMessage) {
            pollMessage.style.display = 'none';
            pollMessage.textContent = '';
        }
        renderVotedMovie(movieData, votedMoviePointsDelta);
        highlightSelectedMovie(movieData.id);
        updateVotingDisabledState(true);
        updateCustomVoteButtonState();
    }

    function updateVotingDisabledState(disabled) {
        if (!pollGrid) return;
        if (disabled) {
            pollGrid.classList.add('poll-grid-disabled');
        } else {
            pollGrid.classList.remove('poll-grid-disabled');
        }
    }

    function highlightSelectedMovie(movieId) {
        if (!pollGrid) return;
        const cards = pollGrid.querySelectorAll('.poll-movie-card');
        cards.forEach(card => card.classList.remove('poll-movie-card-selected'));

        if (!movieId) {
            return;
        }

        const selectedCard = pollGrid.querySelector(`.poll-movie-card[data-movie-id="${movieId}"]`);
        if (selectedCard) {
            selectedCard.classList.add('poll-movie-card-selected');
        }
    }

    function renderVotedMovie(movieData, pointsDelta) {
        if (!votedMovieWrapper || !votedMovieCard) return;
        const poster = movieData.poster || PLACEHOLDER_POSTER;
        const normalizedDelta = Number(pointsDelta);
        const hasDelta = Number.isFinite(normalizedDelta);
        const absDelta = Math.abs(normalizedDelta);
        const pointsLine = hasDelta
            ? `<p class="poll-voted-points">${normalizedDelta >= 0 ? '+' : '−'}${formatPoints(absDelta)} ${normalizedDelta >= 0 ? 'начислено' : 'списано'}</p>`
            : '';
        votedMovieCard.innerHTML = `
            <img src="${poster}" alt="${escapeHtml(movieData.name)}">
            <div>
                <h3>${escapeHtml(movieData.name)}</h3>
                ${movieData.year ? `<p>${escapeHtml(movieData.year)}</p>` : ''}
                ${movieData.genres ? `<p>${escapeHtml(movieData.genres)}</p>` : ''}
                ${pointsLine}
            </div>
        `;
        votedMovieWrapper.style.display = 'block';
    }


    // Закрытие модального окна по клику вне его
    voteConfirmModal.addEventListener('click', (e) => {
        if (e.target === voteConfirmModal) {
            closeVoteConfirmation();
        }
    });

    banCancelBtn?.addEventListener('click', closeBanModal);
    banConfirmBtn?.addEventListener('click', submitBan);
    banModal?.addEventListener('click', (event) => {
        if (event.target === banModal) {
            closeBanModal();
        }
    });

    if (customVoteBtn && customVoteModal && customVoteCancelBtn && customVoteInput) {
        customVoteBtn.addEventListener('click', () => {
            if (pollClosedByBan) {
                renderWinnerBanner(forcedWinner);
                showToast('Голосование завершено из-за банов.', 'info');
                return;
            }
            if (hasVoted) {
                showToast('Вы уже проголосовали в этом опросе.', 'info');
                return;
            }

            if (!canUseCustomVote()) {
                showToast(buildCustomVoteInsufficientMessage(), 'error');
                return;
            }

            openCustomVoteModal();
        });

        customVoteCancelBtn.addEventListener('click', closeCustomVoteModal);

        customVoteInput?.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                searchCustomMovie();
            }
        });

        customVoteSearchBtn?.addEventListener('click', () => {
            if (!customVoteInput.value.trim()) {
                showCustomVoteError('Введите название фильма для поиска.');
                return;
            }
            searchCustomMovie();
        });

        customVoteSubmitBtn?.addEventListener('click', submitCustomVote);

        customVoteModal.addEventListener('click', (e) => {
            if (e.target === customVoteModal) {
                closeCustomVoteModal();
            }
        });
    }

    function openCustomVoteModal() {
        resetCustomVoteModal();
        customVoteModal.style.display = 'flex';
        if (!isCustomVoteModalOpen) {
            lockScroll();
            isCustomVoteModalOpen = true;
            pushModalHistory('custom');
        }
        customVoteInput.focus();
        showCustomVoteStatus('empty');
    }

    function closeCustomVoteModal(options = {}) {
        const { fromPopState = false } = options;
        const wasTracked = modalHistoryStack.includes('custom');
        customVoteModal.style.display = 'none';
        resetCustomVoteModal();
        if (isCustomVoteModalOpen) {
            unlockScroll();
            isCustomVoteModalOpen = false;
        }
        removeModalFromHistory('custom');

        if (!fromPopState && wasTracked) {
            ignoreModalPopState = true;
            history.back();
        }
    }

    function resetCustomVoteModal() {
        customVoteInput.value = '';
        customVoteQuery = '';
        customVoteMovie = null;
        isCustomVoteLoading = false;
        isCustomVoteSubmitting = false;
        customVoteResult.hidden = true;
        customVotePoster.style.backgroundImage = '';
        customVoteTitle.textContent = '';
        customVoteYear.textContent = '';
        customVoteRating.textContent = '';
        if (customVoteDescription) {
            customVoteDescription.textContent = '';
        }
        showCustomVoteStatus('hidden');
        updateCustomVoteActionsState();
    }

    function showCustomVoteStatus(state, errorText = '') {
        if (!customVoteStatus) return;
        customVoteStatus.hidden = state === 'hidden';
        if (customVoteStatusLoading) customVoteStatusLoading.hidden = state !== 'loading';
        if (customVoteStatusEmpty) customVoteStatusEmpty.hidden = state !== 'empty';
        if (customVoteStatusError) customVoteStatusError.hidden = state !== 'error';
        if (customVoteErrorText && state === 'error') {
            customVoteErrorText.textContent = errorText || 'Не удалось найти фильм. Попробуйте уточнить запрос.';
        }
    }

    async function searchCustomMovie() {
        if (isCustomVoteLoading || isCustomVoteSubmitting || !customVoteSearchBtn) return;
        const query = customVoteInput.value.trim();
        if (!query) {
            showCustomVoteError('Введите название фильма для поиска.');
            return;
        }

        isCustomVoteLoading = true;
        customVoteQuery = query;
        customVoteSearchBtn.disabled = true;
        customVoteInput.disabled = true;
        customVoteResult.hidden = true;
        showCustomVoteStatus('loading');
        updateCustomVoteActionsState();

        try {
            const movieData = await fetchMovieInfo(query);
            customVoteMovie = movieData;
            renderCustomVoteResult(movieData);
            showCustomVoteStatus('hidden');
            customVoteResult.hidden = false;
        } catch (error) {
            console.error('Ошибка поиска фильма:', error);
            showCustomVoteError(error.message || 'Не удалось найти фильм.');
            customVoteMovie = null;
        } finally {
            isCustomVoteLoading = false;
            customVoteSearchBtn.disabled = false;
            customVoteInput.disabled = false;
            updateCustomVoteActionsState();
        }
    }

    function renderCustomVoteResult(movieData) {
        const poster = movieData.poster || PLACEHOLDER_POSTER;
        customVotePoster.style.backgroundImage = `url('${poster}')`;
        customVoteTitle.textContent = escapeHtml(movieData.name || 'Без названия');
        customVoteYear.textContent = escapeHtml(movieData.year || '—');
        const rating = Number(movieData.rating_kp);
        customVoteRating.textContent = Number.isFinite(rating) ? `⭐ ${rating.toFixed(1)}` : '';
        const decodedDescription = decodeHtmlEntities(movieData.description || '').trim();
        customVoteDescription.textContent = decodedDescription || 'Описание отсутствует.';
    }

    function showCustomVoteError(text) {
        showCustomVoteStatus('error', text);
        customVoteResult.hidden = true;
        updateCustomVoteActionsState();
    }

    function canUseCustomVote() {
        return !hasVoted && !pollClosedByBan && typeof pointsBalance === 'number' && pointsBalance >= customVoteCost;
    }

    function buildCustomVoteInsufficientMessage() {
        const costPhrase = formatCustomVoteCostPhrase(customVoteCost, { capitalized: true });
        return costPhrase
            ? `Недостаточно баллов: ${costPhrase}.`
            : 'Недостаточно баллов для пользовательского голосования.';
    }

    function updateCustomVoteButtonState(options = {}) {
        if (!customVoteBtn) return;
        const balanceValue = typeof options.balance === 'number' ? options.balance : pointsBalance;
        const hasVoteFlag = typeof options.hasVoted === 'boolean' ? options.hasVoted : hasVoted;
        const canVoteCustom = typeof options.can_vote_custom === 'boolean'
            ? options.can_vote_custom
            : options.canVoteCustom;
        const effectiveBalance = typeof balanceValue === 'number' ? balanceValue : pointsBalance;
        const isBalanceKnown = Number.isFinite(effectiveBalance);
        const isInsufficient = isBalanceKnown ? effectiveBalance < customVoteCost : true;
        const disabled = Boolean(hasVoteFlag || isInsufficient || canVoteCustom === false || pollClosedByBan);

        customVoteBtn.disabled = disabled;
        if (customVoteWarning) {
            customVoteWarning.textContent = buildCustomVoteInsufficientMessage();
            customVoteWarning.hidden = !isInsufficient;
        }

        updateCustomVoteCostLabels();
    }

    function updateCustomVoteActionsState() {
        if (!customVoteSubmitBtn) return;
        const shouldDisableSubmit = !customVoteMovie || isCustomVoteLoading || isCustomVoteSubmitting || !canUseCustomVote();
        const disableInteractions = isCustomVoteLoading || isCustomVoteSubmitting || !canUseCustomVote();
        customVoteSubmitBtn.disabled = shouldDisableSubmit;
        if (customVoteSearchBtn) {
            customVoteSearchBtn.disabled = disableInteractions;
        }
        if (customVoteInput) {
            customVoteInput.disabled = disableInteractions;
        }
    }

    async function submitCustomVote() {
        if (!customVoteMovie || isCustomVoteSubmitting) return;
        if (!canUseCustomVote()) {
            showToast(buildCustomVoteInsufficientMessage(), 'error');
            return;
        }

        isCustomVoteSubmitting = true;
        updateCustomVoteActionsState();
        customVoteSubmitBtn.textContent = 'Отправка...';

        try {
            const payload = {
                query: customVoteQuery || customVoteMovie.name,
                kinopoisk_id: customVoteMovie.kinopoisk_id,
                movie: customVoteMovie,
            };
            const response = await fetch(buildPollApiUrl(`/api/polls/${pollId}/custom-vote`), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(payload),
            });

            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || 'Не удалось отправить голос');
            }

            closeCustomVoteModal();
            showMessage('Голос учтён!', 'success');
            const normalizedDelta = Number(result.points_awarded);
            const pointsDelta = Number.isFinite(normalizedDelta) ? normalizedDelta : -customVoteCost;
            handlePointsAfterVote({
                points_awarded: pointsDelta,
                points_balance: result.points_balance,
            });

            const newMovie = result.movie || customVoteMovie;
            if (newMovie) {
                moviesList.push(newMovie);
                renderMovies(moviesList);
                handleVotedState(newMovie, pointsDelta);
            }
        } catch (error) {
            console.error('Ошибка отправки пользовательского голоса:', error);
            showCustomVoteError(error.message || 'Не удалось отправить голос.');
        } finally {
            isCustomVoteSubmitting = false;
            if (customVoteSubmitBtn) {
                customVoteSubmitBtn.textContent = 'Проголосовать';
            }
            updateCustomVoteActionsState();
        }
    }
});

