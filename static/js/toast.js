// One notification queue for Django messages and existing AJAX showToast calls.
(() => {
    const pendingMessages = [];
    const types = {success: 'alert-success', warning: 'alert-warning', error: 'alert-danger', normal: 'alert-info', info: 'alert-info'};
    const titles = {success: 'Success', warning: 'Please check', error: 'Something went wrong', normal: 'Notification', info: 'Notification'};
    let toast;
    let currentMessage = null;
    let toastTimer;
    let toastHideTimer;
    let returnFocus;

    function startTimer() {
        clearTimeout(toastTimer);
        if (!currentMessage || currentMessage.duration <= 0 || toast.matches(':hover, :focus-within')) return;
        toastTimer = setTimeout(hideToast, currentMessage.duration);
    }

    // Display queued messages without replacing a notification still being read.
    function showNextMessage() {
        if (!toast || currentMessage || !pendingMessages.length) return;
        currentMessage = pendingMessages.shift();
        const {title, message, type} = currentMessage;
        returnFocus = document.activeElement;
        toast.classList.remove('alert-success', 'alert-warning', 'alert-danger', 'alert-info');
        toast.classList.add(types[type]);

        const symbol = document.getElementById('toast-symbol');
        symbol.textContent = '';
        if (type === 'success' || type === 'error') {
            symbol.className = type === 'success' ? 'icon icon-check' : 'icon icon-x';
        } else {
            symbol.className = 'toast-letter';
            symbol.textContent = type === 'warning' ? '!' : 'i';
        }

        const content = toast.querySelector('.toast-content');
        content.setAttribute('role', type === 'error' ? 'alert' : 'status');
        content.setAttribute('aria-live', type === 'error' ? 'assertive' : 'polite');
        toast.hidden = false;
        if (typeof toast.showPopover === 'function') toast.showPopover();
        void toast.offsetHeight;
        toast.classList.remove('toast-hidden');
        toast.classList.add('toast-show');
        document.getElementById('toast-title').textContent = title;
        document.getElementById('toast-message').textContent = message;
        startTimer();
    }

    // Dismiss the current toast, restore its focus if needed, then show the next.
    function hideToast() {
        if (!toast || !currentMessage) return;
        clearTimeout(toastTimer);
        clearTimeout(toastHideTimer);
        const hadFocus = toast.contains(document.activeElement);
        toast.classList.remove('toast-show');
        toast.classList.add('toast-hidden');
        toastHideTimer = setTimeout(() => {
            if (typeof toast.hidePopover === 'function' && toast.matches(':popover-open')) toast.hidePopover();
            toast.hidden = true;
            document.getElementById('toast-title').textContent = '';
            document.getElementById('toast-message').textContent = '';
            currentMessage = null;
            if (hadFocus && returnFocus?.isConnected) returnFocus.focus({preventScroll: true});
            showNextMessage();
        }, 200);
    }

    // Preserve Comparison's API and accept the older showToast(message, type) form.
    function showToast(title, message, type = 'normal', duration = 5000) {
        if (message === undefined || (arguments.length === 2 && Object.hasOwn(types, message))) {
            type = message || 'normal';
            message = title;
            title = titles[type] || titles.normal;
        }
        type = Object.hasOwn(types, type) ? type : 'normal';
        pendingMessages.push({title, message, type, duration});
        showNextMessage();
    }

    window.showToast = showToast;
    window.hideToast = hideToast;

    function initializeToast() {
        toast = document.getElementById('toast-component');
        if (!toast) return;
        document.getElementById('toast-close').addEventListener('click', hideToast);
        toast.addEventListener('mouseenter', () => clearTimeout(toastTimer));
        toast.addEventListener('focusin', () => clearTimeout(toastTimer));
        toast.addEventListener('mouseleave', startTimer);
        toast.addEventListener('focusout', startTimer);
        document.querySelectorAll('#toast-messages [data-message]').forEach(message => {
            const type = message.dataset.type;
            pendingMessages.push({
                title: titles[type] || titles.normal,
                message: message.dataset.message,
                type: Object.hasOwn(types, type) ? type : 'normal',
                duration: type === 'success' ? 5000 : 0,
            });
        });
        showNextMessage();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeToast, {once: true});
    } else {
        initializeToast();
    }
})();
