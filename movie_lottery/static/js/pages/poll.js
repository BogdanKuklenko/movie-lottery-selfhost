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
    const banMonthsInput = document.getElementById('ban-months-input');
    const banPresetButtons = Array.from(document.querySelectorAll('[data-ban-preset]'));
    const banStepButtons = Array.from(document.querySelectorAll('[data-ban-step]'));
    const banModalDescription = document.getElementById('ban-modal-description');
    const banModalError = document.getElementById('ban-modal-error');
    const banLabelFormula = document.getElementById('ban-label-formula');
    const banTotalCost = document.getElementById('ban-total-cost');
    const pollWinnerBanner = document.getElementById('poll-winner-banner');
    const logoutButton = document.getElementById('logout-button');
    const userOnboardingModal = document.getElementById('user-onboarding-modal');
    const userOnboardingInput = document.getElementById('user-onboarding-input');
    const userOnboardingError = document.getElementById('user-onboarding-error');
    const userOnboardingSubmit = document.getElementById('user-onboarding-submit');
    const userOnboardingSuggestions = document.getElementById('user-onboarding-suggestions');
    const userOnboardingSuggestionsList = document.getElementById('user-onboarding-suggestions-list');
    const userSwitchModal = document.getElementById('user-switch-modal');
    const userSwitchInput = document.getElementById('user-switch-input');
    const userSwitchError = document.getElementById('user-switch-error');
    const userSwitchSubmit = document.getElementById('user-switch-submit');
    const userSwitchCancel = document.getElementById('user-switch-cancel');
    const userSwitchSuggestions = document.getElementById('user-switch-suggestions');
    const userSwitchSuggestionsList = document.getElementById('user-switch-suggestions-list');

    const TEXTS = {
        ru: {
            pointsTitle: 'Ваши баллы',
            pointsStatusEmpty: 'Баллы ещё не начислены',
            pointsStatusUpdated: (points) => `Всего начислено ${points}`,
            pointsBadgeEmpty: '—',
            pointsBadgeError: '—',
            pointsProgressDefault: 'Начисляем баллы…',
            pointsProgressEarned: (points) => `+${points} за голос`,
            pointsProgressDeducted: (points) => `−${points} за исключение`,
            toastPointsEarned: (points) => `+${points} баллов за голос`,
            toastPointsDeducted: (points) => `−${points} баллов списано`,
            toastPointsError: 'Не удалось обновить баланс баллов',
            pointsUnavailable: 'Баллы недоступны. Попробуйте обновить страницу позже.',
        },
    };

    const locale = 'ru';
    const T = TEXTS[locale];

    const VOTER_TOKEN_COOKIE = 'voter_token';
    const VOTER_USER_ID_COOKIE = 'voter_user_id';

    const getCookieValue = (cookieName) => {
        if (typeof document === 'undefined' || !cookieName) return '';
        return document.cookie
            .split(';')
            .map((entry) => entry.trim())
            .find((entry) => entry.startsWith(`${cookieName}=`))
            ?.split('=')[1] || '';
    };

    const deleteCookie = (cookieName) => {
        if (typeof document === 'undefined' || !cookieName) return;
        const secureFlag = window.location.protocol === 'https:' ? '; Secure' : '';
        document.cookie = `${cookieName}=; Max-Age=0; Path=/; SameSite=Lax${secureFlag}`;
    };

    const normalizeUserId = (value) => {
        if (value === undefined || value === null) return '';
        const normalized = String(value).trim();
        return normalized ? normalized.slice(0, 128) : '';
    };

    const pointsBalanceCard = document.getElementById('points-widget');
    const pointsBalanceLabel = document.getElementById('points-balance-label');
    const pointsBalanceValue = document.getElementById('points-balance-value');
    const pointsBalanceStatus = document.getElementById('points-balance-status');
    const pointsStateBadge = document.getElementById('points-state-badge');
    const pointsProgress = document.getElementById('points-progress');
    const pointsProgressBar = document.getElementById('points-progress-bar');
    const pointsProgressLabel = document.getElementById('points-progress-label');

    // Streak elements
    const streakIndicator = document.getElementById('streak-indicator');
    const streakCount = document.getElementById('streak-count');
    const streakWidget = document.getElementById('streak-widget');
    const streakDays = document.getElementById('streak-days');
    const streakProgressBar = document.getElementById('streak-progress-bar');
    const streakCurrentBonus = document.getElementById('streak-current-bonus');
    const streakNextBonus = document.getElementById('streak-next-bonus');

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

    const hadInitialVoterToken = Boolean(getCookieValue(VOTER_TOKEN_COOKIE));

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
    let isLogoutInProgress = false;
    let isUserOnboardingModalOpen = false;
    let isUserOnboardingSubmitting = false;
    let shouldRequestUserId = !hadInitialVoterToken;
    let isUserSwitchModalOpen = false;
    let lastKnownUserId = normalizeUserId(getCookieValue(VOTER_USER_ID_COOKIE));
    let moviesList = [];
    let banTargetMovie = null;
    let isBanModalOpen = false;
    let pollClosedByBan = false;
    let forcedWinner = null;
    let isTrailerModalOpen = false;
    let lastTrailerSource = null;
    let lastTrailerMimeType = null;
    let lastTrailerMovieName = null;
    let currentStreak = null;
    const PLACEHOLDER_POSTER = 'https://via.placeholder.com/200x300.png?text=No+Image';

    // Элементы медиаплеера трейлера
    const trailerPlayerModal = document.getElementById('trailer-player-modal');
    const trailerPlayerTitle = document.getElementById('trailer-player-title');
    const trailerVideo = document.getElementById('trailer-video');
    const trailerPlayerClose = trailerPlayerModal?.querySelector('.trailer-player-close');
    const trailerPlayerError = document.getElementById('trailer-player-error');
    const trailerPlayerWrapper = document.getElementById('trailer-player-wrapper');
    const trailerLoadingIndicator = document.getElementById('trailer-player-loading');
    const trailerLoadingLabel = document.getElementById('trailer-player-loading-text');
    const trailerErrorText = document.getElementById('trailer-player-error-text');
    const trailerRetryButton = document.getElementById('trailer-retry-button');
    
    // Video.js плеер
    let trailerPlayer = null;

    const RECENT_USER_IDS_KEY = 'pollRecentUserIds';

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

    const readRecentUserIds = () => {
        if (typeof localStorage === 'undefined') return [];
        try {
            const stored = localStorage.getItem(RECENT_USER_IDS_KEY);
            const parsed = JSON.parse(stored);
            if (!Array.isArray(parsed)) return [];
            return parsed
                .map(normalizeUserId)
                .filter(Boolean)
                .slice(0, 6);
        } catch (error) {
            console.warn('Не удалось прочитать сохранённые ID', error);
            return [];
        }
    };

    const storeRecentUserIds = (ids) => {
        if (typeof localStorage === 'undefined') return;
        try {
            localStorage.setItem(RECENT_USER_IDS_KEY, JSON.stringify(ids.slice(0, 6)));
        } catch (error) {
            console.warn('Не удалось сохранить список ID', error);
        }
    };

    const rememberUserId = (userId) => {
        const normalized = normalizeUserId(userId);
        if (!normalized) return;
        const existing = readRecentUserIds().filter((id) => id !== normalized);
        existing.unshift(normalized);
        storeRecentUserIds(existing);
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

        const userIdFromResponse = normalizeUserId(pollData.user_id);
        if (userIdFromResponse) {
            lastKnownUserId = userIdFromResponse;
            rememberUserId(userIdFromResponse);
            shouldRequestUserId = false;
        } else if (pollData?.voter_token) {
            shouldRequestUserId = true;
            if (!isUserOnboardingModalOpen) {
                openUserOnboardingModal({ suggestedId: lastKnownUserId });
            }
        }

        voterToken = pollData.voter_token || voterToken;
        updatePointsBalance(pollData.points_balance, pollData.points_earned_total);
        updateStreakUI(pollData.streak);
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

    if (shouldRequestUserId) {
        openUserOnboardingModal({ suggestedId: lastKnownUserId });
    }

    function renderMovies(movies) {
        moviesList = Array.isArray(movies) ? movies : [];
        pollGrid.innerHTML = '';

        const maxPoints = moviesList.reduce((max, movie) => {
            const pointsValue = getMoviePoints(movie);
            return pointsValue > max ? pointsValue : max;
        }, 0);

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
            if (pointsValue === maxPoints && moviesList.length > 0) {
                badgeClasses.push('poll-movie-points-badge--max');
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
            
            // Кнопка просмотра трейлера с удержанием
            if (movie.has_trailer) {
                const trailerBtn = document.createElement('button');
                trailerBtn.type = 'button';
                trailerBtn.className = 'poll-trailer-button';
                const trailerCost = movie.trailer_view_cost ?? 1;
                trailerBtn.innerHTML = `<span class="poll-trailer-button-icon">▶</span>${trailerCost > 0 ? `<span class="poll-trailer-cost">−${trailerCost}</span>` : ''}`;
                trailerBtn.title = trailerCost > 0 ? `Удерживайте (${trailerCost} б.)` : 'Удерживайте';
                
                setupHoldToConfirm(trailerBtn, () => {
                    handleTrailerClick(movie);
                }, 2000, trailerCost);
                
                actions.appendChild(trailerBtn);
            }
            
            const banBtn = document.createElement('button');
            banBtn.type = 'button';
            banBtn.className = 'secondary-button poll-ban-button';
            if (isBanned) {
                banBtn.classList.add('poll-ban-button-static');
                banBtn.textContent = buildBanLabelShort(movie);
                banBtn.setAttribute('aria-disabled', 'true');
            } else {
                banBtn.textContent = 'Исключить';
                banBtn.title = 'Исключить из опроса';
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

    // --- Функционал просмотра трейлера ---
    function updateTrailerLoadingState(isLoading, text = 'Загружаем трейлер…') {
        if (trailerPlayerWrapper) {
            trailerPlayerWrapper.classList.toggle('is-loading', Boolean(isLoading));
        }
        if (trailerLoadingIndicator) {
            trailerLoadingIndicator.hidden = !isLoading;
        }
        if (trailerLoadingLabel && text) {
            trailerLoadingLabel.textContent = text;
        }
    }

    function hideTrailerError() {
        if (!trailerPlayerError) return;
        trailerPlayerError.style.display = 'none';
        // Показываем Video.js контейнер
        const vjsContainer = trailerPlayerWrapper?.querySelector('.video-js');
        if (vjsContainer) {
            vjsContainer.style.display = 'block';
        }
    }

    function showTrailerError(message = 'Не удалось загрузить трейлер') {
        if (!trailerPlayerError) return;
        if (trailerErrorText) {
            trailerErrorText.textContent = message;
        }
        trailerPlayerError.style.display = 'block';
        // Скрываем Video.js контейнер при ошибке
        const vjsContainer = trailerPlayerWrapper?.querySelector('.video-js');
        if (vjsContainer) {
            vjsContainer.style.display = 'none';
        }
        updateTrailerLoadingState(false);
    }

    // --- Video.js инициализация ---
    function initVideoJsPlayer() {
        if (trailerPlayer || !trailerVideo || typeof videojs === 'undefined') return;
        
        // Русская локализация (до создания плеера)
        videojs.addLanguage('ru', {
            'Play': 'Воспроизвести',
            'Pause': 'Пауза',
            'Mute': 'Без звука',
            'Unmute': 'Со звуком',
            'Fullscreen': 'Полный экран',
            'Exit Fullscreen': 'Выйти из полного экрана',
            'Non-Fullscreen': 'Выйти из полного экрана',
            'Current Time': 'Текущее время',
            'Duration': 'Длительность',
            'Remaining Time': 'Оставшееся время',
            'Progress Bar': 'Прогресс',
            'Volume Level': 'Уровень громкости',
            'Picture-in-Picture': 'Картинка в картинке',
            'Close': 'Закрыть'
        });

        trailerPlayer = videojs('trailer-video', {
            controls: true,
            autoplay: false,
            preload: 'auto',
            fill: true,  // Заполняем родительский контейнер
            playsinline: true,
            responsive: true,
            language: 'ru',
            html5: {
                vhs: {
                    overrideNative: true
                },
                nativeAudioTracks: false,
                nativeVideoTracks: false
            },
            controlBar: {
                volumePanel: {
                    inline: false  // Вертикальная панель громкости
                },
                children: [
                    'playToggle',
                    'volumePanel',
                    'currentTimeDisplay',
                    'timeDivider',
                    'durationDisplay',
                    'progressControl',
                    'fullscreenToggle'
                ]
            },
            userActions: {
                doubleClick: false,
                hotkeys: true  // Включаем горячие клавиши
            }
        });

        // События плеера
        // При буферизации используем только стандартный спиннер Video.js (vjs-loading-spinner)
        // Наш кастомный спиннер показываем только при первоначальной загрузке

        trailerPlayer.on('playing', () => {
            updateTrailerLoadingState(false);
        });

        trailerPlayer.on('canplay', () => {
            updateTrailerLoadingState(false);
        });

        trailerPlayer.on('error', () => {
            console.error('Video.js ошибка воспроизведения');
            showTrailerError('Не удалось загрузить трейлер');
        });

        // Обработка fullscreen для поворота экрана на мобильных
        trailerPlayer.on('fullscreenchange', handleVideoFullscreenChange);
    }

    // Определяем мобильное устройство
    function isMobileDevice() {
        return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
               (window.innerWidth <= 768 && 'ontouchstart' in window);
    }

    // Блокируем ориентацию экрана в landscape при fullscreen на мобильных
    async function lockScreenOrientation() {
        if (!isMobileDevice()) return;
        
        try {
            if (screen.orientation && screen.orientation.lock) {
                await screen.orientation.lock('landscape');
                console.log('[Video.js] Screen orientation locked to landscape');
            }
        } catch (e) {
            // Screen Orientation API может быть недоступен или заблокирован
            console.log('[Video.js] Screen orientation lock not supported:', e.message);
        }
    }

    // Разблокируем ориентацию экрана
    function unlockScreenOrientation() {
        try {
            if (screen.orientation && screen.orientation.unlock) {
                screen.orientation.unlock();
                console.log('[Video.js] Screen orientation unlocked');
            }
        } catch (e) {
            // Игнорируем ошибки разблокировки
        }
    }

    // Обработчик изменения fullscreen состояния Video.js
    function handleVideoFullscreenChange() {
        if (!trailerPlayer) return;
        
        const isFullscreen = trailerPlayer.isFullscreen();
        
        if (isFullscreen) {
            // Входим в fullscreen - блокируем в landscape
            lockScreenOrientation();
            // Добавляем класс для стилей
            if (trailerPlayerModal) {
                trailerPlayerModal.classList.add('is-native-fullscreen');
            }
        } else {
            // Выходим из fullscreen - разблокируем ориентацию
            unlockScreenOrientation();
            // Убираем класс
            if (trailerPlayerModal) {
                trailerPlayerModal.classList.remove('is-native-fullscreen');
            }
        }
    }

    // Инициализируем Video.js при загрузке страницы
    if (typeof videojs !== 'undefined') {
        initVideoJsPlayer();
    } else {
        // Ждём загрузки Video.js
        window.addEventListener('load', initVideoJsPlayer);
    }

    function resetTrailerPlayerSource() {
        if (trailerPlayer) {
            trailerPlayer.pause();
            trailerPlayer.reset();
        }
    }

    async function handleTrailerClick(movie) {
        if (!movie || !movie.has_trailer) {
            showToast('Трейлер недоступен для этого фильма.', 'info');
            return;
        }

        const trailerCost = movie.trailer_view_cost ?? 1;
        
        // Проверяем баланс перед показом трейлера
        if (trailerCost > 0 && (pointsBalance === null || pointsBalance < trailerCost)) {
            showToast(`Недостаточно баллов для просмотра трейлера. Требуется ${trailerCost} баллов.`, 'error');
            return;
        }

        // СРАЗУ открываем модальное окно с индикатором загрузки (без задержки после подтверждения)
        openTrailerModalLoading(movie.name);

        try {
            const response = await fetch(buildPollApiUrl(`/api/polls/${pollId}/watch-trailer`), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ movie_id: movie.id }),
                credentials: 'include'
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || 'Не удалось загрузить трейлер');
            }

            // Обновляем баланс с анимацией если были списаны баллы
            if (result.cost_deducted > 0) {
                updatePointsBalance(result.points_balance, result.points_earned_total, true);
                showToast(`−${result.cost_deducted} баллов за просмотр трейлера`, 'info');
            }

            // Загружаем и воспроизводим трейлер
            loadAndPlayTrailer(result.trailer_url, result.trailer_mime_type);

        } catch (error) {
            console.error('Ошибка при загрузке трейлера:', error);
            showTrailerError(error.message || 'Не удалось загрузить трейлер');
        }
    }

    // Открывает модальное окно плеера сразу с индикатором загрузки
    function openTrailerModalLoading(movieName) {
        if (!trailerPlayerModal) return;

        if (trailerPlayerTitle) {
            trailerPlayerTitle.textContent = movieName;
        }

        lastTrailerMovieName = movieName;

        // Сбрасываем Video.js плеер
        if (trailerPlayer) {
            trailerPlayer.pause();
            trailerPlayer.reset();
        }

        hideTrailerError();
        updateTrailerLoadingState(true, 'Загружаем трейлер…');

        // Показываем Video.js контейнер
        const vjsContainer = trailerPlayerWrapper?.querySelector('.video-js');
        if (vjsContainer) {
            vjsContainer.style.display = 'block';
        }

        // Открываем модальное окно
        trailerPlayerModal.style.display = 'flex';
        if (!isTrailerModalOpen) {
            lockScroll();
            isTrailerModalOpen = true;
            pushModalHistory('trailer');
        }
    }

    // Загружает и воспроизводит трейлер (после получения URL от сервера)
    function loadAndPlayTrailer(trailerUrl, mimeType) {
        if (!trailerPlayer) {
            // Инициализируем плеер если ещё не инициализирован
            initVideoJsPlayer();
            if (!trailerPlayer) {
                showTrailerError('Плеер недоступен');
                return;
            }
        }

        lastTrailerSource = trailerUrl;
        lastTrailerMimeType = mimeType || 'video/mp4';

        // Устанавливаем источник через Video.js API
        trailerPlayer.src({
            src: trailerUrl,
            type: lastTrailerMimeType
        });

        // Автостарт воспроизведения
        trailerPlayer.ready(() => {
            const playPromise = trailerPlayer.play();
            
            if (playPromise && typeof playPromise.catch === 'function') {
                playPromise.catch((err) => {
                    const message = (err && err.message ? String(err.message) : '').toLowerCase();
                    const isAutoplayBlocked = message.includes('play()') || message.includes('user didn') || message.includes('interact');
                    if (isAutoplayBlocked) {
                        console.warn('Автовоспроизведение заблокировано - нажмите на видео для запуска');
                        updateTrailerLoadingState(false);
                        // Video.js покажет кнопку play
                    } else {
                        console.error('Сбой запуска трейлера:', err);
                        showTrailerError('Не удалось запустить трейлер. Попробуйте ещё раз.');
                    }
                });
            }
        });
    }

    function openTrailerModal(movieName, trailerUrl, mimeType) {
        if (!trailerPlayerModal) return;

        if (trailerPlayerTitle) {
            trailerPlayerTitle.textContent = movieName;
        }

        lastTrailerSource = trailerUrl;
        lastTrailerMimeType = mimeType || 'video/mp4';
        lastTrailerMovieName = movieName;

        hideTrailerError();
        updateTrailerLoadingState(true, 'Загружаем трейлер…');

        // Показываем Video.js контейнер
        const vjsContainer = trailerPlayerWrapper?.querySelector('.video-js');
        if (vjsContainer) {
            vjsContainer.style.display = 'block';
        }

        // Открываем модальное окно
        trailerPlayerModal.style.display = 'flex';
        if (!isTrailerModalOpen) {
            lockScroll();
            isTrailerModalOpen = true;
            pushModalHistory('trailer');
        }

        // Загружаем и воспроизводим через Video.js
        loadAndPlayTrailer(trailerUrl, mimeType);
    }

    function closeTrailerModal(options = {}) {
        const { fromPopState = false } = options;
        const wasTracked = modalHistoryStack.includes('trailer');
        
        // Выходим из fullscreen Video.js если активен
        if (trailerPlayer && trailerPlayer.isFullscreen()) {
            trailerPlayer.exitFullscreen();
        }
        
        // Разблокируем ориентацию экрана
        unlockScreenOrientation();
        
        if (trailerPlayerModal) {
            trailerPlayerModal.style.display = 'none';
            trailerPlayerModal.classList.remove('is-native-fullscreen');
        }
        
        resetTrailerPlayerSource();
        hideTrailerError();
        updateTrailerLoadingState(false);
        
        if (isTrailerModalOpen) {
            unlockScroll();
            isTrailerModalOpen = false;
        }
        
        removeModalFromHistory('trailer');

        if (!fromPopState && wasTracked) {
            ignoreModalPopState = true;
            history.back();
        }
    }

    // Обработчики для модального окна трейлера
    if (trailerPlayerClose) {
        trailerPlayerClose.addEventListener('click', closeTrailerModal);
    }
    if (trailerPlayerModal) {
        trailerPlayerModal.addEventListener('click', (e) => {
            if (e.target === trailerPlayerModal) {
                closeTrailerModal();
            }
        });
    }

    // Video.js события для закрытия модального окна
    function setupPlayerEndedHandler() {
        if (trailerPlayer) {
            trailerPlayer.on('ended', () => {
                if (isTrailerModalOpen) {
                    closeTrailerModal();
                }
            });
        }
    }
    
    // Инициализируем обработчик когда плеер готов
    if (trailerPlayer) {
        setupPlayerEndedHandler();
    } else {
        // Ждём инициализации плеера
        const checkPlayer = setInterval(() => {
            if (trailerPlayer) {
                setupPlayerEndedHandler();
                clearInterval(checkPlayer);
            }
        }, 100);
        // Отменяем проверку через 5 секунд
        setTimeout(() => clearInterval(checkPlayer), 5000);
    }

    if (trailerRetryButton) {
        trailerRetryButton.addEventListener('click', () => {
            if (!lastTrailerSource) return;
            hideTrailerError();
            updateTrailerLoadingState(true, 'Повторяем воспроизведение…');
            loadAndPlayTrailer(lastTrailerSource, lastTrailerMimeType);
        });
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
            const basePoints = getMoviePoints(movie);
            const streakBonus = currentStreak?.current_bonus || 0;
            const totalPoints = basePoints + streakBonus;
            
            if (basePoints <= 0) {
                voteConfirmPoints.textContent = 'Баллы не начисляются';
            } else if (streakBonus > 0) {
                voteConfirmPoints.innerHTML = `
                    <span class="vote-confirm-points-total">+${formatPoints(totalPoints)} за голос</span>
                    <span class="vote-confirm-points-breakdown">
                        <span class="vote-confirm-points-base">${basePoints} базовых</span>
                        <span class="vote-confirm-points-bonus">+${streakBonus} 🔥 бонус</span>
                    </span>`;
            } else {
                voteConfirmPoints.textContent = `+${formatPoints(basePoints)} за голос`;
            }
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
        if (!banModal || !banMonthsInput || !banModalDescription) return;
        banTargetMovie = movie;
        resetBanModal();
        const movieYear = movie?.year ? ` (${movie.year})` : '';
        banModalDescription.textContent = `Исключить «${movie?.name || 'Фильм'}»${movieYear} из опроса.`;
        
        // Получаем цену за месяц бана (по умолчанию 1)
        const costPerMonth = movie?.ban_cost_per_month ?? 1;
        
        // Устанавливаем начальное значение месяцев и обновляем отображение стоимости
        const initialMonths = 1;
        setBanMonthsValue(initialMonths);
        updateBanCostDisplay(costPerMonth, initialMonths);
        
        banModal.style.display = 'flex';
        if (!isBanModalOpen) {
            lockScroll();
            isBanModalOpen = true;
            pushModalHistory('ban');
        }
    }

    function updateBanCostDisplay(costPerMonth, months = null) {
        if (!banLabelFormula) return;
        
        // Обновляем текст "1 месяц = X балл(ов)"
        const costText = costPerMonth === 1 
            ? '(1 месяц = 1 балл)'
            : `(1 месяц = ${costPerMonth} ${declOfNum(costPerMonth, ['балл', 'балла', 'баллов'])})`;
        banLabelFormula.textContent = costText;
        
        // Обновляем общую стоимость, если указано количество месяцев
        if (banTotalCost && months !== null) {
            const totalCost = costPerMonth * months;
            banTotalCost.textContent = `Итого: ${totalCost} ${declOfNum(totalCost, ['балл', 'балла', 'баллов'])}`;
            banTotalCost.style.display = 'block';
        } else if (banTotalCost) {
            banTotalCost.style.display = 'none';
        }
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
        if (modalId === 'user-onboarding' && shouldRequestUserId) {
            return;
        }
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
        } else if (modalId === 'trailer') {
            closeTrailerModal({ fromPopState: true });
        } else if (modalId === 'user-onboarding') {
            if (shouldRequestUserId) {
                openUserOnboardingModal({ suggestedId: lastKnownUserId });
            } else {
                closeUserOnboardingModal({ fromPopState: true });
            }
        } else if (modalId === 'user-switch') {
            closeUserSwitchModal({ fromPopState: true });
        }

        removeModalPopStateListenerIfIdle();
    }

    function setUserOnboardingError(text) {
        if (!userOnboardingError) return;
        if (text) {
            userOnboardingError.textContent = text;
            userOnboardingError.hidden = false;
        } else {
            userOnboardingError.textContent = '';
            userOnboardingError.hidden = true;
        }
    }

    function setUserOnboardingLoading(isLoading) {
        isUserOnboardingSubmitting = isLoading;
        if (userOnboardingSubmit) {
            userOnboardingSubmit.disabled = isLoading;
            userOnboardingSubmit.textContent = isLoading ? 'Сохраняем...' : 'Сохранить ID';
        }
        if (userOnboardingInput) {
            userOnboardingInput.disabled = isLoading;
        }
        if (userOnboardingSuggestionsList) {
            Array.from(userOnboardingSuggestionsList.querySelectorAll('button')).forEach((button) => {
                button.disabled = isLoading;
            });
        }
    }

    function renderUserOnboardingSuggestions(suggestions = []) {
        if (!userOnboardingSuggestions || !userOnboardingSuggestionsList) return;

        const normalized = Array.isArray(suggestions)
            ? suggestions.map(normalizeUserId).filter(Boolean)
            : [];

        userOnboardingSuggestionsList.innerHTML = '';
        if (normalized.length === 0) {
            userOnboardingSuggestions.hidden = true;
            return;
        }

        userOnboardingSuggestions.hidden = false;
        normalized.slice(0, 5).forEach((suggestion) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'user-switch-chip';
            button.textContent = suggestion;
            button.dataset.userId = suggestion;
            button.addEventListener('click', () => {
                if (userOnboardingInput) {
                    userOnboardingInput.value = suggestion;
                    userOnboardingInput.focus();
                }
                setUserOnboardingError('');
            });
            userOnboardingSuggestionsList.appendChild(button);
        });
    }

    function resetUserOnboardingModal(suggestedId = '') {
        if (userOnboardingInput) {
            userOnboardingInput.value = normalizeUserId(suggestedId);
        }
        setUserOnboardingError('');
        setUserOnboardingLoading(false);
        renderUserOnboardingSuggestions([]);
    }

    function openUserOnboardingModal({ suggestedId = '' } = {}) {
        if (!userOnboardingModal) return;
        resetUserOnboardingModal(suggestedId || readRecentUserIds()[0]);
        userOnboardingModal.style.display = 'flex';
        if (!isUserOnboardingModalOpen) {
            lockScroll();
            isUserOnboardingModalOpen = true;
            pushModalHistory('user-onboarding');
        }
        if (userOnboardingInput) {
            userOnboardingInput.focus();
        }
    }

    function closeUserOnboardingModal(options = {}) {
        const { fromPopState = false, force = false } = options;
        const shouldKeepOpen = shouldRequestUserId && !force;
        if (shouldKeepOpen) {
            openUserOnboardingModal({ suggestedId: userOnboardingInput?.value || lastKnownUserId });
            return;
        }
        const wasTracked = modalHistoryStack.includes('user-onboarding');
        if (userOnboardingModal) {
            userOnboardingModal.style.display = 'none';
        }
        if (isUserOnboardingModalOpen) {
            unlockScroll();
            isUserOnboardingModalOpen = false;
        }
        removeModalFromHistory('user-onboarding');

        if (!fromPopState && wasTracked) {
            ignoreModalPopState = true;
            history.back();
        }
    }

    function setUserSwitchError(text) {
        if (!userSwitchError) return;
        if (text) {
            userSwitchError.textContent = text;
            userSwitchError.hidden = false;
        } else {
            userSwitchError.textContent = '';
            userSwitchError.hidden = true;
        }
    }

    function setUserSwitchLoading(isLoading) {
        if (userSwitchSubmit) {
            userSwitchSubmit.disabled = isLoading;
            userSwitchSubmit.textContent = isLoading ? 'Сохраняем...' : 'Сохранить';
        }
        if (userSwitchCancel) {
            userSwitchCancel.disabled = isLoading;
        }
        if (userSwitchInput) {
            userSwitchInput.disabled = isLoading;
        }
        if (userSwitchSuggestionsList) {
            Array.from(userSwitchSuggestionsList.querySelectorAll('button')).forEach((button) => {
                button.disabled = isLoading;
            });
        }
    }

    function renderUserIdSuggestions(prefillId = '') {
        if (!userSwitchSuggestions || !userSwitchSuggestionsList) return;
        const suggestions = [];

        const suggested = normalizeUserId(prefillId || lastKnownUserId);
        if (suggested) {
            suggestions.push(suggested);
        }

        readRecentUserIds().forEach((id) => {
            if (!suggestions.includes(id)) {
                suggestions.push(id);
            }
        });

        userSwitchSuggestionsList.innerHTML = '';

        if (suggestions.length === 0) {
            userSwitchSuggestions.hidden = true;
            return;
        }

        userSwitchSuggestions.hidden = false;
        suggestions.slice(0, 6).forEach((id) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'user-switch-chip';
            button.textContent = id;
            button.dataset.userId = id;
            button.addEventListener('click', () => {
                if (userSwitchInput) {
                    userSwitchInput.value = id;
                    userSwitchInput.focus();
                }
                setUserSwitchError('');
            });
            userSwitchSuggestionsList.appendChild(button);
        });
    }

    function resetUserSwitchModal(suggestedId = '') {
        if (userSwitchInput) {
            userSwitchInput.value = normalizeUserId(suggestedId);
        }
        setUserSwitchError('');
        setUserSwitchLoading(false);
        renderUserIdSuggestions(suggestedId);
    }

    function openUserSwitchModal({ suggestedId = '' } = {}) {
        if (!userSwitchModal) return;
        resetUserSwitchModal(suggestedId);
        userSwitchModal.style.display = 'flex';
        if (!isUserSwitchModalOpen) {
            lockScroll();
            isUserSwitchModalOpen = true;
            pushModalHistory('user-switch');
        }
        if (userSwitchInput) {
            userSwitchInput.focus();
        }
    }

    function closeUserSwitchModal(options = {}) {
        const { fromPopState = false } = options;
        const wasTracked = modalHistoryStack.includes('user-switch');
        if (userSwitchModal) {
            userSwitchModal.style.display = 'none';
        }
        if (isUserSwitchModalOpen) {
            unlockScroll();
            isUserSwitchModalOpen = false;
        }
        removeModalFromHistory('user-switch');

        if (!fromPopState && wasTracked) {
            ignoreModalPopState = true;
            history.back();
        }
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
        setBanMonthsValue(1);
    }

    function setBanModalError(text = '') {
        if (!banModalError) return;
        banModalError.textContent = text;
        banModalError.hidden = !text;
    }

    function parseBanMonths(rawValue) {
        const parsed = Number.parseInt(rawValue, 10);
        if (!Number.isFinite(parsed)) return null;
        return Math.max(1, parsed);
    }

    function setBanMonthsValue(rawValue) {
        const months = parseBanMonths(rawValue);
        if (!months) {
            setBanModalError('Укажите длительность не менее 1 месяца.');
            return null;
        }

        if (banMonthsInput) {
            banMonthsInput.value = String(months);
        }

        // Обновляем отображение общей стоимости
        if (banTargetMovie) {
            const costPerMonth = banTargetMovie?.ban_cost_per_month ?? 1;
            updateBanCostDisplay(costPerMonth, months);
        }

        setBanModalError('');
        return months;
    }

    function validateBanMonthsInput() {
        const months = parseBanMonths(banMonthsInput?.value ?? '');
        const isValid = Number.isFinite(months) && months >= 1;
        if (!isValid) {
            setBanModalError('Укажите длительность не менее 1 месяца.');
        } else {
            setBanModalError('');
        }
        return isValid ? months : null;
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

    function markMovieCardAsBanned(movie) {
        if (!movie) return;
        const card = pollGrid?.querySelector(`[data-movie-id="${movie.id}"]`);
        if (!card) return;

        card.classList.add('poll-movie-card-banned');
        card.style.pointerEvents = 'none';

        const banBtn = card.querySelector('.poll-ban-button');
        if (banBtn) {
            banBtn.classList.add('poll-ban-button-static');
            banBtn.setAttribute('aria-disabled', 'true');
            banBtn.disabled = true;
            banBtn.textContent = buildBanLabelShort(movie);
        }
    }

    async function submitBan() {
        if (!banTargetMovie || !banConfirmBtn) return;
        if (!banMonthsInput) return;

        const bannedMovie = banTargetMovie;
        const activeMovies = getActiveMovies(moviesList);
        if (activeMovies.length <= 1) {
            setBanModalError('Нельзя забанить последний фильм.');
            return;
        }

        const months = validateBanMonthsInput();
        if (!months) {
            return;
        }
        banConfirmBtn.disabled = true;
        banConfirmBtn.textContent = 'Исключаем...';

        try {
            const response = await fetch(buildPollApiUrl(`/api/polls/${pollId}/ban`), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ movie_id: banTargetMovie.id, months }),
            });

            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || 'Не удалось исключить фильм');
            }

            const banPayload = {
                ban_until: result.ban_until,
                ban_status: result.ban_status,
                ban_remaining_seconds: result.ban_remaining_seconds,
            };
            applyBanResult(bannedMovie.id, banPayload);
            const updatedBannedMovie = { ...bannedMovie, ...banPayload };
            markMovieCardAsBanned(updatedBannedMovie);

            // Обрабатываем списание баллов с анимацией
            if (result.points_balance !== undefined) {
                handlePointsAfterBan(result);
            }

            const banMessage = `«${updatedBannedMovie.name}» исключён на ${months} ${declOfNum(months, ['месяц', 'месяца', 'месяцев'])}.`;
            showToast(banMessage, 'success');

            try {
                await fetchPollData({ skipVoteHandling: true, showErrors: false });
            } catch (refreshError) {
                console.error('Не удалось обновить состояние опроса после бана', refreshError);
            }

            closeBanModal();
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
        if (pollDescription) {
            pollDescription.textContent = 'Голосование завершено из-за банов.';
        }
        showMessage('Голосование завершено из-за банов.', 'info');
        updateCustomVoteButtonState();
        renderMovies(moviesList);
    }

    function getPointsEarnedStorageKey() {
        if (!voterToken) return null;
        return `voter-${voterToken}-points-earned-total`;
    }

    function clearStoredPointsEarnedTotal() {
        const storageKey = getPointsEarnedStorageKey();
        if (!storageKey || typeof localStorage === 'undefined') return;
        try {
            localStorage.removeItem(storageKey);
        } catch (error) {
            console.warn('Не удалось очистить сохранённые баллы', error);
        }
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

    function updatePointsBalance(balance, totalEarned, animate = false) {
        if (!pointsBalanceCard || !pointsBalanceValue || !pointsBalanceStatus || !pointsStateBadge) {
            return;
        }

        if (typeof balance !== 'number' || Number.isNaN(balance)) {
            markPointsAsUnavailable();
            return;
        }

        const oldBalance = pointsBalance;
        const isDecreasing = oldBalance !== null && Number.isFinite(oldBalance) && balance < oldBalance;
        const isIncreasing = oldBalance !== null && Number.isFinite(oldBalance) && balance > oldBalance;

        pointsBalance = balance;
        initializePointsEarnedTotal(totalEarned);
        pointsBalanceCard.classList.remove('points-balance-card-error');
        hidePointsBadge();

        if (animate && pointsBalanceValue) {
            // Добавляем класс для анимации
            if (isDecreasing) {
                pointsBalanceValue.classList.remove('increasing');
                pointsBalanceValue.classList.add('decreasing');
            } else if (isIncreasing) {
                pointsBalanceValue.classList.remove('decreasing');
                pointsBalanceValue.classList.add('increasing');
            }

            // Обновляем значение
            pointsBalanceValue.textContent = balance;

            // Убираем класс анимации через некоторое время
            setTimeout(() => {
                if (pointsBalanceValue) {
                    pointsBalanceValue.classList.remove('decreasing', 'increasing');
                }
            }, 600);
        } else {
            pointsBalanceValue.textContent = balance;
        }

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

    function resetPointsDisplayToDefault() {
        if (!pointsBalanceCard || !pointsBalanceValue || !pointsBalanceStatus || !pointsStateBadge) return;
        pointsBalanceCard.classList.remove('points-balance-card-error');
        pointsBalanceValue.textContent = '—';
        pointsBalanceStatus.textContent = T.pointsStatusEmpty;
        pointsStateBadge.textContent = '—';
        pointsStateBadge.setAttribute('aria-hidden', 'true');
        pointsStateBadge.classList.add('points-state-badge-hidden');
        if (pointsProgress) {
            pointsProgress.hidden = true;
        }
    }

    function resetVoterSessionState() {
        clearStoredPointsEarnedTotal();
        pointsBalance = null;
        pointsEarnedTotal = null;
        voterToken = null;
        hasVoted = false;
        votedMovie = null;
        votedMoviePointsDelta = null;
        selectedMovie = null;
        pollClosedByBan = false;
        forcedWinner = null;
        moviesList = [];
        updateVotingDisabledState(false);
        resetPointsDisplayToDefault();
        if (pollMessage) {
            pollMessage.style.display = 'none';
            pollMessage.textContent = '';
        }
        if (votedMovieWrapper) {
            votedMovieWrapper.style.display = 'none';
        }
        highlightSelectedMovie(null);
        if (pollGrid) {
            pollGrid.innerHTML = '';
        }
        if (pollWinnerBanner) {
            pollWinnerBanner.hidden = true;
            pollWinnerBanner.textContent = '';
        }
        updateCustomVoteButtonState();
        if (pollDescription) {
            pollDescription.textContent = 'Выберите один фильм из списка ниже';
        }
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
        // Always prioritize server value over localStorage to stay in sync with DB
        const parsed = Number(initialTotal);
        const serverValue = Number.isFinite(parsed) ? Math.max(0, parsed) : 0;
        
        // Only use stored value as fallback if server value is 0 and we have a stored value
        // (in case server temporarily returns 0 due to sync issues)
        if (serverValue === 0) {
            const storedTotal = readStoredPointsEarnedTotal();
            if (Number.isFinite(storedTotal) && storedTotal > 0) {
                pointsEarnedTotal = storedTotal;
                return;
            }
        }
        
        pointsEarnedTotal = serverValue;
        persistPointsEarnedTotal(pointsEarnedTotal);
    }

    function updatePointsStatus() {
        if (!pointsBalanceStatus) return;
        const totalEarned = Number.isFinite(pointsEarnedTotal) ? pointsEarnedTotal : 0;
        pointsBalanceStatus.textContent = T.pointsStatusUpdated(totalEarned);
    }

    function updateStreakUI(streakInfo, options = {}) {
        if (!streakInfo) {
            // Скрываем streak элементы если нет данных
            if (streakIndicator) streakIndicator.hidden = true;
            if (streakWidget) streakWidget.hidden = true;
            return;
        }

        const { animate = false, streakContinued = false, streakBroken = false } = options;
        const streak = streakInfo.current_streak || 0;
        const maxStreak = streakInfo.max_streak || 0;
        const bonus = streakInfo.current_bonus || 0;
        const isActive = streakInfo.streak_active !== false;
        const nextMilestone = streakInfo.next_milestone || {};

        currentStreak = streakInfo;

        // Обновляем индикатор streak в панели баллов
        if (streakIndicator && streakCount) {
            if (streak > 0 && isActive) {
                streakIndicator.hidden = false;
                streakCount.textContent = streak;
                streakIndicator.title = `Серия: ${streak} ${declOfNum(streak, ['день', 'дня', 'дней'])} подряд`;
            } else {
                streakIndicator.hidden = true;
            }
        }

        // Обновляем виджет streak
        if (streakWidget) {
            // Показываем виджет только если есть streak >= 1 или если есть история
            if ((streak >= 1 && isActive) || maxStreak > 0) {
                streakWidget.hidden = false;

                // Обновляем количество дней
                if (streakDays) {
                    const daysText = streak === 1 ? '1 день' : `${streak} ${declOfNum(streak, ['день', 'дня', 'дней'])}`;
                    streakDays.textContent = daysText;
                }

                // Обновляем прогресс-бар (масштаб 0-7 дней)
                if (streakProgressBar) {
                    const progress = Math.min(100, (streak / 7) * 100);
                    streakProgressBar.style.width = `${progress}%`;
                }

                // Обновляем milestones (подсвечиваем достигнутые)
                const milestones = streakWidget.querySelectorAll('.streak-milestone');
                milestones.forEach((milestone) => {
                    const dayValue = Number(milestone.dataset.day);
                    milestone.classList.remove('achieved', 'current');
                    if (streak >= dayValue) {
                        milestone.classList.add('achieved');
                    }
                    if (streak === dayValue) {
                        milestone.classList.add('current');
                    }
                });

                // Обновляем информацию о бонусе
                if (streakCurrentBonus) {
                    if (bonus > 0) {
                        streakCurrentBonus.textContent = `Бонус: +${bonus}`;
                        streakCurrentBonus.classList.remove('no-bonus');
                    } else {
                        streakCurrentBonus.textContent = 'Бонус: +0';
                        streakCurrentBonus.classList.add('no-bonus');
                    }
                }

                // Обновляем информацию о следующем бонусе
                if (streakNextBonus && nextMilestone) {
                    if (nextMilestone.next_milestone && nextMilestone.days_remaining > 0) {
                        streakNextBonus.textContent = `Ещё ${nextMilestone.days_remaining} ${declOfNum(nextMilestone.days_remaining, ['день', 'дня', 'дней'])} до +${nextMilestone.next_bonus}`;
                    } else if (bonus > 0) {
                        streakNextBonus.textContent = 'Максимальный бонус достигнут! 🎉';
                    } else {
                        streakNextBonus.textContent = '';
                    }
                }

                // Анимации
                if (animate) {
                    streakWidget.classList.remove('streak-updated', 'streak-milestone-reached');
                    void streakWidget.offsetWidth; // Force reflow

                    if (streakContinued) {
                        streakWidget.classList.add('streak-updated');
                        setTimeout(() => streakWidget.classList.remove('streak-updated'), 600);

                        // Проверяем, достигнут ли milestone
                        const isMilestone = [2, 3, 5, 7].includes(streak);
                        if (isMilestone) {
                            streakWidget.classList.add('streak-milestone-reached');
                            setTimeout(() => streakWidget.classList.remove('streak-milestone-reached'), 800);
                        }
                    }
                }
            } else {
                streakWidget.hidden = true;
            }
        }
    }

    function handlePointsAfterVote(result) {
        const awarded = Number(result.points_awarded);
        const newBalance = Number(result.points_balance);
        const earnedTotal = Number(result.points_earned_total);
        const basePoints = Number(result.base_points) || awarded;
        const streakBonus = Number(result.streak_bonus) || 0;
        const streakContinued = Boolean(result.streak_continued);
        const streakBroken = Boolean(result.streak_broken);

        if (!Number.isFinite(awarded) || !Number.isFinite(newBalance)) {
            showToast(T.toastPointsError, 'error');
            markPointsAsUnavailable();
            return;
        }

        updatePointsBalance(newBalance, earnedTotal);

        // Обновляем streak UI с анимацией
        if (result.streak) {
            updateStreakUI(result.streak, { animate: true, streakContinued, streakBroken });
        }

        if (awarded > 0) {
            // Формируем сообщение с учётом streak бонуса
            let toastMessage;
            if (streakBonus > 0 && result.streak?.current_streak) {
                const streakDays = result.streak.current_streak;
                toastMessage = `+${awarded} баллов (${basePoints} + ${streakBonus} бонус за ${streakDays}-дневную серию!)`;
            } else {
                toastMessage = T.toastPointsEarned(awarded);
            }
            showToast(toastMessage, 'success', { duration: 5000 });
            playPointsProgress(awarded);

            // Дополнительное уведомление о streak
            if (streakContinued && result.streak?.current_streak > 1) {
                setTimeout(() => {
                    showToast(`🔥 Серия ${result.streak.current_streak} ${declOfNum(result.streak.current_streak, ['день', 'дня', 'дней'])} подряд!`, 'info', { duration: 3000 });
                }, 1500);
            } else if (streakBroken) {
                setTimeout(() => {
                    showToast('Серия прервана. Начните новую! 💪', 'info', { duration: 3000 });
                }, 1500);
            }
        }

        if (awarded < 0) {
            showToast(T.toastPointsDeducted(Math.abs(awarded)), 'info', { duration: 4000 });
            updateCustomVoteButtonState();
            return;
        }
    }

    function playPointsProgress(points) {
        if (!pointsProgress || !pointsProgressBar) return;
        if (progressTimeoutId) {
            clearTimeout(progressTimeoutId);
        }
        pointsProgress.hidden = false;
        pointsProgressBar.style.width = '0%';
        pointsProgressBar.classList.remove('points-progress-bar-deducted');
        pointsProgressBar.classList.add('points-progress-bar-earned');
        pointsProgressLabel.textContent = T.pointsProgressEarned(points);
        requestAnimationFrame(() => {
            pointsProgressBar.style.width = '100%';
        });
        progressTimeoutId = setTimeout(() => {
            pointsProgress.hidden = true;
            pointsProgressBar.style.width = '0%';
            pointsProgressLabel.textContent = T.pointsProgressDefault;
            pointsProgressBar.classList.remove('points-progress-bar-earned', 'points-progress-bar-deducted');
        }, 1600);
    }

    function playPointsDeduction(points) {
        if (!pointsProgress || !pointsProgressBar) return;
        if (progressTimeoutId) {
            clearTimeout(progressTimeoutId);
        }
        pointsProgress.hidden = false;
        pointsProgressBar.style.width = '100%';
        pointsProgressBar.classList.remove('points-progress-bar-earned');
        pointsProgressBar.classList.add('points-progress-bar-deducted');
        pointsProgressLabel.textContent = T.pointsProgressDeducted(points);
        requestAnimationFrame(() => {
            pointsProgressBar.style.width = '0%';
        });
        progressTimeoutId = setTimeout(() => {
            pointsProgress.hidden = true;
            pointsProgressBar.style.width = '0%';
            pointsProgressLabel.textContent = T.pointsProgressDefault;
            pointsProgressBar.classList.remove('points-progress-bar-earned', 'points-progress-bar-deducted');
        }, 1600);
    }

    function handlePointsAfterBan(result) {
        const deducted = Number(result.points_balance);
        const earnedTotal = Number(result.points_earned_total);
        const oldBalance = pointsBalance;

        if (!Number.isFinite(deducted)) {
            showToast(T.toastPointsError, 'error');
            markPointsAsUnavailable();
            return;
        }

        // Вычисляем количество списанных баллов
        const deductedAmount = oldBalance !== null && Number.isFinite(oldBalance) 
            ? Math.max(0, oldBalance - deducted)
            : 0;

        // Обновляем баланс с анимацией
        updatePointsBalance(deducted, earnedTotal, true);

        if (deductedAmount > 0) {
            showToast(T.toastPointsDeducted(deductedAmount), 'info', { duration: 4000 });
            playPointsDeduction(deductedAmount);
        }

        updateCustomVoteButtonState();
    }

    function setLogoutButtonBusy(isBusy) {
        if (!logoutButton) return;
        logoutButton.disabled = isBusy;
        logoutButton.classList.toggle('logout-button-busy', isBusy);
    }

    async function handleLogoutClick() {
        if (isLogoutInProgress) return;
        isLogoutInProgress = true;
        setLogoutButtonBusy(true);

        try {
            const requestPayload = {};
            if (lastKnownUserId) {
                requestPayload.user_id = lastKnownUserId;
            }

            const response = await fetch(buildPollApiUrl('/api/polls/auth/logout'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(requestPayload),
            });

            const payload = await response.json().catch(() => ({}));
            if (!response.ok || payload?.success === false) {
                throw new Error(payload?.error || 'Не удалось выполнить выход.');
            }

            lastKnownUserId = normalizeUserId(payload.user_id) || lastKnownUserId;
            resetVoterSessionState();
            deleteCookie(VOTER_TOKEN_COOKIE);
            deleteCookie(VOTER_USER_ID_COOKIE);
            const successMessage = payload.user_id
                ? 'Сеанс сброшен. Выберите ID заново.'
                : 'Сеанс сброшен. Можно выбрать новый ID.';
            showToast(successMessage, 'info');
            openUserSwitchModal({ suggestedId: lastKnownUserId });
        } catch (error) {
            console.error('Ошибка выхода из профиля:', error);
            showToast(error.message || 'Не удалось выполнить выход.', 'error');
        } finally {
            isLogoutInProgress = false;
            setLogoutButtonBusy(false);
        }
    }

    async function submitUserSwitch() {
        if (!userSwitchInput || isLogoutInProgress) return;
        const userId = normalizeUserId(userSwitchInput.value);
        if (!userId) {
            setUserSwitchError('Укажите ID пользователя.');
            return;
        }

        setUserSwitchError('');
        setUserSwitchLoading(true);

        try {
            const response = await fetch(buildPollApiUrl('/api/polls/auth/login'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ user_id: userId }),
            });

            const payload = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(payload?.error || 'Не удалось сменить пользователя.');
            }

            lastKnownUserId = normalizeUserId(payload.user_id) || userId;
            rememberUserId(lastKnownUserId);
            resetVoterSessionState();

            if (typeof payload.points_balance === 'number') {
                updatePointsBalance(payload.points_balance, payload.points_earned_total);
            }

            if (payload.voter_token) {
                voterToken = payload.voter_token;
            }

            closeUserSwitchModal();
            showToast('Профиль обновлён. Загружаем данные...', 'success');
            await fetchPollData({ skipVoteHandling: false, showErrors: true });
        } catch (error) {
            console.error('Ошибка смены пользователя:', error);
            setUserSwitchError(error.message || 'Не удалось сменить пользователя.');
        } finally {
            setUserSwitchLoading(false);
        }
    }

    async function submitUserOnboarding() {
        if (!userOnboardingInput || isUserOnboardingSubmitting) return;
        const userId = normalizeUserId(userOnboardingInput.value);
        if (!userId) {
            setUserOnboardingError('Укажите ID пользователя.');
            return;
        }

        setUserOnboardingError('');
        setUserOnboardingLoading(true);

        try {
            const response = await fetch(buildPollApiUrl('/api/polls/auth/register'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ user_id: userId }),
            });

            const payload = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(payload?.error || 'Не удалось сохранить ID.');
            }

            lastKnownUserId = normalizeUserId(payload.user_id) || userId;
            rememberUserId(lastKnownUserId);
            voterToken = payload.voter_token || voterToken;
            shouldRequestUserId = false;

            if (typeof payload.points_balance === 'number') {
                updatePointsBalance(payload.points_balance, payload.points_earned_total);
            }

            closeUserOnboardingModal();
            showToast('ID сохранён. Загружаем данные...', 'success');
            await fetchPollData({ skipVoteHandling: false, showErrors: true });
        } catch (error) {
            console.error('Ошибка сохранения ID:', error);
            setUserOnboardingError(error.message || 'Не удалось сохранить ID.');
        } finally {
            setUserOnboardingLoading(false);
        }
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
            const banUntilStr = banUntil.toLocaleDateString('ru-RU', { timeZone: 'Asia/Vladivostok' });
            return `Исключён до ${banUntilStr}`;
        }
        return 'Уже исключён';
    }

    function buildBanLabelShort(movie) {
        if (!movie) return 'Бан';
        const banUntil = movie.ban_until ? new Date(movie.ban_until) : null;
        if (banUntil && !Number.isNaN(banUntil.getTime())) {
            return `до ${banUntil.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', timeZone: 'Asia/Vladivostok' })}`;
        }
        return 'Бан';
    }

    // Элементы оверлея подтверждения
    const holdConfirmOverlay = document.getElementById('hold-confirm-overlay');
    const holdConfirmCost = document.getElementById('hold-confirm-cost');
    const holdConfirmProgress = holdConfirmOverlay?.querySelector('.hold-confirm-circle-progress');

    // Глобальное состояние для hold-to-confirm (нужно для отслеживания mouseup на document)
    let activeHoldState = null;

    // Функция для удержания кнопки (hold-to-confirm) с полноэкранным оверлеем
    function setupHoldToConfirm(button, onConfirm, holdDuration = 3000, cost = 0) {
        let holdTimer = null;
        let isHolding = false;

        const showOverlay = () => {
            if (!holdConfirmOverlay) return;
            
            // Показываем стоимость
            if (holdConfirmCost) {
                holdConfirmCost.textContent = cost > 0 ? `−${cost} баллов` : 'Бесплатно';
            }
            
            // Сбрасываем анимацию прогресса
            if (holdConfirmProgress) {
                holdConfirmProgress.style.transition = 'none';
                holdConfirmProgress.style.strokeDashoffset = '339.292';
                // Force reflow
                void holdConfirmProgress.offsetWidth;
            }
            
            holdConfirmOverlay.classList.add('active');
            
            // Запускаем анимацию прогресса
            requestAnimationFrame(() => {
                if (holdConfirmProgress) {
                    holdConfirmProgress.style.transition = `stroke-dashoffset ${holdDuration}ms linear`;
                    holdConfirmProgress.style.strokeDashoffset = '0';
                }
            });
        };

        const hideOverlay = (instant = false) => {
            if (!holdConfirmOverlay) return;
            
            if (instant) {
                // Мгновенное скрытие при подтверждении
                holdConfirmOverlay.classList.add('confirmed');
            }
            holdConfirmOverlay.classList.remove('active');
            
            // Сбрасываем прогресс
            if (holdConfirmProgress) {
                holdConfirmProgress.style.transition = 'none';
                holdConfirmProgress.style.strokeDashoffset = '339.292';
            }
            
            // Убираем класс confirmed после скрытия
            if (instant) {
                // Небольшая задержка для завершения скрытия, затем сброс
                requestAnimationFrame(() => {
                    holdConfirmOverlay.classList.remove('confirmed');
                });
            }
        };

        const startHold = (e) => {
            if (button.disabled) return;
            e.preventDefault();
            e.stopPropagation();
            
            if (isHolding) return;
            isHolding = true;
            button.classList.add('holding');
            showOverlay();
            
            // Сохраняем ссылку на cancelHold для глобального обработчика mouseup
            activeHoldState = { cancelHold };
            
            holdTimer = setTimeout(() => {
                if (isHolding) {
                    // Мгновенно скрываем оверлей и сразу вызываем onConfirm
                    isHolding = false;
                    button.classList.remove('holding');
                    hideOverlay(true); // instant = true
                    activeHoldState = null;
                    holdTimer = null;
                    onConfirm();
                }
            }, holdDuration);
        };

        const cancelHold = () => {
            if (holdTimer) {
                clearTimeout(holdTimer);
                holdTimer = null;
            }
            if (!isHolding) return;
            isHolding = false;
            button.classList.remove('holding');
            hideOverlay(false); // плавное скрытие при отмене
            activeHoldState = null;
        };

        // Мышь - только mousedown на кнопке, mouseup обрабатывается глобально
        button.addEventListener('mousedown', startHold);

        // Тач (мобильные) - touchend/touchcancel на кнопке + глобально
        button.addEventListener('touchstart', startHold, { passive: false });
        button.addEventListener('touchend', cancelHold);
        button.addEventListener('touchcancel', cancelHold);

        // Предотвращаем обычный клик
        button.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
        });
    }
    
    // Глобальный обработчик mouseup - отменяет hold при отпускании мыши где угодно
    document.addEventListener('mouseup', () => {
        if (activeHoldState && activeHoldState.cancelHold) {
            activeHoldState.cancelHold();
        }
    });

    // Глобальные обработчики для overlay
    if (holdConfirmOverlay) {
        // При отпускании на overlay тоже отменяем
        holdConfirmOverlay.addEventListener('mouseup', () => {
            if (activeHoldState && activeHoldState.cancelHold) {
                activeHoldState.cancelHold();
            }
        });
        holdConfirmOverlay.addEventListener('touchend', (e) => {
            e.preventDefault();
            if (activeHoldState && activeHoldState.cancelHold) {
                activeHoldState.cancelHold();
            }
        });
        holdConfirmOverlay.addEventListener('touchcancel', (e) => {
            e.preventDefault();
            if (activeHoldState && activeHoldState.cancelHold) {
                activeHoldState.cancelHold();
            }
        });
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
        if (pollDescription) {
            pollDescription.textContent = 'Вы уже проголосовали в этом опросе.';
        }
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


    userOnboardingSubmit?.addEventListener('click', submitUserOnboarding);
    userOnboardingInput?.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            submitUserOnboarding();
        }
    });

    logoutButton?.addEventListener('click', handleLogoutClick);

    userSwitchCancel?.addEventListener('click', () => closeUserSwitchModal());
    userSwitchSubmit?.addEventListener('click', submitUserSwitch);
    userSwitchInput?.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            submitUserSwitch();
        }
    });

    userSwitchModal?.addEventListener('click', (event) => {
        if (event.target === userSwitchModal) {
            closeUserSwitchModal();
        }
    });


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

    banMonthsInput?.addEventListener('input', (event) => {
        setBanMonthsValue(event.target.value);
    });

    banMonthsInput?.addEventListener('blur', validateBanMonthsInput);

    banPresetButtons.forEach((button) => {
        button.addEventListener('click', () => {
            const preset = button.dataset.banPreset;
            setBanMonthsValue(preset);
        });
    });

    banStepButtons.forEach((button) => {
        button.addEventListener('click', () => {
            const step = Number.parseInt(button.dataset.banStep, 10) || 0;
            const current = parseBanMonths(banMonthsInput?.value ?? '1') || 1;
            setBanMonthsValue(current + step);
        });
    });

    // Обновляем стоимость при изменении значения в поле ввода
    if (banMonthsInput) {
        banMonthsInput.addEventListener('input', () => {
            const months = parseBanMonths(banMonthsInput.value);
            if (months && banTargetMovie) {
                const costPerMonth = banTargetMovie?.ban_cost_per_month ?? 1;
                updateBanCostDisplay(costPerMonth, months);
            }
        });
    }

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
        // Показываем кнопку, если пользователь ещё не голосовал и опрос не закрыт
        customVoteBtn.hidden = Boolean(hasVoteFlag || pollClosedByBan);
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

