// movie_lottery/static/js/components/trailerPlayer.js
// Обёртка над Plyr для централизованной настройки трейлерного плеера

const I18N_RU = {
    restart: 'Сначала',
    rewind: 'Назад {seektime} с',
    play: 'Воспроизвести',
    pause: 'Пауза',
    fastForward: 'Вперёд {seektime} с',
    seek: 'Перейти к позиции',
    seekLabel: '{currentTime} из {duration}',
    played: 'Смотрели',
    buffered: 'Буферизовано',
    currentTime: 'Текущее время',
    duration: 'Длительность',
    volume: 'Громкость',
    mute: 'Без звука',
    unmute: 'Со звуком',
    enableCaptions: 'Включить субтитры',
    disableCaptions: 'Выключить субтитры',
    download: 'Скачать',
    enterFullscreen: 'Полный экран',
    exitFullscreen: 'Выйти из полного экрана',
    frameAdvance: 'Следующий кадр',
    frameBack: 'Предыдущий кадр',
    settings: 'Настройки',
    speed: 'Скорость',
    normal: 'Обычная',
    quality: 'Качество',
    loop: 'Зациклить',
    start: 'Начало',
    end: 'Конец',
    all: 'Все',
    reset: 'Сбросить',
    disabled: 'Выключено',
    enabled: 'Включено',
    advertisement: 'Реклама',
    qualityBadge: {
        2160: '4K',
        1440: '2K',
        1080: 'Full HD',
        720: 'HD',
        576: 'SD',
        480: 'SD',
    },
};

const DEFAULT_PLAYER_OPTIONS = {
    ratio: '16:9',
    clickToPlay: true,
    resetOnEnd: true,
    seekTime: 10,
    autoplay: true,
    storage: { enabled: false },
    keyboard: { focused: true, global: false },
    fullscreen: { enabled: false, fallback: false, iosNative: false },
    tooltips: { controls: false, seek: true },
    captions: { active: false, update: false },
    controls: [
        'progress',
        'current-time',
        'duration',
    ],
    settings: [],
    speed: { selected: 1, options: [1] },
    i18n: I18N_RU,
};

const isBrowser = typeof window !== 'undefined';

function isPlyrAvailable() {
    return isBrowser && typeof window.Plyr !== 'undefined';
}

/**
 * Создаёт Plyr для контейнера трейлера.
 * Возвращает экземпляр Plyr или null, если библиотека недоступна.
 */
export function setupTrailerPlayer(videoElement, options = {}) {
    if (!videoElement || !isPlyrAvailable()) {
        return null;
    }

    return new window.Plyr(videoElement, {
        ...DEFAULT_PLAYER_OPTIONS,
        ...options,
    });
}

/**
 * Обновляет источник видео.
 */
export function setTrailerSource(player, { src, type = 'video/mp4', title = 'Трейлер' } = {}) {
    if (!player || !src) return;
    player.source = {
        type: 'video',
        title,
        sources: [
            {
                src,
                type,
            },
        ],
    };
}

/**
 * Завершает работу плеера и очищает слушатели.
 */
export function disposeTrailerPlayer(player) {
    if (player && typeof player.destroy === 'function') {
        player.destroy();
    }
}

export function hasEnhancedTrailerPlayer() {
    return isPlyrAvailable();
}

