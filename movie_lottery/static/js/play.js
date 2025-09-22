// static/js/play.js
document.addEventListener('DOMContentLoaded', () => {
    const drawButton = document.getElementById('draw-button');
    const preDrawDiv = document.getElementById('pre-draw');
    const resultDiv = document.getElementById('result-display');
    const rouletteContainer = document.querySelector('.roulette-container');
    const rouletteDiv = document.querySelector('.roulette');

    // Сразу блокируем кнопку, пока картинки не загрузятся
    drawButton.disabled = true;
    drawButton.textContent = 'Загрузка...';

    // Создаем достаточное количество копий для плавной прокрутки
    const copies = 5;
    const totalSlots = lotteryData.length * copies;
    let finalMovies = [];
    for (let i = 0; i < totalSlots; i++) {
        finalMovies.push(lotteryData[i % lotteryData.length]);
    }

    const imageLoadPromises = [];

    finalMovies.forEach(movie => {
        const img = document.createElement('img');
        img.src = movie.poster || 'https://via.placeholder.com/100x150.png?text=No+Image';
        rouletteDiv.appendChild(img);

        const promise = new Promise((resolve, reject) => {
            img.onload = resolve;
            img.onerror = resolve; // Считаем ошибку загрузки тоже "завершением"
        });
        imageLoadPromises.push(promise);
    });

    // Ждем, пока ВСЕ картинки загрузятся
    Promise.all(imageLoadPromises).then(() => {
        drawButton.disabled = false;
        drawButton.textContent = 'Узнать свою судьбу!';
    });

    drawButton.addEventListener('click', async () => {
        drawButton.disabled = true;
        drawButton.textContent = 'Крутим барабан...';

        try {
            const response = await fetch(drawUrl, { method: 'POST' });
            if (!response.ok) throw new Error('Не удалось провести розыгрыш');

            const winner = await response.json();
            
            const winnerIndex = lotteryData.findIndex(m => m.name === winner.name);

            // Выбираем случайный "победный" слот из последних копий, чтобы барабан прокрутился достаточно далеко
            const winningCopyIndex = copies - 2;
            const targetElementIndex = (lotteryData.length * winningCopyIndex) + winnerIndex;
            const targetElement = rouletteDiv.children[targetElementIndex];

            // Рассчитываем финальную позицию для остановки
            const targetPosition = targetElement.offsetLeft + (targetElement.offsetWidth / 2);
            const centerPosition = rouletteContainer.offsetWidth / 2;
            let finalPosition = targetPosition - centerPosition;
            
            // Добавляем случайное смещение для разнообразия остановки
            finalPosition += Math.random() * (targetElement.offsetWidth * 0.4) - (targetElement.offsetWidth * 0.2);


            // Запускаем анимацию прокрутки
            anime({
                targets: rouletteContainer,
                scrollLeft: finalPosition,
                duration: 6000, // --- ИЗМЕНЕНИЕ: Уменьшили общую длительность ---
                easing: 'easeOutCubic', // --- ИЗМЕНЕНИЕ: Сделали остановку чуть резче ---

                update: function(anim) {
                    if (anim.progress > 90) { // Проявляем победителя чуть раньше
                         if (!targetElement.classList.contains('winner')) {
                             targetElement.classList.add('winner');
                        }
                    }
                },

                complete: function() {
                    // Показываем результат
                    preDrawDiv.style.transition = 'opacity 0.5s ease-out';
                    preDrawDiv.style.opacity = '0';
                    document.body.classList.add('no-scroll');

                    // --- ИЗМЕНЕНИЕ: Уменьшили задержку перед показом результата ---
                    setTimeout(() => {
                        preDrawDiv.style.display = 'none';
                        document.getElementById('result-poster').src = winner.poster || 'https://via.placeholder.com/200x300.png?text=No+Image';
                        document.getElementById('result-name').textContent = winner.name;
                        document.getElementById('result-year').textContent = winner.year;
                        resultDiv.style.display = 'flex';
                    }, 250);
                }
            });

        } catch (error) {
            console.error(error);
            showToast(error.message, 'error');
            drawButton.disabled = false;
            drawButton.textContent = 'Узнать свою судьбу!';
        }
    });
});