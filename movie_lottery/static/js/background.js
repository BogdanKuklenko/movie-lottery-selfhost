// static/js/background.js

import { loadBackgroundInBatches } from './utils/backgroundLoader.js';
import { clearCachedBackground, loadCachedBackground } from './utils/backgroundCache.js';

function computeBackgroundVersion(photos) {
    if (!Array.isArray(photos) || photos.length === 0) {
        return 'empty';
    }

    const hashSource = photos.map((photo) => [
        photo.poster_url,
        photo.pos_top,
        photo.pos_left,
        photo.rotation,
        photo.z_index,
    ]);

    const serialized = JSON.stringify(hashSource);
    let hash = 0;

    for (let index = 0; index < serialized.length; index += 1) {
        hash = (hash * 31 + serialized.charCodeAt(index)) >>> 0;
    }

    return `${photos.length}:${hash}`;
}

document.addEventListener('DOMContentLoaded', () => {
    const rotator = document.querySelector('.background-rotator');
    if (!rotator) {
        return;
    }

    if (typeof backgroundPhotos === 'undefined' || !Array.isArray(backgroundPhotos)) {
        return;
    }

    const cacheVersion = computeBackgroundVersion(backgroundPhotos);
    const cachedBackground = loadCachedBackground(cacheVersion);

    if (cachedBackground && cachedBackground.markup) {
        rotator.innerHTML = cachedBackground.markup;
        requestAnimationFrame(() => {
            rotator.querySelectorAll('.bg-image').forEach((element) => {
                element.classList.add('is-loaded');
            });
        });
        return;
    }

    clearCachedBackground();

    loadBackgroundInBatches(rotator, backgroundPhotos, {
        cacheVersion,
    });
});
