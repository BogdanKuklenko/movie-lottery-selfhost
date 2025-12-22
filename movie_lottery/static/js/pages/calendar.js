// Календарь запланированных фильмов и релизов

const MONTH_NAMES = [
    'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
    'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
];

const MONTH_NAMES_GENITIVE = [
    'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
    'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'
];

let currentYear = new Date().getFullYear();
let currentMonth = new Date().getMonth(); // 0-11
let schedulesCache = [];
let releasesCache = {}; // { "YYYY-MM-country": { "YYYY-MM-DD": [...] } }
let viewMode = localStorage.getItem('calendar-view-mode') || 'schedules'; // 'schedules' или 'releases'

// Фильтры типов релизов (загружаем из localStorage или используем значения по умолчанию)
let releaseFilters = JSON.parse(localStorage.getItem('calendar-release-filters')) || {
    russia: true,
    world: false,
    digital: false
};

let activeGenreFilter = ''; // Фильтр по жанру
let allGenres = new Set(); // Все жанры из текущих релизов

// Тултип элемент
let tooltipElement = null;
let tooltipTimeout = null;

/**
 * Загружает расписания для указанного месяца
 */
async function loadSchedules(year, month) {
    try {
        const response = await fetch(`/api/schedules?year=${year}&month=${month + 1}`);
        const data = await response.json();
        
        if (data.success) {
            schedulesCache = data.schedules || [];
            return schedulesCache;
        }
        return [];
    } catch (error) {
        console.error('Ошибка загрузки расписаний:', error);
        return [];
    }
}

/**
 * Загружает релизы для указанного месяца
 */
async function loadReleases(year, month, country = 'russia') {
    const cacheKey = `${year}-${month + 1}-${country}`;
    
    // Проверяем кэш в памяти
    if (releasesCache[cacheKey]) {
        return releasesCache[cacheKey];
    }
    
    showLoading(true);
    
    try {
        const response = await fetch(`/api/releases?year=${year}&month=${month + 1}&country=${country}`);
        const data = await response.json();
        
        if (data.success) {
            releasesCache[cacheKey] = data.releases || {};
            return releasesCache[cacheKey];
        }
        
        if (data.error) {
            console.error('Ошибка API релизов:', data.error);
            showToast(data.error, 'error');
        }
        return {};
    } catch (error) {
        console.error('Ошибка загрузки релизов:', error);
        showToast('Ошибка загрузки релизов', 'error');
        return {};
    } finally {
        showLoading(false);
    }
}

/**
 * Загружает и объединяет релизы для всех активных типов
 */
async function loadAllFilteredReleases(year, month) {
    const activeTypes = Object.entries(releaseFilters)
        .filter(([_, enabled]) => enabled)
        .map(([type, _]) => type);
    
    if (activeTypes.length === 0) {
        return {};
    }
    
    showLoading(true);
    
    try {
        // Загружаем релизы для всех активных типов параллельно
        const promises = activeTypes.map(type => loadReleases(year, month, type));
        const results = await Promise.all(promises);
        
        // Объединяем результаты по датам, избегая дублирования по kinopoisk_id
        const mergedReleases = {};
        const seenIds = new Set();
        
        results.forEach(releasesData => {
            Object.entries(releasesData).forEach(([date, movies]) => {
                if (!mergedReleases[date]) {
                    mergedReleases[date] = [];
                }
                
                movies.forEach(movie => {
                    const kpId = movie.kinopoisk_id;
                    if (kpId && !seenIds.has(kpId)) {
                        seenIds.add(kpId);
                        mergedReleases[date].push(movie);
                    } else if (!kpId) {
                        // Если нет ID, добавляем всё равно
                        mergedReleases[date].push(movie);
                    }
                });
            });
        });
        
        return mergedReleases;
    } finally {
        showLoading(false);
    }
}

/**
 * Показывает/скрывает индикатор загрузки
 */
function showLoading(show) {
    const loadingEl = document.getElementById('calendar-loading');
    if (loadingEl) {
        loadingEl.style.display = show ? 'flex' : 'none';
    }
}

