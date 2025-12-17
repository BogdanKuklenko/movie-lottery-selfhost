---
name: Исправление центрирования видео в fullscreen
overview: ""
todos:
  - id: 1e3872d7-ca29-4d6f-a400-a82447a2290f
    content: Заменить flex на grid для .trailer-player-wrapper в fullscreen
    status: pending
  - id: 33acc2cd-7d94-4389-ad75-f836384a44cb
    content: Исправить размеры .trailer-video - убрать 100% width/height
    status: pending
  - id: 1f0b6233-3a1f-4ca4-8a69-be974256bc50
    content: Обнулить все safe-area отступы в fullscreen режиме
    status: pending
---

# Исправление центрирования видео в fullscreen

## Проблема

Видео смещено влево в fullscreen режиме на некоторых браузерах Android. Текущий подход с Flexbox и `margin: auto` не работает надёжно.

## Решение

### Использовать CSS Grid для центрирования

CSS Grid с `place-items: center` даёт более надёжное центрирование, чем Flexbox, особенно когда есть абсолютно позиционированные дочерние элементы (контролы).

### Файл: [`movie_lottery/static/css/components/_polls.css`](movie_lottery/static/css/components/_polls.css)

#### 1. Изменить стили `.trailer-player-wrapper` в fullscreen (строки ~2207-2217)

Заменить flex на grid:

```css
.trailer-fullscreen-modal:fullscreen .trailer-player-wrapper {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    background: #000;
    margin: 0;
    padding: 0;
}
```

#### 2. Изменить стили `.trailer-video` в fullscreen (строки ~2219-2230)

Убрать `width/height: 100%` которые растягивают видео, оставить только `max-width/max-height`:

```css
.trailer-fullscreen-modal:fullscreen .trailer-video {
    max-width: 100%;
    max-height: 100%;
    width: auto;
    height: auto;
    object-fit: contain;
    margin: 0;
    padding: 0;
}
```

#### 3. Обнулить все safe-area отступы в fullscreen

Добавить `!important` для сброса padding на всех уровнях контейнера.