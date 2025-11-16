// movie_lottery/static/js/pages/poll.js

import { buildPollApiUrl } from '../utils/polls.js';

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

    let selectedMovie = null;
    let progressTimeoutId = null;
    let hasVoted = false;
    let votedMovie = null;
    let isVoteModalOpen = false;
    const touchMoveOptions = { passive: false };
    const scrollLockManager = createScrollLockManager();
    const PLACEHOLDER_POSTER = 'https://via.placeholder.com/200x300.png?text=No+Image';

    initializePointsWidget();

    const getMoviePoints = (movie) => {
        const rawPoints = movie?.points;
        const parsed = Number.parseInt(rawPoints, 10);
        if (Number.isNaN(parsed)) {
            return 1;
        }
        return Math.min(999, Math.max(0, parsed));
    };

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

        // Отображаем фильмы
        renderMovies(pollData.movies);
        pollDescription.textContent = `Выберите один фильм из ${pollData.movies.length}. Проголосовало: ${pollData.total_votes}`;

        if (pollData.has_voted) {
            hasVoted = true;
            if (pollData.voted_movie) {
                handleVotedState(pollData.voted_movie);
            } else {
                showMessage('Вы уже проголосовали в этом опросе.', 'info');
                updateVotingDisabledState(true);
            }
        }

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

            movieCard.addEventListener('click', () => {
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

    function openVoteConfirmation(movie) {
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
            scrollLockManager.lock();
            isVoteModalOpen = true;
        }
        voteConfirmModal.style.display = 'flex';
    }

    function closeVoteConfirmation() {
        voteConfirmModal.style.display = 'none';
        selectedMovie = null;
        if (isVoteModalOpen) {
            scrollLockManager.unlock();
            isVoteModalOpen = false;
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
                handleVotedState(votedMovieData);
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

    function createScrollLockManager() {
        const state = {
            isLocked: false,
            scrollPosition: 0,
            previousBodyStyles: {
                position: '',
                top: '',
                width: '',
                overflow: '',
                paddingRight: '',
            },
            touchMoveHandler: null,
        };

        function preventBackgroundTouchMove(event) {
            if (event.target.closest('.modal-content')) {
                return;
            }
            event.preventDefault();
        }

        function lock() {
            if (state.isLocked) {
                return;
            }

            state.isLocked = true;
            state.scrollPosition = window.scrollY || document.documentElement.scrollTop || 0;
            state.previousBodyStyles = {
                position: document.body.style.position,
                top: document.body.style.top,
                width: document.body.style.width,
                overflow: document.body.style.overflow,
                paddingRight: document.body.style.paddingRight,
            };

            const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth;

            document.documentElement.classList.add('no-scroll');
            document.body.classList.add('no-scroll');

            document.body.style.top = `-${state.scrollPosition}px`;
            document.body.style.position = 'fixed';
            document.body.style.width = '100%';
            document.body.style.overflow = 'hidden';
            if (scrollbarWidth > 0) {
                document.body.style.paddingRight = `${scrollbarWidth}px`;
            }

            state.touchMoveHandler = preventBackgroundTouchMove;
            document.addEventListener('touchmove', state.touchMoveHandler, touchMoveOptions);
        }

        function unlock() {
            if (!state.isLocked) {
                return;
            }

            document.documentElement.classList.remove('no-scroll');
            document.body.classList.remove('no-scroll');

            document.body.style.position = state.previousBodyStyles.position;
            document.body.style.top = state.previousBodyStyles.top;
            document.body.style.width = state.previousBodyStyles.width;
            document.body.style.overflow = state.previousBodyStyles.overflow;
            document.body.style.paddingRight = state.previousBodyStyles.paddingRight;

            if (state.touchMoveHandler) {
                document.removeEventListener('touchmove', state.touchMoveHandler, touchMoveOptions);
                state.touchMoveHandler = null;
            }

            requestAnimationFrame(() => {
                window.scrollTo(0, state.scrollPosition);
                state.scrollPosition = 0;
            });

            state.isLocked = false;
        }

        return { lock, unlock };
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function initializePointsWidget() {
        if (!pointsBalanceLabel || !pointsBalanceStatus || !pointsStateBadge || !pointsProgressLabel) {
            return;
        }
        pointsBalanceLabel.textContent = T.pointsTitle;
        pointsBalanceStatus.textContent = T.pointsStatusEmpty;
        pointsStateBadge.textContent = T.pointsBadgeEmpty;
        pointsProgressLabel.textContent = T.pointsProgressDefault;
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

    function formatPointsBadge(points) {
        if (!Number.isFinite(points) || points <= 0) {
            return '0';
        }
        return `+${points}`;
    }

    function declOfNum(number, titles) {
        const cases = [2, 0, 1, 1, 1, 2];
        return titles[(number % 100 > 4 && number % 100 < 20) ? 2 : cases[(number % 10 < 5) ? number % 10 : 5]];
    }

    function handleVotedState(movieData) {
        hasVoted = true;
        votedMovie = movieData;
        selectedMovie = null;
        pollDescription.textContent = 'Вы уже проголосовали в этом опросе.';
        showMessage(`Вы уже проголосовали за «${movieData.name}».`, 'info');
        renderVotedMovie(movieData);
        highlightSelectedMovie(movieData.id);
        updateVotingDisabledState(true);
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

    function renderVotedMovie(movieData) {
        if (!votedMovieWrapper || !votedMovieCard) return;
        const poster = movieData.poster || PLACEHOLDER_POSTER;
        const pointsValue = getMoviePoints(movieData);
        const pointsLine = pointsValue > 0
            ? `<p class="poll-voted-points">+${formatPoints(pointsValue)} за ваш голос</p>`
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
});