/**
 * Возвращает количество дней в месяце
 */
function getDaysInMonth(year, month) {
    return new Date(year, month + 1, 0).getDate();
}

/**
 * Возвращает день недели для первого числа месяца (0=Пн, 6=Вс)
 */
function getFirstDayOfMonth(year, month) {
    const day = new Date(year, month, 1).getDay();
    // Преобразуем: 0=Вс -> 6, 1=Пн -> 0, и т.д.
    return day === 0 ? 6 : day - 1;
}

/**
 * Получает расписания для указанной даты
 */
function getSchedulesForDate(year, month, day) {
    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    
    return schedulesCache.filter(schedule => {
        if (!schedule.scheduled_date) return false;
        return schedule.scheduled_date.startsWith(dateStr);
    });
}

/**
 * Получает релизы для указанной даты
 */
function getReleasesForDate(releasesData, year, month, day) {
    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    let releases = releasesData[dateStr] || [];
    
    // Применяем фильтр по жанру
    if (activeGenreFilter) {
        releases = releases.filter(movie => 
            movie.genres && movie.genres.toLowerCase().includes(activeGenreFilter.toLowerCase())
        );
    }
    
    return releases;
}

/**
 * Собирает все уникальные жанры из релизов
 */
function collectGenres(releasesData) {
    allGenres.clear();
    
    Object.values(releasesData).forEach(dayReleases => {
        dayReleases.forEach(movie => {
            if (movie.genres) {
                movie.genres.split(', ').forEach(genre => {
                    if (genre.trim()) {
                        allGenres.add(genre.trim());
                    }
                });
            }
        });
    });
    
    return Array.from(allGenres).sort();
}

/**
 * Обновляет dropdown фильтра жанров
 */
function updateGenreFilter(genres) {
    const filterContainer = document.getElementById('genre-filter-container');
    if (!filterContainer) return;
    
    if (viewMode !== 'releases' || genres.length === 0) {
        filterContainer.style.display = 'none';
        return;
    }
    
    filterContainer.style.display = 'flex';
    
    const optionsContainer = document.getElementById('genre-filter-options');
    const hiddenInput = document.getElementById('genre-filter');
    if (!optionsContainer || !hiddenInput) return;
    
    const currentValue = hiddenInput.value;
    
    // Очищаем и пересоздаём опции
    optionsContainer.innerHTML = '';
    
    // Добавляем "Все жанры"
    const allOption = document.createElement('div');
    allOption.className = 'custom-select-option' + (currentValue === '' ? ' selected' : '');
    allOption.dataset.value = '';
    allOption.textContent = 'Все жанры';
    optionsContainer.appendChild(allOption);
    
    // Добавляем жанры
    genres.forEach(genre => {
        const option = document.createElement('div');
        option.className = 'custom-select-option' + (genre === currentValue ? ' selected' : '');
        option.dataset.value = genre;
        option.textContent = genre;
        optionsContainer.appendChild(option);
    });
    
    // Добавляем обработчики для опций
    setupCustomSelectOptions();
}

/**
 * Настраивает обработчики для кастомного select
 */
function setupCustomSelect() {
    const wrapper = document.getElementById('genre-filter-wrapper');
    const trigger = document.getElementById('genre-filter-trigger');
    
    if (!wrapper || !trigger) return;
    
    // Открытие/закрытие по клику на триггер
    trigger.addEventListener('click', (e) => {
        e.stopPropagation();
        wrapper.classList.toggle('open');
    });
    
    // Закрытие при клике вне
    document.addEventListener('click', (e) => {
        if (!wrapper.contains(e.target)) {
            wrapper.classList.remove('open');
        }
    });
    
    // Закрытие при нажатии Escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            wrapper.classList.remove('open');
        }
    });
}

/**
 * Настраивает обработчики для опций кастомного select
 */
