const SCROLL_LOCK_CLASS = 'no-scroll';
let scrollPosition = 0;
let lockDepth = 0;

const getBody = () => (typeof document !== 'undefined' ? document.body : null);
const getWindow = () => (typeof window !== 'undefined' ? window : null);

const applyLockStyles = (body, offset) => {
    body.style.position = 'fixed';
    body.style.width = '100%';
    body.style.top = `-${offset}px`;
    body.style.left = '0';
    body.style.touchAction = 'none';
    body.style.setProperty('--scroll-lock-offset', `-${offset}px`);
};

const resetLockStyles = (body) => {
    body.style.position = '';
    body.style.width = '';
    body.style.top = '';
    body.style.left = '';
    body.style.touchAction = '';
    body.style.removeProperty('--scroll-lock-offset');
};

export function lockScroll() {
    const body = getBody();
    if (!body) {
        return;
    }

    if (lockDepth === 0) {
        const currentWindow = getWindow();
        scrollPosition = currentWindow ? (currentWindow.scrollY || currentWindow.pageYOffset || 0) : 0;
        applyLockStyles(body, scrollPosition);
        body.classList.add(SCROLL_LOCK_CLASS);
    }

    lockDepth += 1;
}

export function unlockScroll() {
    if (lockDepth === 0) {
        return;
    }

    lockDepth = Math.max(0, lockDepth - 1);
    if (lockDepth > 0) {
        return;
    }

    const body = getBody();
    if (!body) {
        return;
    }

    resetLockStyles(body);
    body.classList.remove(SCROLL_LOCK_CLASS);

    const currentWindow = getWindow();
    if (currentWindow) {
        currentWindow.scrollTo(0, scrollPosition);
    }
}
