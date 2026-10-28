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