function setupCustomSelectOptions() {
    const wrapper = document.getElementById('genre-filter-wrapper');
    const trigger = document.getElementById('genre-filter-trigger');
    const optionsContainer = document.getElementById('genre-filter-options');
    const hiddenInput = document.getElementById('genre-filter');
    
    if (!optionsContainer) return;
    
    optionsContainer.querySelectorAll('.custom-select-option').forEach(option => {
        option.addEventListener('click', (e) => {
            e.stopPropagation();
            
            const value = option.dataset.value;
            const text = option.textContent.replace('✓', '').trim();
            
            // Обновляем выбранную опцию
            optionsContainer.querySelectorAll('.custom-select-option').forEach(opt => {
                opt.classList.remove('selected');
            });
            option.classList.add('selected');
            
            // Обновляем триггер
            if (trigger) {
                trigger.querySelector('span').textContent = text;
            }
            
            // Обновляем скрытый input
            if (hiddenInput) {
                hiddenInput.value = value;
            }
            
            // Закрываем dropdown
            if (wrapper) {
                wrapper.classList.remove('open');
            }
            
            // Применяем фильтр
            activeGenreFilter = value;
            renderCalendar();
        });
    });
}

/**
 * Проверяет, есть ли валидный постер
 */
function hasValidPoster(url) {
    return url && !url.includes('placeholder') && url !== '';
}

/**
 * Создаёт HTML заглушки постера для миниатюры
 */
function createPosterPlaceholder(name) {
    const initials = (name || '?')
        .split(' ')
        .slice(0, 2)
        .map(word => word.charAt(0).toUpperCase())
        .join('');
    
    return `<div class="poster-placeholder"><span>${escapeHtml(initials)}</span></div>`;
}

/**
 * Создаёт HTML заглушки постера для тултипа (большего размера)
 */
function createTooltipPosterPlaceholder(name) {
    const initials = (name || '?')
        .split(' ')
        .slice(0, 2)
        .map(word => word.charAt(0).toUpperCase())
        .join('');
    
    return `
        <div class="tooltip-poster-placeholder">
            <svg class="placeholder-icon" viewBox="0 0 24 24" width="32" height="32">
                <path fill="currentColor" d="M18 4l2 4h-3l-2-4h-2l2 4h-3l-2-4H8l2 4H7L5 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V4h-4z"/>
            </svg>
            <span class="placeholder-initials">${escapeHtml(initials)}</span>
        </div>
    `;
}

/**
 * Создаёт HTML для миниатюры запланированного фильма
 */
function createScheduleThumbnail(schedule) {
    const movie = schedule.movie;
    if (!movie) return '';
    
    const statusClass = schedule.status === 'confirmed' ? 'confirmed' : 'pending';
    const posterUrl = movie.poster_url || movie.poster || '';
    const hasPoster = hasValidPoster(posterUrl);
    
    // Сохраняем данные в data-атрибутах для тултипа
    const dataAttrs = `
        data-name="${escapeHtml(movie.name)}"
        data-year="${escapeHtml(movie.year || '')}"
        data-poster="${escapeHtml(posterUrl)}"
        data-has-poster="${hasPoster}"
        data-genres="${escapeHtml(movie.genres || '')}"
        data-countries="${escapeHtml(movie.countries || '')}"
        data-status="${schedule.status}"
    `.replace(/\n/g, ' ');
    
    const posterContent = hasPoster 
        ? `<img src="${escapeHtml(posterUrl)}" alt="${escapeHtml(movie.name)}" loading="lazy">`
        : createPosterPlaceholder(movie.name);
    
    return `
        <div class="calendar-movie ${statusClass}" ${dataAttrs}>
            ${posterContent}
        </div>
    `;
}

/**
 * Создаёт HTML для миниатюры релиза
 */
