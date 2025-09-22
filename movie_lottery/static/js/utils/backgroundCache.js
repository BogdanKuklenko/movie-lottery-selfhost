const STORAGE_KEY = 'movie_lottery_background_cache';

function getSessionStorage() {
    try {
        if (typeof window === 'undefined' || !window.sessionStorage) {
            return null;
        }
        const { sessionStorage } = window;
        const testKey = `${STORAGE_KEY}_test`;
        sessionStorage.setItem(testKey, '1');
        sessionStorage.removeItem(testKey);
        return sessionStorage;
    } catch (error) {
        return null;
    }
}

function readCache() {
    const storage = getSessionStorage();
    if (!storage) {
        return null;
    }

    try {
        const raw = storage.getItem(STORAGE_KEY);
        if (!raw) {
            return null;
        }
        return JSON.parse(raw);
    } catch (error) {
        return null;
    }
}

function writeCache(payload) {
    const storage = getSessionStorage();
    if (!storage) {
        return;
    }

    try {
        if (payload === null) {
            storage.removeItem(STORAGE_KEY);
            return;
        }

        storage.setItem(STORAGE_KEY, JSON.stringify(payload));
    } catch (error) {
        // Игнорируем ошибки записи (например, переполнение quota)
    }
}

export function loadCachedBackground(version) {
    const cached = readCache();
    if (!cached || !cached.version || cached.version !== version) {
        return null;
    }
    return cached;
}

export function saveCachedBackground(data) {
    if (!data || !data.version) {
        return;
    }

    writeCache({
        ...data,
        version: data.version,
        savedAt: Date.now(),
    });
}

export function clearCachedBackground() {
    writeCache(null);
}
