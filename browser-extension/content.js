// Content Script для Кинопоиска
// Добавляет кнопку на страницы фильмов/сериалов
/* global chrome */

(function() {
  'use strict';

  // Проверяем, что мы на странице фильма
  const isMoviePage = /kinopoisk\.ru\/(film|series)\/\d+/.test(window.location.href);
  if (!isMoviePage) return;

  // ID для предотвращения дублирования
  const BUTTON_ID = 'ml-add-to-library-btn';
  const TOAST_ID = 'ml-toast-container';

  // Ждём загрузки страницы
  let attempts = 0;
  const maxAttempts = 30;

  function init() {
    // Если кнопка уже есть — не добавляем
    if (document.getElementById(BUTTON_ID)) return;

    // Ищем контейнер для кнопки (возле заголовка фильма)
    const titleContainer = findTitleContainer();
    
    if (titleContainer) {
      injectButton(titleContainer);
    } else if (attempts < maxAttempts) {
      attempts++;
      setTimeout(init, 500);
    }
  }

  function findTitleContainer() {
    // Пробуем разные селекторы для Кинопоиска
    const selectors = [
      '[data-test-id="encyclopedic-table"]', // Новый дизайн
      '.styles_root__ti07r', // Контейнер информации
      '.styles_titleContainer__0GWMV', // Заголовок
      '.film-page', // Старый дизайн
      '[class*="styles_header"]', // Общий селектор
      'h1[data-tid]', // Заголовок h1
    ];

    for (const selector of selectors) {
      const el = document.querySelector(selector);
      if (el) return el;
    }

    return null;
  }

  function injectButton(container) {
    // Создаём кнопку
    const button = document.createElement('button');
    button.id = BUTTON_ID;
    button.className = 'ml-button';
    button.innerHTML = `
      <svg class="ml-button-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 5v14M5 12h14"/>
      </svg>
      <span class="ml-button-text">В библиотеку</span>
    `;

    // Находим подходящее место для вставки
    const insertionPoint = findInsertionPoint(container);
    
    if (insertionPoint) {
      insertionPoint.parentNode.insertBefore(button, insertionPoint.nextSibling);
    } else {
      // Вставляем в начало контейнера если не нашли точку
      container.insertBefore(button, container.firstChild);
    }

    // Обработчик клика
    button.addEventListener('click', handleButtonClick);
  }

  function findInsertionPoint(container) {
    // Ищем кнопки действий Кинопоиска
    const actionSelectors = [
      '[data-tid="b6ed9a57"]', // Кнопки действий
      '[class*="styles_buttons"]',
      '[class*="actions"]',
      'button[class*="style"]',
    ];

    for (const selector of actionSelectors) {
      const el = container.querySelector(selector);
      if (el) return el.parentElement || el;
    }

    return null;
  }

  async function handleButtonClick(event) {
    const button = event.currentTarget;
    
    // Блокируем повторные клики
    if (button.classList.contains('ml-loading')) return;
    
    button.classList.add('ml-loading');
    button.innerHTML = `
      <svg class="ml-spinner" viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" fill="none" stroke-dasharray="40 60"/>
      </svg>
      <span class="ml-button-text">Добавление...</span>
    `;

    try {
      // Отправляем текущий URL в background script
      const response = await chrome.runtime.sendMessage({
        action: 'addMovieToLibrary',
        url: window.location.href,
      });

      if (response.success) {
        showToast(response.message, 'success', response.movie);
        button.classList.remove('ml-loading');
        button.classList.add('ml-success');
        button.innerHTML = `
          <svg class="ml-button-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="20,6 9,17 4,12"/>
          </svg>
          <span class="ml-button-text">Добавлено!</span>
        `;
        
        // Возвращаем исходное состояние через 3 секунды
        setTimeout(() => {
          button.classList.remove('ml-success');
          button.innerHTML = `
            <svg class="ml-button-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 5v14M5 12h14"/>
            </svg>
            <span class="ml-button-text">В библиотеку</span>
          `;
        }, 3000);
      } else {
        showToast(response.message, 'error');
        button.classList.remove('ml-loading');
        button.innerHTML = `
          <svg class="ml-button-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 5v14M5 12h14"/>
          </svg>
          <span class="ml-button-text">В библиотеку</span>
        `;
      }
    } catch (error) {
      console.error('Movie Lottery Extension Error:', error);
      showToast('Ошибка расширения. Попробуйте обновить страницу.', 'error');
      button.classList.remove('ml-loading');
      button.innerHTML = `
        <svg class="ml-button-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 5v14M5 12h14"/>
        </svg>
        <span class="ml-button-text">В библиотеку</span>
      `;
    }
  }

  function showToast(message, type = 'info', movie = null) {
    // Удаляем старый toast если есть
    const existingToast = document.getElementById(TOAST_ID);
    if (existingToast) {
      existingToast.remove();
    }

    // Создаём контейнер для toast
    const container = document.createElement('div');
    container.id = TOAST_ID;
    container.className = `ml-toast ml-toast-${type}`;

    // Иконка
    let iconSvg = '';
    if (type === 'success') {
      iconSvg = `
        <svg class="ml-toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <polyline points="8,12 11,15 16,9"/>
        </svg>
      `;
    } else if (type === 'error') {
      iconSvg = `
        <svg class="ml-toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <line x1="15" y1="9" x2="9" y2="15"/>
          <line x1="9" y1="9" x2="15" y2="15"/>
        </svg>
      `;
    } else {
      iconSvg = `
        <svg class="ml-toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <line x1="12" y1="16" x2="12" y2="12"/>
          <line x1="12" y1="8" x2="12" y2="8"/>
        </svg>
      `;
    }

    // Дополнительная информация о фильме
    let movieInfo = '';
    if (movie && movie.poster) {
      movieInfo = `
        <div class="ml-toast-movie">
          <img src="${movie.poster}" alt="${movie.name}" class="ml-toast-poster"/>
          <div class="ml-toast-movie-info">
            <div class="ml-toast-movie-name">${movie.name}</div>
            ${movie.year ? `<div class="ml-toast-movie-year">${movie.year}</div>` : ''}
          </div>
        </div>
      `;
    }

    container.innerHTML = `
      <div class="ml-toast-content">
        ${iconSvg}
        <div class="ml-toast-body">
          <div class="ml-toast-message">${message}</div>
          ${movieInfo}
        </div>
        <button class="ml-toast-close" aria-label="Закрыть">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>
      <div class="ml-toast-progress"></div>
    `;

    document.body.appendChild(container);

    // Анимация появления
    requestAnimationFrame(() => {
      container.classList.add('ml-toast-visible');
    });

    // Закрытие по клику
    container.querySelector('.ml-toast-close').addEventListener('click', () => {
      hideToast(container);
    });

    // Автоматическое закрытие через 5 секунд
    setTimeout(() => {
      hideToast(container);
    }, 5000);
  }

  function hideToast(container) {
    if (!container || !container.parentNode) return;
    
    container.classList.remove('ml-toast-visible');
    container.classList.add('ml-toast-hiding');
    
    setTimeout(() => {
      if (container.parentNode) {
        container.remove();
      }
    }, 300);
  }

  // Запускаем инициализацию
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Наблюдаем за изменениями DOM (для SPA навигации)
  const observer = new MutationObserver(() => {
    if (!document.getElementById(BUTTON_ID)) {
      init();
    }
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true,
  });
})();