function createReleaseThumbnail(movie) {
    if (!movie) return '';
    
    const posterUrl = movie.poster || '';
    const hasPoster = hasValidPoster(posterUrl);
    
    // Определяем класс рейтинга
    let ratingClass = '';
    if (movie.rating_kp) {
        if (movie.rating_kp >= 7) ratingClass = 'rating-high';
        else if (movie.rating_kp >= 5) ratingClass = 'rating-medium';
        else ratingClass = 'rating-low';
    }
    
    // Сохраняем данные в data-атрибутах для тултипа
    const dataAttrs = `
        data-kp-id="${movie.kinopoisk_id || ''}"
        data-name="${escapeHtml(movie.name)}"
        data-year="${escapeHtml(movie.year || '')}"
        data-poster="${escapeHtml(posterUrl)}"
        data-has-poster="${hasPoster}"
        data-rating="${movie.rating_kp || ''}"
        data-genres="${escapeHtml(movie.genres || '')}"
        data-countries="${escapeHtml(movie.countries || '')}"
        data-release-date="${escapeHtml(movie.release_date || '')}"
    `.replace(/\n/g, ' ');
    
    const posterContent = hasPoster 
        ? `<img src="${escapeHtml(posterUrl)}" alt="${escapeHtml(movie.name)}" loading="lazy">`
        : createPosterPlaceholder(movie.name);
    
    return `
        <div class="calendar-movie release ${ratingClass}" ${dataAttrs}>
            ${posterContent}
            ${movie.rating_kp ? `<span class="mini-rating">${movie.rating_kp.toFixed(1)}</span>` : ''}
        </div>
    `;
}

/**
 * Экранирует HTML
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Форматирует дату релиза для отображения
 */
function formatReleaseDate(dateStr) {
    if (!dateStr) return '';
    
    try {
        const date = new Date(dateStr);
        const day = date.getDate();
        const month = MONTH_NAMES_GENITIVE[date.getMonth()];
        return `${day} ${month}`;
    } catch (e) {
        return dateStr;
    }
}

/**
 * Создаёт и показывает тултип
 */
function showTooltip(element, event) {
    // Очищаем предыдущий таймаут
    if (tooltipTimeout) {
        clearTimeout(tooltipTimeout);
    }
    
    // Задержка появления для избежания мерцания
    tooltipTimeout = setTimeout(() => {
        const data = element.dataset;
        
        // Создаём тултип если его нет
        if (!tooltipElement) {
            tooltipElement = document.createElement('div');
            tooltipElement.className = 'movie-tooltip';
            document.body.appendChild(tooltipElement);
        }
        
        // Определяем тип элемента
        const isRelease = element.classList.contains('release');
        
        // Формируем рейтинг
        let ratingHtml = '';
        if (data.rating) {
            const rating = parseFloat(data.rating);
            let ratingClass = 'rating-neutral';
            if (rating >= 7) ratingClass = 'rating-high';
            else if (rating >= 5) ratingClass = 'rating-medium';
            else ratingClass = 'rating-low';
            
            ratingHtml = `<div class="tooltip-rating ${ratingClass}">★ ${rating.toFixed(1)}</div>`;
        }
        
        // Формируем дату релиза
        let releaseDateHtml = '';
        if (data.releaseDate) {
            releaseDateHtml = `<div class="tooltip-release-date">Премьера: ${formatReleaseDate(data.releaseDate)}</div>`;
        }
        
        // Формируем статус для расписания
        let statusHtml = '';
        if (!isRelease && data.status) {
            const statusText = data.status === 'confirmed' ? 'Просмотрено' : 'Запланировано';
            const statusClass = data.status === 'confirmed' ? 'status-confirmed' : 'status-pending';
            statusHtml = `<div class="tooltip-status ${statusClass}">${statusText}</div>`;
        }
        
        // Формируем постер или заглушку для тултипа
        const hasPoster = data.hasPoster === 'true' && data.poster;
        const posterHtml = hasPoster 
            ? `<img src="${data.poster}" alt="${data.name}" loading="lazy">`
            : createTooltipPosterPlaceholder(data.name);
        
        // Заполняем содержимое
        tooltipElement.innerHTML = `
            <div class="tooltip-poster ${hasPoster ? '' : 'no-poster'}">
                ${posterHtml}
            </div>
            <div class="tooltip-info">
                <div class="tooltip-title">${data.name}${data.year ? ` (${data.year})` : ''}</div>
                ${ratingHtml}
                ${data.genres ? `<div class="tooltip-genres">${data.genres}</div>` : ''}
                ${data.countries ? `<div class="tooltip-countries">${data.countries}</div>` : ''}
                ${releaseDateHtml}
                ${statusHtml}
                ${isRelease ? '<div class="tooltip-hint">Клик — открыть на Кинопоиске</div>' : ''}
            </div>
        `;
        
        // Позиционируем тултип
        positionTooltip(element);
        
        // Показываем с анимацией
        tooltipElement.classList.add('visible');
    }, 200);
}

