// movie_lottery/static/js/utils/polls.js

/**
 * Загружает опросы пользователя по сохранённым токенам создателя.
 *
 * @param {Object} options
 * @param {HTMLButtonElement} [options.myPollsButton] - Кнопка перехода к "Мои опросы".
 * @param {HTMLElement} [options.myPollsBadgeElement] - Элемент бейджа с количеством новых опросов.
 * @returns {Promise<Array>} Список всех найденных опросов.
 */
export async function loadMyPolls({ myPollsButton, myPollsBadgeElement } = {}) {
    const creatorTokens = JSON.parse(localStorage.getItem('pollCreatorTokens') || '{}');
    const tokens = Object.values(creatorTokens).filter(Boolean);
    const uniqueTokens = Array.from(new Set(tokens));

    if (uniqueTokens.length === 0) {
        if (myPollsButton) {
            myPollsButton.style.display = 'none';
        }
        if (myPollsBadgeElement) {
            myPollsBadgeElement.style.display = 'none';
            myPollsBadgeElement.textContent = '';
        }
        return [];
    }

    try {
        const pollsByToken = await Promise.all(
            uniqueTokens.map(async (token) => {
                try {
                    const response = await fetch(`/api/polls/my-polls?creator_token=${encodeURIComponent(token)}`);
                    if (!response.ok) {
                        return [];
                    }
                    const data = await response.json();
                    return Array.isArray(data.polls) ? data.polls : [];
                } catch (error) {
                    console.error('Ошибка загрузки опросов для токена:', token, error);
                    return [];
                }
            })
        );

        const allPolls = pollsByToken.flat();

        if (allPolls.length > 0) {
            if (myPollsButton) {
                myPollsButton.style.display = 'inline-block';
            }

            if (myPollsBadgeElement) {
                const viewedPolls = JSON.parse(localStorage.getItem('viewedPolls') || '{}');
                const newResults = allPolls.filter((poll) => !viewedPolls[poll.poll_id]);

                if (newResults.length > 0) {
                    myPollsBadgeElement.textContent = newResults.length;
                    myPollsBadgeElement.style.display = 'inline-block';
                } else {
                    myPollsBadgeElement.style.display = 'none';
                }
            }
        } else {
            if (myPollsButton) {
                myPollsButton.style.display = 'none';
            }
            if (myPollsBadgeElement) {
                myPollsBadgeElement.style.display = 'none';
                myPollsBadgeElement.textContent = '';
            }
        }

        return allPolls;
    } catch (error) {
        console.error('Ошибка загрузки опросов:', error);
        if (myPollsButton) {
            myPollsButton.style.display = 'none';
        }
        if (myPollsBadgeElement) {
            myPollsBadgeElement.style.display = 'none';
            myPollsBadgeElement.textContent = '';
        }
        return [];
    }
}
