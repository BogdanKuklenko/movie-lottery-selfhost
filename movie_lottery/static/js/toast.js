// static/js/toast.js
(function () {
    const TOAST_DURATION = 3000;

    const ensureContainer = () => {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
        return container;
    };

    window.showToast = function showToast(message, type = 'info', options = {}) {
        const container = ensureContainer();
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        container.appendChild(toast);

        const duration = options.duration && Number.isFinite(options.duration)
            ? Math.max(1000, options.duration)
            : TOAST_DURATION;

        requestAnimationFrame(() => {
            toast.classList.add('toast-visible');
        });

        setTimeout(() => {
            toast.classList.remove('toast-visible');
            toast.classList.add('toast-hide');
            toast.addEventListener('transitionend', () => {
                toast.remove();
                if (!container.children.length) {
                    container.remove();
                }
            }, { once: true });
        }, duration);
    };
})();