/**
 * Позиционирует тултип относительно элемента
 */
function positionTooltip(element) {
    if (!tooltipElement) return;
    
    const rect = element.getBoundingClientRect();
    const tooltipRect = tooltipElement.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    
    // Предпочтительно справа от элемента
    let left = rect.right + 10;
    let top = rect.top;
    
    // Проверяем, не выходит ли за правый край
    if (left + 280 > viewportWidth) {
        // Показываем слева
        left = rect.left - 290;
        
        // Если и слева не помещается, центрируем под элементом
        if (left < 10) {
            left = Math.max(10, Math.min(rect.left, viewportWidth - 290));
            top = rect.bottom + 10;
        }
    }
    
    // Проверяем, не выходит ли за нижний край
    if (top + 320 > viewportHeight) {
        top = Math.max(10, viewportHeight - 330);
    }
    
    // Проверяем верхний край
    if (top < 10) {
        top = 10;
    }
    
    tooltipElement.style.left = `${left}px`;
    tooltipElement.style.top = `${top}px`;
}

/**
 * Скрывает тултип
 */
function hideTooltip() {
    if (tooltipTimeout) {
        clearTimeout(tooltipTimeout);
        tooltipTimeout = null;
    }
    
    if (tooltipElement) {
        tooltipElement.classList.remove('visible');
    }
}

/**
 * Рендерит календарь
 */
async function renderCalendar() {
    const titleEl = document.getElementById('calendar-title');
    const gridEl = document.getElementById('calendar-grid');
    const emptyEl = document.getElementById('calendar-empty');
    const releasesEmptyEl = document.getElementById('calendar-releases-empty');
    const schedulesLegend = document.getElementById('calendar-legend-schedules');
    const releasesLegend = document.getElementById('calendar-legend-releases');
    
    titleEl.textContent = `${MONTH_NAMES[currentMonth]} ${currentYear}`;
    
    // Показываем/скрываем кнопку "Сегодня"
    updateTodayButton();
    
    // Переключаем легенды
    if (schedulesLegend) schedulesLegend.style.display = viewMode === 'schedules' ? 'flex' : 'none';
    if (releasesLegend) releasesLegend.style.display = viewMode === 'releases' ? 'flex' : 'none';
    
    let itemsData = [];
    
    if (viewMode === 'schedules') {
        await loadSchedules(currentYear, currentMonth);
        itemsData = schedulesCache;
        updateGenreFilter([]);
    } else {
        itemsData = await loadAllFilteredReleases(currentYear, currentMonth);
        const genres = collectGenres(itemsData);
        updateGenreFilter(genres);
    }
    
    const daysInMonth = getDaysInMonth(currentYear, currentMonth);
    const firstDay = getFirstDayOfMonth(currentYear, currentMonth);
    
    const today = new Date();
    const isCurrentMonth = today.getFullYear() === currentYear && today.getMonth() === currentMonth;
    const todayDate = today.getDate();
    
    let html = '';
    
    // Пустые ячейки до первого дня месяца
    for (let i = 0; i < firstDay; i++) {
        html += '<div class="calendar-day empty"></div>';
    }
    
    // Дни месяца
    let hasAnyItems = false;
    for (let day = 1; day <= daysInMonth; day++) {
        let items = [];
        
        if (viewMode === 'schedules') {
            items = getSchedulesForDate(currentYear, currentMonth, day);
        } else {
            items = getReleasesForDate(itemsData, currentYear, currentMonth, day);
        }
        
        const isToday = isCurrentMonth && day === todayDate;
        const isPast = new Date(currentYear, currentMonth, day) < new Date(today.getFullYear(), today.getMonth(), today.getDate());
        
        let dayClass = 'calendar-day';
        if (isToday) dayClass += ' today';
        if (isPast && viewMode === 'schedules') dayClass += ' past';
        if (items.length > 0) {
            dayClass += ' has-movies';
            hasAnyItems = true;
            
            // Подсветка дней с большим количеством релизов
            if (items.length >= 5) dayClass += ' many-releases';
            else if (items.length >= 3) dayClass += ' some-releases';
        }
        
        html += `<div class="${dayClass}">`;
        html += `<span class="day-number">${day}</span>`;
        
        if (items.length > 0) {
            // Показываем ВСЕ миниатюры без ограничений
            html += '<div class="day-movies">';
            items.forEach(item => {
                if (viewMode === 'schedules') {
                    html += createScheduleThumbnail(item);
                } else {
                    html += createReleaseThumbnail(item);
                }
            });
            html += '</div>';
        }
        
        html += '</div>';
    }
    
    // Заполняем оставшиеся ячейки до конца недели
    const totalCells = firstDay + daysInMonth;
    const remainingCells = totalCells % 7 === 0 ? 0 : 7 - (totalCells % 7);
    for (let i = 0; i < remainingCells; i++) {
        html += '<div class="calendar-day empty"></div>';
    }
    
    gridEl.innerHTML = html;
    
    // Управляем сообщениями о пустом календаре
    if (emptyEl) {
        emptyEl.style.display = (viewMode === 'schedules' && schedulesCache.length === 0) ? 'block' : 'none';
    }
    if (releasesEmptyEl) {
        const releasesCount = viewMode === 'releases' ? Object.keys(itemsData).length : 0;
        releasesEmptyEl.style.display = (viewMode === 'releases' && releasesCount === 0) ? 'block' : 'none';
    }
    
    // Добавляем обработчики событий для миниатюр
    setupMovieEventHandlers(gridEl);
}

