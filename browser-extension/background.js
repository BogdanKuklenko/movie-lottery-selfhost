// Background Service Worker для Movie Lottery Extension
/* global chrome */

// Значения по умолчанию
const DEFAULT_SERVER_URL = 'http://localhost:8888';

// Получение URL сервера из storage
async function getServerUrl() {
  const result = await chrome.storage.sync.get(['serverUrl']);
  return result.serverUrl || DEFAULT_SERVER_URL;
}

// Слушаем сообщения от content script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'addMovieToLibrary') {
    handleAddMovie(request.url)
      .then(response => sendResponse(response))
      .catch(error => sendResponse({ success: false, message: error.message }));
    return true; // Важно для асинхронного ответа
  }
  
  if (request.action === 'getServerUrl') {
    getServerUrl().then(url => sendResponse({ serverUrl: url }));
    return true;
  }
});

/**
 * Находит все открытые вкладки с библиотекой и вызывает обновление.
 * Использует chrome.scripting.executeScript с world: 'MAIN' 
 * для доступа к контексту страницы.
 */
async function refreshLibraryTabs(movieData) {
  try {
    // Получаем все вкладки
    const tabs = await chrome.tabs.query({});
    
    // Фильтруем вкладки с /library в URL
    const libraryTabs = tabs.filter(tab => 
      tab.url && tab.url.includes('/library')
    );
    
    if (libraryTabs.length === 0) {
      console.log('Movie Lottery: No library tabs found');
      return;
    }
    
    console.log(`Movie Lottery: Found ${libraryTabs.length} library tab(s)`);
    
    // Выполняем скрипт обновления на каждой вкладке библиотеки
    for (const tab of libraryTabs) {
      try {
        await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          world: 'MAIN', // Выполняем в контексте страницы
          func: (movie) => {
            // Вызываем глобальную функцию обновления если она есть
            if (typeof window.refreshLibraryFromExtension === 'function') {
              window.refreshLibraryFromExtension(movie);
            } else {
              console.warn('Movie Lottery: refreshLibraryFromExtension not found, reloading page');
              // Fallback: перезагружаем страницу
              window.location.reload();
            }
          },
          args: [movieData]
        });
        console.log(`Movie Lottery: Refreshed tab ${tab.id}`);
      } catch (error) {
        // Игнорируем ошибки (вкладка могла быть закрыта или не иметь доступа)
        console.warn(`Movie Lottery: Could not refresh tab ${tab.id}:`, error.message);
      }
    }
  } catch (error) {
    console.error('Movie Lottery: Error refreshing library tabs:', error);
  }
}

// Обработка добавления фильма
async function handleAddMovie(movieUrl) {
  const serverUrl = await getServerUrl();
  const apiUrl = `${serverUrl}/api/library/add-from-url`;
  
  try {
    const response = await fetch(apiUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ url: movieUrl }),
    });
    
    const data = await response.json();
    
    if (!response.ok) {
      return {
        success: false,
        message: data.message || `Ошибка сервера: ${response.status}`,
      };
    }
    
    // После успешного добавления — обновляем открытые вкладки библиотеки
    if (data.success && data.movie) {
      await refreshLibraryTabs(data.movie);
    }
    
    return data;
  } catch (error) {
    console.error('Movie Lottery Extension Error:', error);
    return {
      success: false,
      message: `Не удалось подключиться к серверу. Проверьте, что сервер запущен на ${serverUrl}`,
    };
  }
}
