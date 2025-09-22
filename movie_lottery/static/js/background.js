// static/js/background.js

document.addEventListener('DOMContentLoaded', () => {
    // Эта функция отрисовывает статичный фон на основе данных от сервера
    const renderStaticBackground = (photos) => {
        const rotator = document.querySelector('.background-rotator');
        if (!rotator) return;

        // Очищаем фон от старых изображений
        rotator.innerHTML = '';

        // Проходим по каждому объекту фото и создаем для него div
        photos.forEach(photo => {
            const div = document.createElement('div');
            div.className = 'bg-image';
            
            // Устанавливаем все стили напрямую из данных, полученных от сервера
            div.style.backgroundImage = `url(${photo.poster_url})`;
            div.style.top = `${photo.pos_top}%`;
            div.style.left = `${photo.pos_left}%`;
            div.style.zIndex = photo.z_index;
            div.style.transform = `rotate(${photo.rotation}deg) scale(1)`;
            div.style.opacity = '1'; // Сразу делаем видимым, без анимации падения

            rotator.appendChild(div);
        });
    };

    // Проверяем, передал ли сервер данные для фона в глобальной переменной
    if (typeof backgroundPhotos !== 'undefined' && Array.isArray(backgroundPhotos)) {
        renderStaticBackground(backgroundPhotos);
    }
});