/**
 * Настраивает обработчики событий для миниатюр фильмов
 */
function setupMovieEventHandlers(gridEl) {
    gridEl.querySelectorAll('.calendar-movie').forEach(el => {
        // Hover для тултипа
        el.addEventListener('mouseenter', (e) => {
            showTooltip(el, e);
        });
        
        el.addEventListener('mouseleave', () => {
            hideTooltip();
        });
        
        // Клик для релизов - открываем Кинопоиск
        if (el.classList.contains('release')) {
            el.addEventListener('click', (e) => {
                const kpId = el.dataset.kpId;
                if (kpId) {
                    window.open(`https://www.kinopoisk.ru/film/${kpId}/`, '_blank');
                }
            });
        }
    });
    
    // Настраиваем плавную прокрутку с меньшим шагом для контейнеров миниатюр
    setupSmoothScroll(gridEl);
}

/**
 * Настраивает плавную прокрутку с меньшим шагом для контейнеров .day-movies
 */
function setupSmoothScroll(gridEl) {
    gridEl.querySelectorAll('.day-movies').forEach(container => {
        container.addEventListener('wheel', (e) => {
            // Проверяем, нужен ли скролл (есть ли переполнение)
            if (container.scrollHeight <= container.clientHeight) {
                return; // Нет скролла - ничего не делаем
            }
            
            e.preventDefault();
            
            // Уменьшаем шаг прокрутки (делим на 3)
            const scrollStep = Math.sign(e.deltaY) * 25;
            
            container.scrollBy({
                top: scrollStep,
                behavior: 'smooth'
            });
        }, { passive: false });
    });
}

/**
 * Обновляет видимость кнопки "Сегодня"
 */
function updateTodayButton() {
    const todayBtn = document.getElementById('today-btn');
    if (!todayBtn) return;
    
    const now = new Date();
    const isCurrentMonth = now.getFullYear() === currentYear && now.getMonth() === currentMonth;
    
    todayBtn.style.display = isCurrentMonth ? 'none' : 'inline-flex';
}

