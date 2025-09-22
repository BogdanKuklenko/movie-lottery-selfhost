// F:\GPT\movie-lottery V2\movie_lottery\static\js\api\torrents.js

/**
 * Отправляет запрос на запуск скачивания торрента по Kinopoisk ID.
 * @param {string|number} kinopoiskId - ID фильма на Кинопоиске.
 * @returns {Promise<object>} - Результат запроса от сервера.
 */
export async function startDownloadByKpId(kinopoiskId) {
    const response = await fetch(`/api/start-download/${kinopoiskId}`, { method: 'POST' });
    if (!response.ok) {
        throw new Error('Ошибка сети при попытке начать скачивание.');
    }
    return await response.json();
}

/**
 * Отправляет запрос на запуск скачивания торрента из библиотеки по ID фильма в библиотеке.
 * @param {string|number} libraryMovieId - ID фильма в таблице LibraryMovie.
 * @returns {Promise<object>} - Результат запроса от сервера.
 */
export async function startLibraryDownload(libraryMovieId) {
    const response = await fetch(`/api/library/start-download/${libraryMovieId}`, { method: 'POST' });
    if (!response.ok) {
        throw new Error('Ошибка сети при попытке начать скачивание из библиотеки.');
    }
    return await response.json();
}

/**
 * Отправляет запрос на удаление торрента и файлов с клиента по хешу.
 * @param {string} torrentHash - Хеш торрента.
 * @returns {Promise<object>} - Результат запроса от сервера.
 */
export async function deleteTorrentFromClient(torrentHash) {
    const response = await fetch(`/api/delete-torrent/${torrentHash}`, { method: 'POST' });
    if (!response.ok) {
        throw new Error('Ошибка сети при удалении торрента.');
    }
    return await response.json();
}

async function fetchTorrentStatus(url, defaultErrorMessage) {
    try {
        const response = await fetch(url);
        let data = null;
        try {
            data = await response.json();
        } catch (parseError) {
            data = null;
        }

        if (!response.ok) {
            if (data && typeof data === 'object') {
                return data;
            }
            return { status: 'error', message: defaultErrorMessage };
        }

        if (data && typeof data === 'object') {
            return data;
        }
        return { status: 'error', message: defaultErrorMessage };
    } catch (error) {
        return { status: 'error', message: error.message || defaultErrorMessage };
    }
}

/**
 * Запрашивает статус торрента для лотереи.
 * @param {string} lotteryId - ID лотереи.
 * @returns {Promise<object>} - Данные о статусе.
 */
export async function getTorrentStatusForLottery(lotteryId) {
    const encodedId = encodeURIComponent(lotteryId);
    return fetchTorrentStatus(`/api/torrent-status/${encodedId}`, 'Не удалось получить статус торрента лотереи.');
}

/**
 * Запрашивает статус торрента для фильма из библиотеки.
 * @param {string|number} libraryMovieId - ID фильма в библиотеке.
 * @returns {Promise<object>} - Данные о статусе.
 */
export async function getTorrentStatusForLibrary(libraryMovieId) {
    const encodedId = encodeURIComponent(libraryMovieId);
    return fetchTorrentStatus(`/api/library/torrent-status/${encodedId}`, 'Не удалось получить статус торрента библиотеки.');
}

/**
 * Запрашивает статус торрента по Kinopoisk ID.
 * @param {string|number} kinopoiskId - ID фильма на Кинопоиске.
 * @returns {Promise<object>} - Данные о статусе.
 */
export async function getDownloadStatusByKpId(kinopoiskId) {
    const encodedId = encodeURIComponent(kinopoiskId);
    return fetchTorrentStatus(`/api/download-status/${encodedId}`, 'Не удалось получить статус загрузки.');
}

/**
 * Запрашивает список всех активных загрузок.
 * @returns {Promise<object>} - Список загрузок.
 */
export async function fetchActiveDownloads() {
    const response = await fetch('/api/active-downloads');
    if (!response.ok) throw new Error('Не удалось получить список активных загрузок.');
    return await response.json();
}
