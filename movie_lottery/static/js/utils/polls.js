// movie_lottery/static/js/utils/polls.js

const TOKEN_MAP_KEY = 'pollCreatorTokens';
const TOKEN_LIST_KEY = 'pollCreatorTokenList';
const SECRET_HEADER = 'X-Poll-Secret';
const ABSOLUTE_URL_REGEX = /^https?:\/\//i;

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

const getPollCreatorSecret = () => {
    try {
        return window.appConfig?.pollCreatorSecret || null;
    } catch (error) {
        return null;
    }
};

export const getPollApiBaseUrl = () => {
    try {
        const base = window.appConfig?.pollApiBaseUrl || '';
        return base ? base.replace(/\/+$/, '') : '';
    } catch (error) {
        return '';
    }
};

export const buildPollApiUrl = (path = '') => {
    const normalizedPath = path || '';
    if (!normalizedPath) {
        return getPollApiBaseUrl() || '';
    }

    if (ABSOLUTE_URL_REGEX.test(normalizedPath)) {
        return normalizedPath;
    }

    const baseUrl = getPollApiBaseUrl();
    if (!baseUrl) {
        return normalizedPath;
    }

    if (normalizedPath.startsWith('/')) {
        return `${baseUrl}${normalizedPath}`;
    }

    return `${baseUrl}/${normalizedPath}`;
};

const ensureTokenStoredLocally = ({ token, pollId, map, list, persist = true } = {}) => {
    const normalizedToken = (token || '').trim();
    if (!normalizedToken) {
        return { normalizedToken: null, map, list, changed: false };
    }

    const workingMap = map || getTokenMap();
    const workingList = list || getTokenList();
    let changed = false;

    if (pollId) {
        if (workingMap[pollId] !== normalizedToken) {
            workingMap[pollId] = normalizedToken;
            changed = true;
        }
    } else {
        const mapValues = Object.values(workingMap);
        if (!mapValues.includes(normalizedToken)) {
            workingMap[normalizedToken] = normalizedToken;
            changed = true;
        }
    }

    if (!workingList.includes(normalizedToken)) {
        workingList.push(normalizedToken);
        changed = true;
    }

    if (changed && persist) {
        updateStoredTokens(workingMap, workingList);
    }

    return { normalizedToken, map: workingMap, list: workingList, changed };
};

const getStoredTokenByPollId = (pollId) => {
    if (!pollId) {
        return null;
    }
    const map = getTokenMap();
    const token = map[pollId];
    return typeof token === 'string' && token.trim() ? token.trim() : null;
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
    const baseTokens = [...Object.values(map).filter(Boolean), ...list.filter(Boolean)];
    const tokensSet = new Set(baseTokens);

    const urlTokens = extractTokensFromUrl();
    urlTokens.forEach((token) => {
        const { normalizedToken } = ensureTokenStoredLocally({ token, map, list });
        if (normalizedToken) {
            tokensSet.add(normalizedToken);
        }
    });

    return Array.from(tokensSet);
};

const registerCreatorTokenOnServer = async (token) => {
    const secret = getPollCreatorSecret();
    if (!secret) {
        return;
    }

    try {
        const response = await fetch(buildPollApiUrl('/api/polls/creator-tokens'), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                [SECRET_HEADER]: secret,
            },
            body: JSON.stringify({ creator_token: token, secret }),
        });

        if (!response.ok) {
            const payload = await response.json().catch(() => ({}));
            const message = payload?.error || 'Не удалось синхронизировать токен организатора.';
            throw new Error(message);
        }
    } catch (error) {
        console.warn('Не удалось сохранить токен организатора на сервере:', error);
    }
};

const fetchCreatorTokensFromServer = async () => {
    const secret = getPollCreatorSecret();
    if (!secret) {
        return [];
    }

    const response = await fetch(buildPollApiUrl('/api/polls/creator-tokens'), {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
            [SECRET_HEADER]: secret,
        },
        body: JSON.stringify({ secret }),
    });

    let payload = null;
    try {
        payload = await response.json();
    } catch (error) {
        payload = null;
    }

    if (!response.ok) {
        const message = (payload && payload.error) || 'Не удалось получить токены организатора.';
        throw new Error(message);
    }

    const tokens = Array.isArray(payload?.tokens) ? payload.tokens : [];
    return tokens
        .map((entry) => {
            if (typeof entry === 'string') {
                return entry.trim();
            }
            if (entry && typeof entry === 'object') {
                return (entry.creator_token || '').trim();
            }
            return '';
        })
        .filter(Boolean);
};

const cacheCreatorTokens = (tokens) => {
    if (!Array.isArray(tokens) || tokens.length === 0) {
        return;
    }

    const map = getTokenMap();
    const list = getTokenList();
    let changed = false;

    tokens.forEach((token) => {
        const result = ensureTokenStoredLocally({ token, map, list, persist: false });
        if (result.changed) {
            changed = true;
        }
    });

    if (changed) {
        updateStoredTokens(map, list);
    }
};

export async function syncCreatorTokensFromUrl() {
    const tokens = extractTokensFromUrl();
    if (tokens.length === 0) {
        return;
    }

    const map = getTokenMap();
    const list = getTokenList();
    const syncTasks = [];

    tokens.forEach((token) => {
        const { normalizedToken } = ensureTokenStoredLocally({ token, map, list });
        if (normalizedToken) {
            syncTasks.push(registerCreatorTokenOnServer(normalizedToken));
        }
    });

    await Promise.all(syncTasks);
}

export async function storeCreatorToken({ token, pollId } = {}) {
    const { normalizedToken } = ensureTokenStoredLocally({ token, pollId });
    if (!normalizedToken) {
        return;
    }

    await registerCreatorTokenOnServer(normalizedToken);
}

export function getStoredCreatorToken(pollId) {
    return getStoredTokenByPollId(pollId);
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
    const localTokens = collectCreatorTokens();
    let remoteTokens = [];

    try {
        remoteTokens = await fetchCreatorTokensFromServer();
        cacheCreatorTokens(remoteTokens);
    } catch (error) {
        console.warn('Используем локальный кеш токенов организатора:', error);
    }

    const uniqueTokens = Array.from(new Set([...localTokens, ...remoteTokens]));

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
                    const response = await fetch(buildPollApiUrl(`/api/polls/my-polls?creator_token=${encodeURIComponent(token)}`));
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
