<!-- fd4b87be-d0f5-428d-9201-afc30a63b012 285949ba-e818-411f-9139-b3c7b5207bd1 -->
# Исправление проблем fullscreen режима плеера трейлеров

## Выявленные проблемы (из скриншота и описания)

1. **Полоса прогресса без золотого цвета** - в fullscreen режиме не отображается золотая полоса прогресса воспроизведения
2. **Белая полоса справа** - лишнее пространство под кнопки навигации системы, которое занимает место на экране
3. **Нет автоповорота в landscape** - при включении fullscreen экран должен автоматически переворачиваться в горизонтальное положение
4. **Picture-in-Picture (PiP) при выходе** - видео переходит в режим "окно в окне" при сворачивании, что не нужно

## План исправлений

### 1. Исправить отображение золотой полосы прогресса в fullscreen

В файле [movie_lottery/static/css/components/_polls.css](movie_lottery/static/css/components/_polls.css) CSS для прогресс-бара в fullscreen использует `::-moz-range-progress` который работает только в Firefox. Для Chrome/Safari нужно обновлять градиент через JavaScript.

Проверить и исправить функцию `updateProgressBar()` в [movie_lottery/static/js/pages/poll.js](movie_lottery/static/js/pages/poll.js) чтобы градиент корректно обновлялся в fullscreen режиме.

### 2. Убрать белое пространство справа (safe area)

Исправить CSS чтобы контент занимал весь экран без резервирования места под системные кнопки:

- Установить `padding: 0` для fullscreen контейнера
- Использовать `width: 100%` вместо учёта safe-area справа
- Убедиться что видео растягивается на весь экран

### 3. Добавить автоповорот экрана в landscape при fullscreen

Использовать Screen Orientation API для принудительной блокировки ориентации в landscape:

```javascript
// При входе в fullscreen
if (screen.orientation && screen.orientation.lock) {
    screen.orientation.lock('landscape').catch(() => {});
}

// При выходе из fullscreen
if (screen.orientation && screen.orientation.unlock) {
    screen.orientation.unlock();
}
```

### 4. Отключить режим Picture-in-Picture

Добавить атрибут `disablepictureinpicture` на video элемент в HTML и через JavaScript:

```html
<video disablepictureinpicture ...>
```
```javascript
trailerVideo.disablePictureInPicture = true;
```

Также добавить обработчик для предотвращения автоматического PiP:

```javascript
trailerVideo.addEventListener('enterpictureinpicture', (e) => {
    document.exitPictureInPicture().catch(() => {});
});
```

## Файлы для изменения

- `movie_lottery/templates/poll.html` - добавить атрибут `disablepictureinpicture` на video
- `movie_lottery/static/js/pages/poll.js` - логика автоповорота и отключения PiP, исправление прогресс-бара
- `movie_lottery/static/css/components/_polls.css` - исправить стили для полного использования экрана без белых полос

### To-dos

- [ ] Переписать логику fullscreen: контейнер для Android, video для iOS, fallback на pseudo-fullscreen
- [ ] Добавить CSS класс .pseudo-fullscreen для fallback режима
- [ ] Улучшить CSS центрирования видео во всех fullscreen режимах
- [ ] Обновить функцию exitVideoFullscreen для работы с контейнером и pseudo-fullscreen
- [ ] приведи внешний вид плеера к общему стилю сайта во всех режимах