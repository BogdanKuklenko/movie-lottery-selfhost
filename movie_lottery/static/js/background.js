// static/js/background.js

import { loadBackgroundInBatches } from './utils/backgroundLoader.js';

document.addEventListener('DOMContentLoaded', () => {
    const rotator = document.querySelector('.background-rotator');
    if (!rotator) {
        return;
    }

    if (typeof backgroundPhotos !== 'undefined' && Array.isArray(backgroundPhotos)) {
        loadBackgroundInBatches(rotator, backgroundPhotos);
    }
});
