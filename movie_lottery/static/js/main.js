// static/js/main.js

import { buildPollApiUrl, loadMyPolls } from './utils/polls.js';

const escapeHtml = (unsafeValue) => {
    const value = unsafeValue == null ? '' : String(unsafeValue);
    return value
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
};

var movies = [];

document.addEventListener('DOMContentLoaded', async () => {
    const movieInput = document.getElementById('movie-input');
    const addMovieBtn = document.getElementById('add-movie-btn');
    const createLotteryBtn = document.getElementById('create-lottery-btn');
    const createPollBtn = document.getElementById('create-poll-btn');
    const movieListDiv = document.getElementById('movie-list');
    const loader = document.getElementById('loader');
    const errorMessage = document.getElementById('error-message');
    const autoDownloadCheckbox = document.getElementById('auto-download-checkbox');
    const myPollsBtn = document.getElementById('my-polls-btn');
    const myPollsBadge = document.getElementById('my-polls-badge');
    const pollModal = document.getElementById('poll-modal');

    if (localStorage.getItem('autoDownloadEnabled') === 'true') {
        autoDownloadCheckbox.checked = true;
    }
    autoDownloadCheckbox.addEventListener('change', () => {
        localStorage.setItem('autoDownloadEnabled', autoDownloadCheckbox.checked);
    });

    const refreshMyPolls = () => loadMyPolls({
        myPollsButton: myPollsBtn,
        myPollsBadgeElement: myPollsBadge,
    });
    await refreshMyPolls();

    const updateCreateButtonState = () => {
        const canCreate = movies.length >= 2 && movies.length <= 25;
        createLotteryBtn.disabled = !canCreate;
        createPollBtn.disabled = !canCreate;
    };

    const renderMovieList = () => {
        movieListDiv.innerHTML = '';
        movies.forEach((movie, index) => {
            const movieCard = document.createElement('div');
            movieCard.className = 'movie-card';
            movieCard.dataset.movieName = movie.name;
            movieCard.dataset.movieSearchName = movie.search_name || '';
            movieCard.dataset.movieYear = movie.year || '';
            movieCard.innerHTML = `
                <div class="movie-card-poster-wrapper">
                    <img src="${movie.poster || 'https://via.placeholder.com/100x150.png?text=No+Image'}" alt="Постер">
                    <div class="movie-card-actions-overlay">
                        <button class="icon-button search-rutracker-btn" data-index="${index}" title="Найти на RuTracker" aria-label="Найти на RuTracker">
                            <svg class="icon-svg icon-search" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                                <use href="#icon-search"></use>
                            </svg>
                        </button>
                        <button class="remove-btn" data-index="${index}">&times;</button>
                    </div>
                </div>
                <div class="movie-info">
                    <h4>${movie.name}</h4>
                    <p>${movie.year}</p>
                </div>
                <div class="movie-card-actions">
                    <button class="secondary-button library-add-btn" data-index="${index}">Добавить в библиотеку</button>
                </div>
            `;
            movieListDiv.appendChild(movieCard);
        });

        document.querySelectorAll('.remove-btn').forEach(button => {
            button.addEventListener('click', (e) => {
                e.stopPropagation();
                const indexToRemove = parseInt(e.target.dataset.index, 10);
                movies.splice(indexToRemove, 1);
                renderMovieList();
                updateCreateButtonState();
            });
        });

        document.querySelectorAll('.search-rutracker-btn').forEach(button => {
            button.addEventListener('click', (e) => {
                e.stopPropagation();
                const index = parseInt(e.target.closest('.search-rutracker-btn').dataset.index, 10);
                const movie = movies[index];
                if (movie) {
                    const searchQuery = `${movie.search_name || movie.name}${movie.year ? ' ' + movie.year : ''}`;
                    const encodedQuery = encodeURIComponent(searchQuery);
                    const rutrackerUrl = `https://rutracker.org/forum/tracker.php?nm=${encodedQuery}`;
                    window.open(rutrackerUrl, '_blank');
                    showToast(`Открыт поиск на RuTracker: "${searchQuery}"`, 'info');
                }
            });
        });

        document.querySelectorAll('.library-add-btn').forEach(button => {
            button.addEventListener('click', async (e) => {
                const indexToAdd = parseInt(e.target.dataset.index, 10);
                const movieToAdd = movies[indexToAdd];
                if (!movieToAdd) return;

                const originalText = e.target.textContent;
                e.target.disabled = true;
                e.target.textContent = 'Добавление...';

                try {
                    // ИСПРАВЛЕНИЕ: Добавлен префикс /api/
                    const response = await fetch('/api/library', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ movie: movieToAdd })
                    });
                    const data = await response.json();
                    if (!response.ok || !data.success) {
                        throw new Error(data.message || 'Не удалось добавить фильм.');
                    }
                    showToast(data.message || 'Фильм добавлен в библиотеку.', 'success');
                    e.target.textContent = 'Добавлено!';
                } catch (error) {
                    showToast(error.message, 'error');
                    e.target.textContent = originalText;
                    e.target.disabled = false;
                    return;
                }

                setTimeout(() => {
                    e.target.textContent = originalText;
                    e.target.disabled = false;
                }, 2000);
            });
        });
    };

    const addMovie = async () => {
        const query = movieInput.value.trim();
        if (!query) return;

        loader.style.display = 'block';
        errorMessage.textContent = '';
        addMovieBtn.disabled = true;

        try {
            // ИСПРАВЛЕНИЕ: Добавлен префикс /api/
            const response = await fetch('/api/fetch-movie', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: query })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Не удалось найти фильм');
            }

            const movieData = await response.json();
            movies.push(movieData);
            renderMovieList();
            updateCreateButtonState();
            movieInput.value = '';

        } catch (error) {
            errorMessage.textContent = error.message;
        } finally {
            loader.style.display = 'none';
            addMovieBtn.disabled = false;
        }
    };
    
    addMovieBtn.addEventListener('click', addMovie);
    movieInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            addMovie();
        }
    });

    createLotteryBtn.addEventListener('click', async () => {
        createLotteryBtn.disabled = true;
        createLotteryBtn.textContent = 'Перенаправление...';
        try {
            // ИСПРАВЛЕНИЕ: Добавлен префикс /api/
            const response = await fetch('/api/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ movies: movies })
            });
            if (!response.ok) throw new Error('Не удалось создать лотерею на сервере');
            
            const data = await response.json();

            if (data.wait_url) {
                window.location.href = data.wait_url;
            }

        } catch (error) {
            errorMessage.textContent = error.message;
            createLotteryBtn.disabled = false;
            createLotteryBtn.textContent = 'Создать лотерею';
        }
    });

    // --- Функционал опросов ---

    createPollBtn.addEventListener('click', async () => {
        if (movies.length < 2 || movies.length > 25) return;

        createPollBtn.disabled = true;
        createPollBtn.textContent = 'Создание...';

        try {
            const response = await fetch(buildPollApiUrl('/api/polls/create'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ movies: movies })
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

            // Очищаем список фильмов
            movies = [];
            renderMovieList();
            updateCreateButtonState();

            // Обновляем кнопку "Мои опросы"
            await refreshMyPolls();

        } catch (error) {
            errorMessage.textContent = error.message;
            createPollBtn.disabled = false;
            createPollBtn.textContent = 'Создать опрос';
        }
    });

    function showPollCreatedModal({ pollUrl, resultsUrl }) {
        const modalContent = pollModal.querySelector('.modal-content > div');
        modalContent.innerHTML = `
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
        pollModal.style.display = 'flex';

        modalContent.querySelectorAll('.copy-btn').forEach((button) => {
            button.addEventListener('click', () => {
                const targetId = button.getAttribute('data-copy-target');
                const input = modalContent.querySelector(`#${targetId}`);
                if (!input) return;

                input.select();
                input.setSelectionRange(0, input.value.length);

                const copied = document.execCommand('copy');
                if (copied) {
                    showToast('Ссылка скопирована!', 'success');
                } else if (navigator.clipboard && input.value) {
                    navigator.clipboard.writeText(input.value).then(() => {
                        showToast('Ссылка скопирована!', 'success');
                    }).catch(() => {
                        showToast('Не удалось скопировать ссылку', 'error');
                    });
                }
            });
        });
    }

    // Закрытие модального окна
    const closeBtn = pollModal.querySelector('.close-button');
    closeBtn.addEventListener('click', () => {
        pollModal.style.display = 'none';
    });

    pollModal.addEventListener('click', (e) => {
        if (e.target === pollModal) {
            pollModal.style.display = 'none';
        }
    });

    myPollsBtn.addEventListener('click', () => {
        window.location.href = '/library';
    });

    // Периодически проверяем новые результаты
    setInterval(refreshMyPolls, 10000); // Каждые 10 секунд
});
