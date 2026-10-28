let toastTimer;
let toastHideTimer;
let toastAfterClose = null;

function hideToast() {
    const toast = document.getElementById("toast-component");

    if (!toast) return;

    clearTimeout(toastTimer);
    clearTimeout(toastHideTimer);

    toast.classList.remove("toast-show");
    toast.classList.add("toast-hidden");

    toastHideTimer = setTimeout(() => {
        if (toast.matches(":popover-open")) {
            toast.hidePopover();
        }

        const afterClose = toastAfterClose;
        toastAfterClose = null;

        if (afterClose) afterClose();
    }, 200);
}

function showToast(title, message, type = "normal", duration = 5000) {
    const toast = document.getElementById("toast-component");
    const toastTitle = document.getElementById("toast-title");
    const toastMessage = document.getElementById("toast-message");
    const toastSymbol = document.getElementById("toast-symbol");

    if (!toast || !toastTitle || !toastMessage || !toastSymbol) return;

    clearTimeout(toastTimer);
    clearTimeout(toastHideTimer);

    toast.classList.remove(
        "alert-success",
        "alert-warning",
        "alert-danger",
        "alert-info"
    );

    const types = {
        success: "alert-success",
        warning: "alert-warning",
        error: "alert-danger",
        normal: "alert-info",
    };

    toast.classList.add(types[type] || types.normal);

    toastSymbol.textContent = "";

    if (type === "success") {
        toastSymbol.className = "icon icon-check";
    } else if (type === "error") {
        toastSymbol.className = "icon icon-x";
    } else {
        toastSymbol.className = "compare-toast-letter";
        toastSymbol.textContent = type === "warning" ? "!" : "i";
    }

    toastTitle.textContent = title;
    toastMessage.textContent = message;

    const content = toast.querySelector(".compare-toast-content");
    content.setAttribute("role", type === "error" ? "alert" : "status");

    if (!toast.matches(":popover-open")) {
        toast.showPopover();
        void toast.offsetHeight;
    }

    toast.classList.remove("toast-hidden");
    toast.classList.add("toast-show");

    if (duration > 0) {
        toastTimer = setTimeout(hideToast, duration);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const toast = document.getElementById("toast-component");
    const closeButton = document.getElementById("toast-close");

    if (!toast || !closeButton) return;

    closeButton.addEventListener("click", hideToast);

    // keep the notification visible while it is being read or focused.
    toast.addEventListener("mouseenter", () => {
        clearTimeout(toastTimer);
    });

    toast.addEventListener("focusin", () => {
        clearTimeout(toastTimer);
    });

    const pendingMessages = Array.from(
        document.querySelectorAll(
            "#compare-toast-messages [data-message]"
        )
    );

    const titles = {
        success: "Success",
        warning: "Please check",
        error: "Something went wrong",
        normal: "Notification",
    };

    function showNextMessage() {
        const next = pendingMessages.shift();

        if (!next) return;

        const type = next.dataset.type;
        const duration = type === "success" ? 5000 : 0;

        toastAfterClose = showNextMessage;

        showToast(
            titles[type] || titles.normal,
            next.dataset.message,
            type,
            duration
        );
    }

    showNextMessage();
});