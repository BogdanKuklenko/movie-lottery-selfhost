// F:\GPT\movie-lottery V2\movie_lottery\static\js\pages\library.js

import { ModalManager } from '../components/modal.js';
import { StatusWidgetManager } from '../components/statusWidget.js';
import * as movieApi from '../api/movies.js';
import * as torrentApi from '../api/torrents.js';

function formatDate(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    return date.toLocaleDateString('ru-RU');
}

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

document.addEventListener('DOMContentLoaded', () => {
    const gallery = document.querySelector('.library-gallery');
    const modalElement = document.getElementById('library-modal');
    const widgetElement = document.getElementById('torrent-status-widget');

    if (!gallery || !modalElement || !widgetElement) return;

    const modal = new ModalManager(modalElement);
    const widget = new StatusWidgetManager(widgetElement, 'libraryActiveDownloads');

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

    // Проверяем и загружаем "Мои опросы"
    loadMyPolls();

    function toggleSelectionMode() {
        selectionMode = !selectionMode;
        selectedMovies.clear();
        updateSelectionUI();

        const checkboxes = document.querySelectorAll('.movie-checkbox');
        checkboxes.forEach(cb => {
            cb.style.display = selectionMode ? 'block' : 'none';
            cb.checked = false;
        });

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
                    countries: card.dataset.movieCountries || null
                });
            }
        });

        try {
            const response = await fetch('/api/polls/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ movies: moviesData })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Не удалось создать опрос');
            }

            // Сохраняем токен создателя в localStorage
            const creatorTokens = JSON.parse(localStorage.getItem('pollCreatorTokens') || '{}');
            creatorTokens[data.poll_id] = data.creator_token;
            localStorage.setItem('pollCreatorTokens', JSON.stringify(creatorTokens));

            // Показываем модальное окно с результатом
            showPollCreatedModal(data.poll_url, data.poll_id);

            // Сбрасываем выбор
            toggleSelectionMode();

            // Обновляем кнопку "Мои опросы"
            loadMyPolls();

        } catch (error) {
            showToast(error.message, 'error');
            createPollBtn.disabled = false;
            createPollBtn.textContent = 'Создать опрос';
        }
    });

    function showPollCreatedModal(pollUrl, pollId) {
        const modalContent = `
            <h2>Опрос создан!</h2>
            <p>Поделитесь этой ссылкой с друзьями:</p>
            <div class="link-box">
                <input type="text" id="poll-share-link" value="${pollUrl}" readonly>
                <button class="copy-btn" onclick="copyPollLink()">Копировать</button>
            </div>
            <a href="https://t.me/share/url?url=${encodeURIComponent(pollUrl)}&text=${encodeURIComponent('Приглашаю принять участие в опросе')}" 
               class="action-button-tg" target="_blank">
                Поделиться в Telegram
            </a>
            <p class="poll-info">Результаты появятся в "Мои опросы" после первого голоса</p>
        `;
        modal.open();
        modal.renderCustomContent(modalContent);

        // Добавляем функцию копирования
        window.copyPollLink = () => {
            const input = document.getElementById('poll-share-link');
            input.select();
            document.execCommand('copy');
            showToast('Ссылка скопирована!', 'success');
        };
    }

    async function loadMyPolls() {
        const creatorTokens = JSON.parse(localStorage.getItem('pollCreatorTokens') || '{}');
        const tokens = Object.values(creatorTokens);
        
        if (tokens.length === 0) {
            myPollsBtn.style.display = 'none';
            return;
        }

        try {
            // Проверяем каждый токен и собираем все опросы
            let allPolls = [];
            for (const token of tokens) {
                const response = await fetch(`/api/polls/my-polls?creator_token=${token}`);
                if (response.ok) {
                    const data = await response.json();
                    allPolls = allPolls.concat(data.polls);
                }
            }

            if (allPolls.length > 0) {
                myPollsBtn.style.display = 'inline-block';
                
                // Подсчитываем новые результаты (опросы с голосами)
                const viewedPolls = JSON.parse(localStorage.getItem('viewedPolls') || '{}');
                const newResults = allPolls.filter(poll => !viewedPolls[poll.poll_id]);
                
                if (newResults.length > 0) {
                    myPollsBadge.textContent = newResults.length;
                    myPollsBadge.style.display = 'inline-block';
                } else {
                    myPollsBadge.style.display = 'none';
                }
            } else {
                myPollsBtn.style.display = 'none';
            }
        } catch (error) {
            console.error('Ошибка загрузки опросов:', error);
        }
    }

    myPollsBtn.addEventListener('click', () => {
        showMyPollsModal();
    });

    async function showMyPollsModal() {
        const creatorTokens = JSON.parse(localStorage.getItem('pollCreatorTokens') || '{}');
        const tokens = Object.values(creatorTokens);
        
        let allPolls = [];
        for (const token of tokens) {
            try {
                const response = await fetch(`/api/polls/my-polls?creator_token=${token}`);
                if (response.ok) {
                    const data = await response.json();
                    allPolls = allPolls.concat(data.polls);
                }
            } catch (error) {
                console.error('Ошибка загрузки опросов:', error);
            }
        }

        if (allPolls.length === 0) {
            modal.open();
            modal.renderCustomContent('<h2>Мои опросы</h2><p>У вас пока нет активных опросов с голосами.</p>');
            return;
        }

        // Сортируем по дате создания (новые первые)
        allPolls.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

        let pollsHtml = '<h2>Мои опросы</h2><div class="my-polls-list">';
        
        allPolls.forEach(poll => {
            const createdDate = new Date(poll.created_at).toLocaleString('ru-RU');
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

            pollsHtml += `
                <div class="poll-result-item">
                    <div class="poll-result-header">
                        <h3>Опрос от ${createdDate}</h3>
                        <p>Всего голосов: ${poll.total_votes} | Фильмов: ${poll.movies_count}</p>
                    </div>
                    <div class="poll-winners">
                        ${poll.winners.length > 1 ? '<p><strong>Победители (равное количество голосов):</strong></p>' : '<p><strong>Победитель:</strong></p>'}
                        ${winnersHtml}
                    </div>
                    ${poll.winners.length > 1 ? `
                        <button class="secondary-button create-poll-from-winners" data-winners='${JSON.stringify(poll.winners)}'>
                            Создать опрос из победителей
                        </button>
                    ` : ''}
                    <div class="poll-actions">
                        <button class="secondary-button search-winner-btn" data-movie-name="${poll.winners[0].name}" data-movie-year="${poll.winners[0].year || ''}">
                            Найти на RuTracker
                        </button>
                        <a href="${poll.poll_url}" class="secondary-button" target="_blank">Открыть опрос</a>
                    </div>
                </div>
            `;
        });

        pollsHtml += '</div>';

        modal.open();
        modal.renderCustomContent(pollsHtml);

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
                const searchQuery = `${movieName}${movieYear ? ' ' + movieYear : ''}`;
                const encodedQuery = encodeURIComponent(searchQuery);
                const rutrackerUrl = `https://rutracker.org/forum/tracker.php?nm=${encodedQuery}`;
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

                try {
                    const response = await fetch('/api/polls/create', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ movies: winners })
                    });

                    const data = await response.json();

                    if (!response.ok) {
                        throw new Error(data.error || 'Не удалось создать опрос');
                    }

                    // Сохраняем токен создателя
                    const creatorTokens = JSON.parse(localStorage.getItem('pollCreatorTokens') || '{}');
                    creatorTokens[data.poll_id] = data.creator_token;
                    localStorage.setItem('pollCreatorTokens', JSON.stringify(creatorTokens));

                    showPollCreatedModal(data.poll_url, data.poll_id);
                    loadMyPolls();

                } catch (error) {
                    showToast(error.message, 'error');
                    btn.disabled = false;
                    btn.textContent = 'Создать опрос из победителей';
                }
            });
        });
    }

    // Периодически проверяем новые результаты опросов
    setInterval(loadMyPolls, 10000); // Каждые 10 секунд

    // --- Конец функционала опросов ---

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
        };
    };

    const handleOpenModal = (card) => {
        const movieData = getMovieDataFromCard(card);
        modalElement.dataset.activeCardId = card.dataset.movieId || '';
        modal.open();
        modal.renderLibraryModal(movieData, {
            onSaveMagnet: async (kinopoiskId, magnetLink) => {
                const result = await movieApi.saveMagnetLink(kinopoiskId, magnetLink);
                showToast(result.message, 'success');
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
                    showToast(data.message, data.success ? 'success' : 'error');
                });
            },
            onDownload: () => torrentApi.startLibraryDownload(movieData.id).then(data => showToast(data.message, data.success ? 'success' : 'error')),
            onDeleteTorrent: async (torrentHash) => {
                await torrentApi.deleteTorrentFromClient(torrentHash);
                card.classList.remove('has-torrent-on-client');
                handleOpenModal(card);
            }
        });
    };

    // АВТОПОИСК МАГНЕТ-ССЫЛОК ОТКЛЮЧЕН
    // Пользователь вручную вводит магнет-ссылки через модальное окно
    // Кнопка RuTracker для поиска на сайте сохранена

    gallery.addEventListener('click', (event) => {
        const card = event.target.closest('.gallery-item');
        if (!card) return;

        const { movieId, kinopoiskId, movieName, movieYear, movieSearchName, hasMagnet, magnetLink } = card.dataset;
        const button = event.target.closest('.icon-button');

        if (button) {
            event.stopPropagation();
            if (button.classList.contains('delete-button')) {
                movieApi.deleteLibraryMovie(movieId).then(data => {
                    if (data.success) card.remove();
                    showToast(data.message, data.success ? 'success' : 'error');
                });
            } else if (button.classList.contains('search-rutracker-button')) {
                // Открываем поиск на RuTracker
                const searchQuery = `${movieSearchName || movieName}${movieYear ? ' ' + movieYear : ''}`;
                const encodedQuery = encodeURIComponent(searchQuery);
                const rutrackerUrl = `https://rutracker.org/forum/tracker.php?nm=${encodedQuery}`;
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

    if (window.torrentUpdater) {
        window.torrentUpdater.updateUi();
    }
});