const SCROLL_LOCK_CLASS = 'no-scroll';
let scrollPositionX = 0;
let scrollPositionY = 0;
let lockDepth = 0;

const getBody = () => (typeof document !== 'undefined' ? document.body : null);
const getWindow = () => (typeof window !== 'undefined' ? window : null);

const applyLockStyles = (body, offsetX, offsetY) => {
    body.style.position = 'fixed';
    body.style.width = '100%';
    body.style.top = `-${offsetY}px`;
    body.style.left = `-${offsetX}px`;
    body.style.touchAction = 'none';
    body.style.setProperty('--scroll-lock-offset', `-${offsetY}px`);
    body.style.setProperty('--scroll-lock-offset-x', `-${offsetX}px`);
};

const resetLockStyles = (body) => {
    body.style.position = '';
    body.style.width = '';
    body.style.top = '';
    body.style.left = '';
    body.style.touchAction = '';
    body.style.removeProperty('--scroll-lock-offset');
    body.style.removeProperty('--scroll-lock-offset-x');
};

export function lockScroll() {
    const body = getBody();
    if (!body) {
        return;
    }

    if (lockDepth === 0) {
        const currentWindow = getWindow();
        if (currentWindow) {
            scrollPositionY = currentWindow.scrollY || currentWindow.pageYOffset || 0;
            scrollPositionX = currentWindow.scrollX || currentWindow.pageXOffset || 0;
        } else {
            scrollPositionY = 0;
            scrollPositionX = 0;
        }
        applyLockStyles(body, scrollPositionX, scrollPositionY);
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
        currentWindow.scrollTo(scrollPositionX, scrollPositionY);
    }
}
