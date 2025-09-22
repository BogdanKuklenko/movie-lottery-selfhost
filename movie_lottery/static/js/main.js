// static/js/main.js

var movies = [];

document.addEventListener('DOMContentLoaded', () => {
    const movieInput = document.getElementById('movie-input');
    const addMovieBtn = document.getElementById('add-movie-btn');
    const createLotteryBtn = document.getElementById('create-lottery-btn');
    const movieListDiv = document.getElementById('movie-list');
    const loader = document.getElementById('loader');
    const errorMessage = document.getElementById('error-message');
    // --- НОВОЕ: Получаем доступ к галочке ---
    const autoDownloadCheckbox = document.getElementById('auto-download-checkbox');

    // --- НОВОЕ: Логика для запоминания состояния галочки ---
    // При загрузке страницы, проверяем, что сохранено в памяти браузера
    if (localStorage.getItem('autoDownloadEnabled') === 'true') {
        autoDownloadCheckbox.checked = true;
    }
    // При каждом клике на галочку, сохраняем ее новое состояние
    autoDownloadCheckbox.addEventListener('change', () => {
        localStorage.setItem('autoDownloadEnabled', autoDownloadCheckbox.checked);
    });

    const updateCreateButtonState = () => {
        createLotteryBtn.disabled = movies.length < 2;
    };

    const renderMovieList = () => {
        movieListDiv.innerHTML = '';
        movies.forEach((movie, index) => {
            const movieCard = document.createElement('div');
            movieCard.className = 'movie-card';
            movieCard.innerHTML = `
                <img src="${movie.poster || 'https://via.placeholder.com/100x150.png?text=No+Image'}" alt="Постер">
                <div class="movie-info">
                    <h4>${movie.name}</h4>
                    <p>${movie.year}</p>
                </div>
                <div class="movie-card-actions">
                    <button class="secondary-button library-add-btn" data-index="${index}">Добавить в библиотеку</button>
                </div>
                <button class="remove-btn" data-index="${index}">&times;</button>
            `;
            movieListDiv.appendChild(movieCard);
        });

        document.querySelectorAll('.remove-btn').forEach(button => {
            button.addEventListener('click', (e) => {
                const indexToRemove = parseInt(e.target.dataset.index, 10);
                movies.splice(indexToRemove, 1);
                renderMovieList();
                updateCreateButtonState();
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
            const response = await fetch('/fetch-movie', {
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
            const response = await fetch('/create', {
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
            createLotteryBtn.textContent = 'Создать лотерею и перейти к ожиданию';
        }
    });
});