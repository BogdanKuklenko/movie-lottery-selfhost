// movie_lottery/static/js/utils/pollTheme.js
// Модуль управления темами страницы опроса

const THEME_COOKIE_NAME = 'poll_theme';
const THEME_COOKIE_MAX_AGE = 60 * 60 * 24 * 365; // 1 год
const THEME_LINK_ID_PREFIX = 'poll-theme-css-';

// Доступные темы
const AVAILABLE_THEMES = ['default', 'newyear'];

/**
 * Получает значение cookie по имени
 * @param {string} name - имя cookie
 * @returns {string|null}
 */
function getCookie(name) {
    const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
    return match ? decodeURIComponent(match[2]) : null;
}

/**
 * Устанавливает cookie
 * @param {string} name - имя cookie
 * @param {string} value - значение
 * @param {number} maxAge - время жизни в секундах
 */
function setCookie(name, value, maxAge = THEME_COOKIE_MAX_AGE) {
    const secureFlag = window.location.protocol === 'https:' ? '; Secure' : '';
    document.cookie = `${name}=${encodeURIComponent(value)}; Max-Age=${maxAge}; Path=/; SameSite=Lax${secureFlag}`;
}

/**
 * Получает тему из URL параметра
 * @returns {string|null}
 */
function getThemeFromURL() {
    const params = new URLSearchParams(window.location.search);
    const theme = params.get('theme');
    return theme && AVAILABLE_THEMES.includes(theme) ? theme : null;
}

/**
 * Получает текущую тему из cookie
 * @returns {string}
 */
function getThemeFromCookie() {
    const theme = getCookie(THEME_COOKIE_NAME);
    return theme && AVAILABLE_THEMES.includes(theme) ? theme : 'default';
}

/**
 * Получает текущую активную тему
 * @returns {string}
 */
export function getCurrentTheme() {
    // URL параметр имеет приоритет
    const urlTheme = getThemeFromURL();
    if (urlTheme) return urlTheme;
    
    return getThemeFromCookie();
}

/**
 * Возвращает список доступных тем
 * @returns {string[]}
 */
export function getAvailableThemes() {
    return [...AVAILABLE_THEMES];
}

/**
 * Генерирует путь к CSS файлу темы
 * @param {string} themeName - название темы
 * @returns {string}
 */
function getThemeCSSPath(themeName) {
    return `/static/css/components/themes/poll_theme_${themeName}.css`;
}

/**
 * Загружает CSS файл темы
 * @param {string} themeName - название темы
 * @returns {Promise<void>}
 */
function loadThemeCSS(themeName) {
    return new Promise((resolve, reject) => {
        if (themeName === 'default') {
            resolve();
            return;
        }
        
        const linkId = THEME_LINK_ID_PREFIX + themeName;
        
        // Проверяем, не загружен ли уже этот CSS
        if (document.getElementById(linkId)) {
            resolve();
            return;
        }
        
        const link = document.createElement('link');
        link.id = linkId;
        link.rel = 'stylesheet';
        link.href = getThemeCSSPath(themeName);
        
        link.onload = () => resolve();
        link.onerror = () => reject(new Error(`Failed to load theme CSS: ${themeName}`));
        
        document.head.appendChild(link);
    });
}

/**
 * Удаляет CSS файл темы из DOM
 * @param {string} themeName - название темы
 */
function unloadThemeCSS(themeName) {
    if (themeName === 'default') return;
    
    const linkId = THEME_LINK_ID_PREFIX + themeName;
    const existingLink = document.getElementById(linkId);
    if (existingLink) {
        existingLink.remove();
    }
}

/**
 * Удаляет все загруженные темы CSS (кроме текущей)
 * @param {string} exceptTheme - тема, которую не нужно удалять
 */
function unloadAllThemesExcept(exceptTheme) {
    AVAILABLE_THEMES.forEach(theme => {
        if (theme !== exceptTheme && theme !== 'default') {
            unloadThemeCSS(theme);
        }
    });
}

/**
 * Обновляет класс темы на body
 * @param {string} themeName - название темы
 */
function updateBodyClass(themeName) {
    // Удаляем все классы тем
    AVAILABLE_THEMES.forEach(theme => {
        document.body.classList.remove(`poll-theme-${theme}`);
    });
    
    // Добавляем новый класс темы
    document.body.classList.add(`poll-theme-${themeName}`);
}

/**
 * Устанавливает тему
 * @param {string} themeName - название темы
 * @returns {Promise<void>}
 */
export async function setPollTheme(themeName) {
    if (!AVAILABLE_THEMES.includes(themeName)) {
        console.warn(`Unknown theme: ${themeName}, falling back to default`);
        themeName = 'default';
    }
    
    // Сохраняем в cookie
    setCookie(THEME_COOKIE_NAME, themeName);
    
    // Удаляем CSS других тем
    unloadAllThemesExcept(themeName);
    
    // Загружаем CSS новой темы (если не default)
    await loadThemeCSS(themeName);
    
    // Обновляем класс на body
    updateBodyClass(themeName);
    
    // Отправляем событие для обновления UI
    document.dispatchEvent(new CustomEvent('pollThemeChanged', { 
        detail: { theme: themeName } 
    }));
}

/**
 * Переключает тему на следующую в списке
 * @returns {Promise<string>} - название новой темы
 */
export async function togglePollTheme() {
    const currentTheme = getCurrentTheme();
    const currentIndex = AVAILABLE_THEMES.indexOf(currentTheme);
    const nextIndex = (currentIndex + 1) % AVAILABLE_THEMES.length;
    const nextTheme = AVAILABLE_THEMES[nextIndex];
    
    await setPollTheme(nextTheme);
    return nextTheme;
}

/**
 * Инициализирует систему тем
 * Вызывается при загрузке страницы
 * @returns {Promise<string>} - активная тема
 */
export async function initPollTheme() {
    const theme = getCurrentTheme();
    
    // Если URL параметр указан, сохраняем его в cookie
    const urlTheme = getThemeFromURL();
    if (urlTheme) {
        setCookie(THEME_COOKIE_NAME, urlTheme);
    }
    
    // Загружаем CSS темы (если не загружен ранним скриптом)
    await loadThemeCSS(theme);
    
    // Обновляем класс на body (на случай если ранний скрипт не сработал)
    updateBodyClass(theme);
    
    return theme;
}

/**
 * Возвращает информацию о теме для отображения
 * @param {string} themeName - название темы
 * @returns {{name: string, icon: string, label: string}}
 */
export function getThemeInfo(themeName) {
    const themes = {
        'default': {
            name: 'default',
            icon: '🎬',
            label: 'Обычная тема'
        },
        'newyear': {
            name: 'newyear',
            icon: '🎄',
            label: 'Новогодняя тема'
        }
    };
    
    return themes[themeName] || themes['default'];
}






