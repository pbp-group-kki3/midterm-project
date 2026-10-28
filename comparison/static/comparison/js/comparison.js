document.addEventListener("DOMContentLoaded", () => {
    const dialog = document.getElementById("compare-remove-dialog");
    const form = document.getElementById("compare-remove-form");
    const productName = document.getElementById(
        "compare-remove-product-name"
    );
    const cancelButton = document.getElementById(
        "compare-remove-cancel"
    );
    const triggers = document.querySelectorAll(
        ".compare-remove-trigger"
    );

    if (!dialog || !form || !productName || !cancelButton) {
        return;
    }

    let activeTrigger = null;

    triggers.forEach((trigger) => {
        trigger.addEventListener("click", () => {
            const removeUrl = trigger.dataset.removeUrl;

            if (!removeUrl || dialog.open) {
                return;
            }

            activeTrigger = trigger;

            productName.textContent =
                trigger.dataset.productName || "this product";

            form.setAttribute("action", removeUrl);

            dialog.showModal();
        });
    });

    cancelButton.addEventListener("click", () => {
        dialog.close();
    });

    dialog.addEventListener("close", () => {
        form.removeAttribute("action");
        productName.textContent = "";

        if (activeTrigger) {
            activeTrigger.focus();
            activeTrigger = null;
        }
    });
});

document.addEventListener("DOMContentLoaded", () => {
    const dialog = document.getElementById("compare-save-dialog");
    const openButton = document.getElementById("compare-save-open");
    const cancelButton = document.getElementById("compare-save-cancel");
    const form = document.getElementById("compare-save-form");
    const submitButton = document.getElementById("compare-save-submit");

    if (!dialog || !cancelButton || !form || !submitButton) {
        return;
    }

    function openSaveDialog() {
        if (!dialog.open) {
            dialog.showModal();
        }

        const invalidField = form.querySelector(
            '[aria-invalid="true"]'
        );
        const nameField = form.querySelector('[name="name"]');
        const focusTarget = invalidField || nameField;

        if (focusTarget) {
            focusTarget.focus();
        }
    }

    if (openButton) {
        openButton.addEventListener("click", openSaveDialog);
    }

    cancelButton.addEventListener("click", () => {
        dialog.close();
    });

    dialog.addEventListener("close", () => {
        if (openButton) {
            openButton.focus();
        }
    });

    form.addEventListener("submit", () => {
        submitButton.disabled = true;
        submitButton.textContent = "Saving...";
    });

    if (dialog.dataset.openOnLoad === "true") {
        openSaveDialog();
    }
});