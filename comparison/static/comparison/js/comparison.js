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
    const feedback = document.getElementById("compare-save-feedback");
    const savedLocation = document.getElementById("compare-save-location");
    const closeButton = dialog?.querySelector(".dialog-close");

    if (!dialog || !form || !submitButton || !cancelButton || !feedback) {
        return;
    }

    let isSaving = false;

    function clearErrors() {
        feedback.replaceChildren();
        feedback.hidden = true;

        form.querySelectorAll('[aria-invalid="true"]').forEach((field) => {
            field.removeAttribute("aria-invalid");
            field.removeAttribute("aria-describedby");
        });
    }

    function showErrors(errors) {
        const labels = {
            name: "Comparison name",
            notes: "Notes",
            selection: "Product selection",
        };

        let firstInvalidField = null;

        Object.entries(errors).forEach(([fieldName, fieldErrors]) => {
            const field = form.elements.namedItem(fieldName);

            fieldErrors.forEach((error) => {
                const paragraph = document.createElement("p");
                const label = labels[fieldName];

                paragraph.textContent = label
                    ? `${label}: ${error.message}`
                    : error.message;

                feedback.append(paragraph);
            });

            if (field && field.type !== "hidden") {
                field.setAttribute("aria-invalid", "true");
                field.setAttribute("aria-describedby", feedback.id);
                firstInvalidField ||= field;
            }
        });

        feedback.hidden = false;
        (firstInvalidField || feedback).focus();
    }

    function setBusy(busy) {
        isSaving = busy;
        submitButton.disabled = busy;
        cancelButton.disabled = busy;

        if (closeButton) {
            closeButton.disabled = busy;
        }

        form.setAttribute("aria-busy", String(busy));
        submitButton.textContent = busy ? "Saving..." : "Save comparison";
    }

    openButton?.addEventListener("click", () => {
        clearErrors();
        dialog.showModal();
        form.elements.namedItem("name")?.focus();
    });

    cancelButton.addEventListener("click", () => {
        dialog.close();
    });

    dialog.addEventListener("cancel", (event) => {
        if (isSaving) {
            event.preventDefault();
        }
    });

    dialog.addEventListener("close", () => {
        if (openButton && !openButton.disabled) {
            openButton.focus();
        } else {
            const title = document.querySelector(".compare-header .page-title");

            if (title) {
                title.setAttribute("tabindex", "-1");
                title.focus();
            }
        }
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        if (isSaving) return;

        clearErrors();
        setBusy(true);

        try {
            const response = await fetch(form.action, {
                method: "POST",
                body: new FormData(form),
                credentials: "same-origin",
                mode: "same-origin",
                headers: {
                    Accept: "application/json",
                    "X-CSRFToken": form.elements.namedItem(
                        "csrfmiddlewaretoken"
                    ).value,
                },
            });

            const contentType = response.headers.get("content-type") || "";

            if (!contentType.includes("application/json")) {
                throw new Error(
                    "The server could not confirm the save. " +
                    "Please reload the page and check its saved status."
                );
            }

            const data = await response.json();

            if (!response.ok || !data.ok) {
                showErrors(
                    data.errors || {
                        __all__: [{
                            message: data.message || "Could not save this comparison.",
                        }],
                    }
                );

                if (response.status === 401 && data.login_url) {
                    const loginLink = document.createElement("a");
                    loginLink.href = data.login_url;
                    loginLink.className = "link";
                    loginLink.textContent = "Log in";
                    feedback.append(loginLink);
                }

                return;
            }

            if (openButton) {
                const icon = document.createElement("span");
                icon.className = "icon icon-check";
                icon.setAttribute("aria-hidden", "true");

                openButton.replaceChildren(
                    document.createTextNode("Saved "),
                    icon
                );
                openButton.disabled = true;
            }

            if (savedLocation) {
                savedLocation.hidden = false;
            }

            dialog.close();

            window.showToast(
                "Saved",
                data.message,
                "success"
            );
        } catch (error) {
            showErrors({
                __all__: [{
                    message: error instanceof TypeError
                        ? "We couldn't confirm the save. " +
                          "Check your connection, then reload to check its status."
                        : error.message,
                }],
            });
        } finally {
            setBusy(false);
        }
    });
});