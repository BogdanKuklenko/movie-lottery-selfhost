import { saveCachedBackground } from './backgroundCache.js';

const DEFAULT_BATCH_SIZE = 4;

function decodeImage(image) {
    if (typeof image.decode === 'function') {
        return image.decode().catch(() => waitForImageLoad(image));
    }
    return waitForImageLoad(image);
}

function waitForImageLoad(image) {
    return new Promise((resolve, reject) => {
        if (image.complete) {
            if (image.naturalWidth !== 0) {
                resolve();
            } else {
                reject(new Error('Image failed to load'));
            }
            return;
        }

        const handleLoad = () => {
            cleanup();
            resolve();
        };

        const handleError = () => {
            cleanup();
            reject(new Error('Image failed to load'));
        };

        const cleanup = () => {
            image.removeEventListener('load', handleLoad);
            image.removeEventListener('error', handleError);
        };

        image.addEventListener('load', handleLoad, { once: true });
        image.addEventListener('error', handleError, { once: true });
    });
}

function scheduleBatch(callback) {
    if (typeof window.requestIdleCallback === 'function') {
        window.requestIdleCallback(callback);
        return;
    }

    window.requestAnimationFrame(() => {
        callback({
            didTimeout: false,
            timeRemaining: () => 0,
        });
    });
}

function createBackgroundElement(rotator, photo) {
    const div = document.createElement('div');
    div.className = 'bg-image';

    div.style.top = `${photo.pos_top}%`;
    div.style.left = `${photo.pos_left}%`;
    div.style.zIndex = photo.z_index;
    div.style.setProperty('--initial-transform', `rotate(${photo.rotation}deg) scale(1.05)`);
    div.style.setProperty('--final-transform', `rotate(${photo.rotation}deg) scale(1)`);

    const image = new Image();
    image.decoding = 'async';
    image.src = photo.poster_url;

    const handleResolved = () => {
        div.style.backgroundImage = `url(${photo.poster_url})`;
        rotator.appendChild(div);
        requestAnimationFrame(() => {
            div.classList.add('is-loaded');
        });
    };

    const handleRejected = () => {
        div.style.backgroundImage = `url(${photo.poster_url})`;
        rotator.appendChild(div);
        requestAnimationFrame(() => {
            div.classList.add('is-loaded');
            div.classList.add('is-failed');
        });
    };

    return decodeImage(image).then(handleResolved).catch(handleRejected);
}

export function loadBackgroundInBatches(rotator, photos, options = {}) {
    if (!rotator || !Array.isArray(photos) || photos.length === 0) {
        return Promise.resolve([]);
    }

    const { batchSize = DEFAULT_BATCH_SIZE, cacheVersion } = options;
    let index = 0;
    const tasks = [];
    let resolveCompletion;
    const completionPromise = new Promise((resolve) => {
        resolveCompletion = resolve;
    });

    rotator.innerHTML = '';

    const finalize = () => {
        Promise.allSettled(tasks).then(() => {
            if (cacheVersion) {
                saveCachedBackground({
                    version: cacheVersion,
                    markup: rotator.innerHTML,
                });
            }
            resolveCompletion();
        });
    };

    const processBatch = (deadline) => {
        let processedInBatch = 0;

        while (index < photos.length && processedInBatch < batchSize) {
            tasks.push(createBackgroundElement(rotator, photos[index]));
            index += 1;
            processedInBatch += 1;

            if (deadline && typeof deadline.timeRemaining === 'function' && deadline.timeRemaining() <= 0) {
                break;
            }
        }

        if (index < photos.length) {
            scheduleBatch(processBatch);
        } else {
            finalize();
        }
    };

    scheduleBatch(processBatch);

    return completionPromise;
}