/**
 * Переход к текущему месяцу
 */
function goToToday() {
    const now = new Date();
    currentYear = now.getFullYear();
    currentMonth = now.getMonth();
    renderCalendar();
}

/**
 * Переключает режим отображения
 */
function setViewMode(mode) {
    if (mode === viewMode) return;
    
    viewMode = mode;
    
    // Сохраняем в localStorage
    localStorage.setItem('calendar-view-mode', mode);
    
    // Сбрасываем фильтр жанров
    activeGenreFilter = '';
    const hiddenInput = document.getElementById('genre-filter');
    const trigger = document.getElementById('genre-filter-trigger');
    if (hiddenInput) hiddenInput.value = '';
    if (trigger) trigger.querySelector('span').textContent = 'Все жанры';
    
    // Обновляем активную кнопку
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.mode === mode);
    });
    
    renderCalendar();
}

/**
 * Переход к предыдущему месяцу
 */
function prevMonth() {
    currentMonth--;
    if (currentMonth < 0) {
        currentMonth = 11;
        currentYear--;
    }
    renderCalendar();
}

/**
 * Переход к следующему месяцу
 */
function nextMonth() {
    currentMonth++;
    if (currentMonth > 11) {
        currentMonth = 0;
        currentYear++;
    }
    renderCalendar();
}

/**
 * Обновляет состояние фильтра релизов и сохраняет в localStorage
 */
function updateReleaseFilter(type, enabled) {
    releaseFilters[type] = enabled;
    localStorage.setItem('calendar-release-filters', JSON.stringify(releaseFilters));
    renderCalendar();
}

/**
 * Синхронизирует состояние чекбоксов с releaseFilters
 */
function syncReleaseFilterCheckboxes() {
    const russiaToggle = document.getElementById('russia-releases-toggle');
    const worldToggle = document.getElementById('world-releases-toggle');
    const digitalToggle = document.getElementById('digital-releases-toggle');
    
    if (russiaToggle) russiaToggle.checked = releaseFilters.russia;
    if (worldToggle) worldToggle.checked = releaseFilters.world;
    if (digitalToggle) digitalToggle.checked = releaseFilters.digital;
}

// Инициализация
document.addEventListener('DOMContentLoaded', () => {
    const prevBtn = document.getElementById('prev-month');
    const nextBtn = document.getElementById('next-month');
    const todayBtn = document.getElementById('today-btn');
    
    // Чекбоксы фильтров релизов
    const russiaToggle = document.getElementById('russia-releases-toggle');
    const worldToggle = document.getElementById('world-releases-toggle');
    const digitalToggle = document.getElementById('digital-releases-toggle');
    
    if (prevBtn) prevBtn.addEventListener('click', prevMonth);
    if (nextBtn) nextBtn.addEventListener('click', nextMonth);
    if (todayBtn) todayBtn.addEventListener('click', goToToday);
    
    // Обработчики переключения режимов
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            setViewMode(btn.dataset.mode);
        });
        
        // Устанавливаем активную кнопку из localStorage
        btn.classList.toggle('active', btn.dataset.mode === viewMode);
    });
    
    // Обработчики фильтров типов релизов
    if (russiaToggle) {
        russiaToggle.addEventListener('change', () => {
            updateReleaseFilter('russia', russiaToggle.checked);
        });
    }
    
    if (worldToggle) {
        worldToggle.addEventListener('change', () => {
            updateReleaseFilter('world', worldToggle.checked);
        });
    }
    
    if (digitalToggle) {
        digitalToggle.addEventListener('change', () => {
            updateReleaseFilter('digital', digitalToggle.checked);
        });
    }
    
    // Синхронизируем состояние чекбоксов с сохранёнными настройками
    syncReleaseFilterCheckboxes();
    
    // Настраиваем кастомный select для жанров
    setupCustomSelect();
    
    // Скрываем тултип при скролле
    window.addEventListener('scroll', hideTooltip, { passive: true });
    
    // Рендерим календарь
    renderCalendar();
});
