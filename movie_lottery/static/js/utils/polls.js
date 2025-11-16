// movie_lottery/static/js/utils/polls.js

const ABSOLUTE_URL_REGEX = /^https?:\/\//i;
const VIEWED_POLLS_KEY = 'viewedPolls';

const parseJsonSafe = (value, fallback) => {
    try {
        const parsed = JSON.parse(value);
        return parsed ?? fallback;
    } catch (error) {
        return fallback;
    }
};

const getViewedPolls = () => {
    const stored = localStorage.getItem(VIEWED_POLLS_KEY);
    const parsed = parseJsonSafe(stored, {});
    return parsed && typeof parsed === 'object' ? parsed : {};
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

const toggleMyPollsUi = ({ polls, myPollsButton, myPollsBadgeElement }) => {
    const hasPolls = polls.length > 0;
    if (myPollsButton) {
        myPollsButton.style.display = hasPolls ? 'inline-block' : 'none';
    }

    if (!myPollsBadgeElement) {
        return;
    }

    if (!hasPolls) {
        myPollsBadgeElement.style.display = 'none';
        myPollsBadgeElement.textContent = '';
        return;
    }

    const viewedPolls = getViewedPolls();
    const newResults = polls.filter((poll) => !viewedPolls[poll.poll_id]);

    if (newResults.length > 0) {
        myPollsBadgeElement.textContent = newResults.length;
        myPollsBadgeElement.style.display = 'inline-block';
    } else {
        myPollsBadgeElement.style.display = 'none';
        myPollsBadgeElement.textContent = '';
    }
};

export async function loadMyPolls({ myPollsButton, myPollsBadgeElement } = {}) {
    try {
        const response = await fetch(buildPollApiUrl('/api/polls/my-polls'), {
            credentials: 'include'
        });
        if (!response.ok) {
            throw new Error('Не удалось загрузить опросы');
        }

        const data = await response.json();
        const polls = Array.isArray(data.polls) ? data.polls : [];

        toggleMyPollsUi({ polls, myPollsButton, myPollsBadgeElement });
        return polls;
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
