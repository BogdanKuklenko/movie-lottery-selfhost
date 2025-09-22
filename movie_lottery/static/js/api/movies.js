// F:\GPT\movie-lottery V2\movie_lottery\static\js\api\movies.js

/**
 * Запрашивает у сервера информацию о фильме по названию или ссылке.
 * @param {string} query - Поисковый запрос.
 * @returns {Promise<object>} - Данные о фильме.
 */
export async function fetchMovieInfo(query) {
    const response = await fetch('/api/fetch-movie', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
    });
    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Не удалось найти фильм');
    }
    return await response.json();
}

/**
 * Отправляет на сервер список фильмов для создания новой лотереи.
 * @param {Array<object>} movies - Массив объектов фильмов.
 * @returns {Promise<object>} - Ответ сервера, содержащий URL страницы ожидания.
 */
export async function createLottery(movies) {
    const response = await fetch('/api/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ movies })
    });
    if (!response.ok) throw new Error('Не удалось создать лотерею на сервере');
    return await response.json();
}

/**
 * Запускает розыгрыш лотереи на сервере.
 * @param {string} lotteryId - ID лотереи.
 * @returns {Promise<object>} - Данные о фильме-победителе.
 */
export async function drawWinner(lotteryId) {
    const response = await fetch(`/api/draw/${lotteryId}`, { method: 'POST' });
    if (!response.ok) throw new Error('Не удалось провести розыгрыш');
    return await response.json();
}

/**
 * Получает с сервера полную информацию о лотерее (участники, победитель).
 * @param {string} lotteryId - ID лотереи.
 * @returns {Promise<object>} - Полные данные о лотерее.
 */
export async function fetchLotteryDetails(lotteryId) {
    const response = await fetch(`/api/result/${lotteryId}`);
    if (!response.ok) throw new Error('Ошибка сети при загрузке деталей лотереи.');
    const data = await response.json();
    if(data.error) throw new Error(data.error);
    return data;
}

/**
 * Отправляет запрос на удаление лотереи из истории.
 * @param {string} lotteryId - ID лотереи.
 * @returns {Promise<object>} - Результат операции.
 */
export async function deleteLottery(lotteryId) {
    const response = await fetch(`/api/delete-lottery/${lotteryId}`, { method: 'POST' });
    if (!response.ok) throw new Error('Ошибка сети при удалении лотереи.');
    return await response.json();
}

/**
 * Добавляет или обновляет фильм в библиотеке.
 * @param {object} movieData - Данные фильма.
 * @returns {Promise<object>} - Результат операции.
 */
export async function addOrUpdateLibraryMovie(movieData) {
    const response = await fetch('/api/library', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ movie: movieData }),
    });
    if (!response.ok) throw new Error('Ошибка сети при работе с библиотекой.');
    return await response.json();
}

/**
 * Удаляет фильм из библиотеки.
 * @param {string|number} movieId - ID фильма в библиотеке.
 * @returns {Promise<object>} - Результат операции.
 */
export async function deleteLibraryMovie(movieId) {
    const response = await fetch(`/api/library/${movieId}`, { method: 'DELETE' });
    if (!response.ok) throw new Error('Ошибка сети при удалении из библиотеки.');
    return await response.json();
}

/**
 * Сохраняет или удаляет magnet-ссылку для фильма.
 * @param {string|number} kinopoiskId - ID фильма на Кинопоиске.
 * @param {string} magnetLink - Magnet-ссылка. Пустая строка для удаления.
 * @returns {Promise<object>} - Результат операции.
 */
export async function saveMagnetLink(kinopoiskId, magnetLink) {
    const response = await fetch('/api/movie-magnet', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kinopoisk_id: kinopoiskId, magnet_link: magnetLink }),
    });
    if (!response.ok) throw new Error('Ошибка сети при сохранении magnet-ссылки.');
    return await response.json();
}