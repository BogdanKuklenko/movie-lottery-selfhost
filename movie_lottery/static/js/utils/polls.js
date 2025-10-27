// movie_lottery/static/js/utils/polls.js

const TOKEN_MAP_KEY = 'pollCreatorTokens';
const TOKEN_LIST_KEY = 'pollCreatorTokenList';

const parseJsonSafe = (value, fallback) => {
    try {
        const parsed = JSON.parse(value);
        return parsed ?? fallback;
    } catch (error) {
        return fallback;
    }
};

const getTokenMap = () => {
    const stored = localStorage.getItem(TOKEN_MAP_KEY);
    const map = parseJsonSafe(stored, {});
    return map && typeof map === 'object' ? map : {};
};

const getTokenList = () => {
    const stored = localStorage.getItem(TOKEN_LIST_KEY);
    const list = parseJsonSafe(stored, []);
    return Array.isArray(list) ? list : [];
};

const updateStoredTokens = (map, list) => {
    localStorage.setItem(TOKEN_MAP_KEY, JSON.stringify(map));
    localStorage.setItem(TOKEN_LIST_KEY, JSON.stringify(list));
};

const extractTokensFromUrl = () => {
    const tokens = [];
    try {
        const searchParams = new URLSearchParams(window.location.search);
        const queryToken = searchParams.get('creator_token');
        if (queryToken) {
            tokens.push(queryToken.trim());
        }

        if (window.location.hash) {
            const hash = window.location.hash.startsWith('#') ? window.location.hash.substring(1) : window.location.hash;
            const hashParams = new URLSearchParams(hash);
            const hashToken = hashParams.get('creator_token');
            if (hashToken) {
                tokens.push(hashToken.trim());
            }
        }
    } catch (error) {
        console.error('Не удалось разобрать токен создателя из URL', error);
    }
    return tokens.filter(Boolean);
};

const collectCreatorTokens = () => {
    const map = getTokenMap();
    const list = getTokenList();
    const existingMapValues = Object.values(map).filter(Boolean);
    const tokensSet = new Set([...existingMapValues, ...list.filter(Boolean)]);

    const urlTokens = extractTokensFromUrl();
    if (urlTokens.length > 0) {
        urlTokens.forEach((token) => {
            if (!token) return;
            const normalizedToken = token.trim();
            if (!normalizedToken) {
                return;
            }
            tokensSet.add(normalizedToken);

            if (!Object.values(map).includes(normalizedToken)) {
                map[normalizedToken] = normalizedToken;
            }

            if (!list.includes(normalizedToken)) {
                list.push(normalizedToken);
            }
        });
        updateStoredTokens(map, list);
    }

    const tokensArray = Array.from(tokensSet);
    if (tokensArray.length > 0) {
        localStorage.setItem(TOKEN_LIST_KEY, JSON.stringify(tokensArray));
    }

    return tokensArray;
};

export function storeCreatorToken({ token, pollId } = {}) {
    if (!token) {
        return;
    }

    const normalizedToken = token.trim();
    if (!normalizedToken) {
        return;
    }

    const map = getTokenMap();
    const list = getTokenList();

    if (pollId) {
        map[pollId] = normalizedToken;
    } else if (!Object.values(map).includes(normalizedToken)) {
        map[normalizedToken] = normalizedToken;
    }

    if (!list.includes(normalizedToken)) {
        list.push(normalizedToken);
    }

    updateStoredTokens(map, list);
}

/**
 * Загружает опросы пользователя по сохранённым токенам создателя.
 *
 * @param {Object} options
 * @param {HTMLButtonElement} [options.myPollsButton] - Кнопка перехода к "Мои опросы".
 * @param {HTMLElement} [options.myPollsBadgeElement] - Элемент бейджа с количеством новых опросов.
 * @returns {Promise<Array>} Список всех найденных опросов.
 */
export async function loadMyPolls({ myPollsButton, myPollsBadgeElement } = {}) {
    const uniqueTokens = collectCreatorTokens();

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
