// Календарь запланированных фильмов

const MONTH_NAMES = [
    'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
    'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
];

let currentYear = new Date().getFullYear();
let currentMonth = new Date().getMonth(); // 0-11
let schedulesCache = [];

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
 * Создаёт HTML для миниатюры фильма
 */
function createMovieThumbnail(schedule) {
    const movie = schedule.movie;
    if (!movie) return '';
    
    const statusClass = schedule.status === 'confirmed' ? 'confirmed' : 'pending';
    const posterUrl = movie.poster_url || movie.poster || 'https://via.placeholder.com/40x60.png?text=?';
    const title = movie.name + (movie.year ? ` (${movie.year})` : '');
    
    return `
        <div class="calendar-movie ${statusClass}" title="${escapeHtml(title)}">
            <img src="${escapeHtml(posterUrl)}" alt="${escapeHtml(movie.name)}" loading="lazy">
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
 * Рендерит календарь
 */
async function renderCalendar() {
    const titleEl = document.getElementById('calendar-title');
    const gridEl = document.getElementById('calendar-grid');
    const emptyEl = document.getElementById('calendar-empty');
    
    titleEl.textContent = `${MONTH_NAMES[currentMonth]} ${currentYear}`;
    
    // Загружаем расписания для текущего месяца
    await loadSchedules(currentYear, currentMonth);
    
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
    let hasAnySchedules = false;
    for (let day = 1; day <= daysInMonth; day++) {
        const schedules = getSchedulesForDate(currentYear, currentMonth, day);
        const isToday = isCurrentMonth && day === todayDate;
        const isPast = new Date(currentYear, currentMonth, day) < new Date(today.getFullYear(), today.getMonth(), today.getDate());
        
        let dayClass = 'calendar-day';
        if (isToday) dayClass += ' today';
        if (isPast) dayClass += ' past';
        if (schedules.length > 0) {
            dayClass += ' has-movies';
            hasAnySchedules = true;
        }
        
        html += `<div class="${dayClass}">`;
        html += `<span class="day-number">${day}</span>`;
        
        if (schedules.length > 0) {
            html += '<div class="day-movies">';
            // Ограничиваем количество отображаемых миниатюр
            const displaySchedules = schedules.slice(0, 3);
            displaySchedules.forEach(schedule => {
                html += createMovieThumbnail(schedule);
            });
            if (schedules.length > 3) {
                html += `<div class="more-movies">+${schedules.length - 3}</div>`;
            }
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
    
    // Проверяем, есть ли расписания вообще (для всех месяцев)
    // Показываем сообщение только если загрузка завершена и данных нет
    if (emptyEl) {
        emptyEl.style.display = schedulesCache.length === 0 ? 'block' : 'none';
    }
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

// Инициализация
document.addEventListener('DOMContentLoaded', () => {
    const prevBtn = document.getElementById('prev-month');
    const nextBtn = document.getElementById('next-month');
    
    if (prevBtn) prevBtn.addEventListener('click', prevMonth);
    if (nextBtn) nextBtn.addEventListener('click', nextMonth);
    
    // Рендерим календарь
    renderCalendar();
});

