// movie_lottery/static/js/pages/poll.js

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

    let selectedMovie = null;

    // Загружаем данные опроса
    try {
        const response = await fetch(`/api/polls/${pollId}`);
        
        if (!response.ok) {
            const error = await response.json();
            showMessage(error.error || 'Опрос не найден', 'error');
            return;
        }

        const pollData = await response.json();

        // Если пользователь уже голосовал
        if (pollData.has_voted) {
            showMessage('Вы уже проголосовали в этом опросе. Спасибо за участие!', 'info');
            pollDescription.textContent = `Всего проголосовало: ${pollData.total_votes}`;
            return;
        }

        // Отображаем фильмы
        renderMovies(pollData.movies);
        pollDescription.textContent = `Выберите один фильм из ${pollData.movies.length}. Проголосовало: ${pollData.total_votes}`;

    } catch (error) {
        console.error('Ошибка загрузки опроса:', error);
        showMessage('Не удалось загрузить опрос', 'error');
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
            const response = await fetch(`/api/polls/${pollId}/vote`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ movie_id: selectedMovie.id })
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || 'Не удалось проголосовать');
            }

            // Закрываем модальное окно
            closeVoteConfirmation();

            // Показываем сообщение об успехе
            showMessage(result.message, 'success');
            
            // Скрываем сетку фильмов
            pollGrid.style.display = 'none';
            pollDescription.textContent = 'Спасибо за участие!';

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

    // Закрытие модального окна по клику вне его
    voteConfirmModal.addEventListener('click', (e) => {
        if (e.target === voteConfirmModal) {
            closeVoteConfirmation();
        }
    });
});

