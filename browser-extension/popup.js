// Movie Lottery Extension - Popup Script
/* global chrome */

const DEFAULT_SERVER_URL = 'http://localhost:8888';

document.addEventListener('DOMContentLoaded', async () => {
  const serverUrlInput = document.getElementById('serverUrl');
  const saveBtn = document.getElementById('saveBtn');
  const statusMessage = document.getElementById('statusMessage');
  
  const movieUrlInput = document.getElementById('movieUrl');
  const addBtn = document.getElementById('addBtn');
  const addStatusMessage = document.getElementById('addStatusMessage');

  // Загружаем сохранённый URL
  const { serverUrl } = await chrome.storage.sync.get(['serverUrl']);
  serverUrlInput.value = serverUrl || DEFAULT_SERVER_URL;

  // Сохранение URL сервера
  saveBtn.addEventListener('click', async () => {
    const url = serverUrlInput.value.trim();
    
    if (!url) {
      showStatus(statusMessage, 'Введите URL сервера', 'error');
      return;
    }

    // Простая валидация URL
    try {
      new URL(url);
    } catch {
      showStatus(statusMessage, 'Некорректный URL', 'error');
      return;
    }

    // Убираем trailing slash
    const cleanUrl = url.replace(/\/+$/, '');
    
    await chrome.storage.sync.set({ serverUrl: cleanUrl });
    showStatus(statusMessage, 'Сохранено!', 'success');
    
    // Очищаем статус через 2 секунды
    setTimeout(() => {
      statusMessage.textContent = '';
      statusMessage.className = 'status-message';
    }, 2000);
  });

  // Быстрое добавление фильма
  addBtn.addEventListener('click', async () => {
    const movieUrl = movieUrlInput.value.trim();
    
    if (!movieUrl) {
      showStatus(addStatusMessage, 'Введите ссылку или ID фильма', 'error');
      return;
    }

    addBtn.disabled = true;
    showStatus(addStatusMessage, 'Добавление...', 'loading');

    try {
      const response = await chrome.runtime.sendMessage({
        action: 'addMovieToLibrary',
        url: movieUrl,
      });

      if (response.success) {
        showStatus(addStatusMessage, response.message, 'success');
        movieUrlInput.value = '';
        
        // Очищаем статус через 3 секунды
        setTimeout(() => {
          addStatusMessage.textContent = '';
          addStatusMessage.className = 'status-message';
        }, 3000);
      } else {
        showStatus(addStatusMessage, response.message, 'error');
      }
    } catch (error) {
      console.error('Error:', error);
      showStatus(addStatusMessage, 'Ошибка соединения с расширением', 'error');
    } finally {
      addBtn.disabled = false;
    }
  });

  // Enter для быстрого добавления
  movieUrlInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      addBtn.click();
    }
  });

  // Enter для сохранения URL
  serverUrlInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      saveBtn.click();
    }
  });
});

function showStatus(element, message, type) {
  element.textContent = message;
  element.className = `status-message ${type}`;
}

