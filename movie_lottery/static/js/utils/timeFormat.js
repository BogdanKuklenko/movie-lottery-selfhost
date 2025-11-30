// Утилита для форматирования времени в часовом поясе Владивостока (UTC+10)

/**
 * Конвертирует ISO строку времени в объект Date с учетом часового пояса Владивостока (UTC+10)
 * @param {string} isoString - ISO строка времени (например, "2024-01-01T12:00:00" или "2024-01-01T12:00:00Z")
 * @returns {Date|null} - Объект Date или null если строка некорректна
 */
function parseVladivostokTime(isoString) {
    if (!isoString) return null;
    
    let date;
    
    // Если строка заканчивается на Z, это UTC время
    if (isoString.endsWith('Z')) {
        // Парсим как UTC время и конвертируем в Владивосток (UTC+10)
        date = new Date(isoString);
        if (Number.isNaN(date.getTime())) {
            return null;
        }
        // Добавляем 10 часов к UTC времени
        date = new Date(date.getTime() + (10 * 60 * 60 * 1000));
    } else {
        // Если нет Z и нет timezone offset, предполагаем что это время Владивостока (naive datetime)
        // JavaScript интерпретирует строку без timezone как локальное время браузера
        // Нам нужно скорректировать это, чтобы получить правильное время Владивостока
        
        // Парсим как локальное время браузера
        const tempDate = new Date(isoString);
        if (Number.isNaN(tempDate.getTime())) {
            return null;
        }
        
        // Получаем локальный offset браузера в миллисекундах
        const localOffsetMs = tempDate.getTimezoneOffset() * 60 * 1000;
        // Offset Владивостока: UTC+10 = -600 минут = -36000000 мс
        const vladivostokOffsetMs = -10 * 60 * 60 * 1000;
        
        // Корректируем: если браузер интерпретировал время как локальное,
        // нам нужно вычесть локальный offset и добавить offset Владивостока
        // Формула: UTC_time = local_time - local_offset, затем vladivostok_time = UTC_time + vladivostok_offset
        date = new Date(tempDate.getTime() - localOffsetMs + vladivostokOffsetMs);
    }
    
    return date;
}

/**
 * Форматирует дату в формате Владивостока
 * @param {string} isoString - ISO строка времени
 * @returns {string} - Отформатированная дата или пустая строка
 */
function formatDate(isoString) {
    if (!isoString) return '';
    const date = parseVladivostokTime(isoString);
    if (!date) return '';
    
    return date.toLocaleDateString('ru-RU', {
        timeZone: 'Asia/Vladivostok',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
    });
}

/**
 * Форматирует дату и время в формате Владивостока
 * @param {string} isoString - ISO строка времени
 * @param {boolean} withTime - Включать ли время (по умолчанию true)
 * @returns {string} - Отформатированная дата/время или пустая строка/—
 */
function formatDateTime(isoString, withTime = true) {
    if (!isoString) return withTime ? '' : '';
    const date = parseVladivostokTime(isoString);
    if (!date) return withTime ? '' : '';
    
    const options = {
        timeZone: 'Asia/Vladivostok',
        year: 'numeric',
        month: 'short',
        day: '2-digit'
    };
    
    if (withTime) {
        options.hour = '2-digit';
        options.minute = '2-digit';
    }
    
    return new Intl.DateTimeFormat('ru-RU', options).format(date);
}

/**
 * Форматирует дату и время в коротком формате Владивостока (для toLocaleString)
 * @param {string} isoString - ISO строка времени
 * @returns {string} - Отформатированная дата/время или пустая строка
 */
function formatDateTimeShort(isoString) {
    if (!isoString) return '';
    const date = parseVladivostokTime(isoString);
    if (!date) return '';
    
    return date.toLocaleString('ru-RU', {
        timeZone: 'Asia/Vladivostok'
    });
}

export { formatDate, formatDateTime, formatDateTimeShort, parseVladivostokTime };

