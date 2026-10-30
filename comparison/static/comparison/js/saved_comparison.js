document.addEventListener("DOMContentLoaded", () => {
    const editForm = document.getElementById("compare-edit-form");
    if (!editForm) return;

    const header = document.getElementById("compare-header");
    const heading = document.getElementById("compare-page-heading");
    const notes = document.getElementById("compare-saved-notes");
    const backLink = document.getElementById("compare-back-to-saved");
    const editOpen = document.getElementById("compare-edit-open");
    const removeOpen = document.getElementById("compare-saved-remove-open");
    const editDialog = document.getElementById("compare-edit-dialog");
    const removeDialog = document.getElementById("compare-saved-remove-dialog");
    const removeForm = document.getElementById("compare-saved-remove-form");
    const editSubmit = document.getElementById("compare-edit-submit");
    const removeSubmit = document.getElementById("compare-saved-remove-submit");
    const editFeedback = document.getElementById("compare-edit-feedback");
    const removeFeedback = document.getElementById("compare-saved-remove-feedback");
    const nameField = editForm.elements.namedItem("edit-name");
    const notesField = editForm.elements.namedItem("edit-notes");

    const recordId = Number(header.dataset.savedId);
    const dialogs = [editDialog, removeDialog];
    const fields = {
        name: [nameField, document.getElementById("compare-edit-name-error")],
        notes: [notesField, document.getElementById("compare-edit-notes-error")],
    };

    let saved = {name: nameField.value, notes: notesField.value};
    let busy = false;
    let controller = null;
    let version = 0;
    let trigger = null;
    let scrollPosition = null;
    let previousOverflow = "";

    function renderSaved() {
        heading.textContent = saved.name;
        notes.textContent = saved.notes;
        notes.hidden = !saved.notes.trim();
        document.title = `${saved.name} | SpoonFeed`;
    }

    function clearErrors() {
        for (const [field, error] of Object.values(fields)) {
            field.classList.remove("is-error");
            field.removeAttribute("aria-invalid");
            field.removeAttribute("aria-describedby");
            error.textContent = "";
            error.hidden = true;
        }

        for (const feedback of [editFeedback, removeFeedback]) {
            feedback.textContent = "";
            feedback.hidden = true;
        }
    }

    function showValidationErrors(errors) {
        const generalErrors = [];
        let firstInvalid = null;

        for (const [name, entries] of Object.entries(errors)) {
            const message = entries.map(entry => entry.message).join(" ");
            const pair = fields[name];

            if (!pair) {
                generalErrors.push(message);
                continue;
            }

            const [field, error] = pair;
            error.textContent = message;
            error.hidden = false;
            field.classList.add("is-error");
            field.setAttribute("aria-invalid", "true");
            field.setAttribute("aria-describedby", error.id);
            firstInvalid ||= field;
        }

        if (generalErrors.length) {
            editFeedback.textContent = generalErrors.join(" ");
            editFeedback.hidden = false;
        }

        if (firstInvalid) firstInvalid.focus();
        else if (!editFeedback.hidden) editFeedback.focus();
    }

    function setBusy(value, form = null) {
        busy = value;
        editOpen.disabled = value;
        removeOpen.disabled = value;

        for (const dialog of dialogs) {
            dialog.querySelectorAll("button, input, textarea").forEach(control => {
                control.disabled = value;
            });
        }

        editForm.setAttribute("aria-busy", String(value));
        removeForm.setAttribute("aria-busy", String(value));
        editSubmit.textContent = value && form === editForm ? "Saving" : "Save changes";
        removeSubmit.textContent = value && form === removeForm ? "Removing" : "Remove";
    }

    function openDialog(dialog, button) {
        if (busy || document.querySelector("dialog[open]")) return;

        version += 1;
        clearErrors();
        nameField.value = saved.name;
        notesField.value = saved.notes;
        trigger = button;
        scrollPosition = {x: window.scrollX, y: window.scrollY};
        previousOverflow = document.body.style.overflow;
        document.body.style.overflow = "hidden";

        dialog.showModal();

        if (dialog === editDialog) nameField.focus();
        else dialog.querySelector("[data-saved-cancel]").focus();
    }

    function restoreAfterClose() {
        if (controller) {
            version += 1;
            controller.abort();
            controller = null;
            setBusy(false);
        }

        document.body.style.overflow = previousOverflow;

        if (scrollPosition) {
            window.scrollTo(scrollPosition.x, scrollPosition.y);
            scrollPosition = null;
        }

        trigger?.focus({preventScroll: true});
        trigger = null;
    }

    editOpen.addEventListener("click", () => openDialog(editDialog, editOpen));
    removeOpen.addEventListener("click", () => openDialog(removeDialog, removeOpen));

    for (const dialog of dialogs) {
        dialog.querySelector("[data-saved-cancel]").addEventListener("click", () => {
            if (!busy) dialog.close();
        });

        dialog.addEventListener("cancel", event => {
            if (busy) event.preventDefault();
        });

        dialog.addEventListener("close", restoreAfterClose);
    }

    async function submit(event, kind) {
        event.preventDefault();

        const form = kind === "edit" ? editForm : removeForm;
        const dialog = kind === "edit" ? editDialog : removeDialog;
        const feedback = kind === "edit" ? editFeedback : removeFeedback;

        if (busy || !dialog.open) return;

        clearErrors();

        // Read form values before disabling controls.
        const body = new FormData(form);
        const csrfToken = form.elements.namedItem("csrfmiddlewaretoken").value;
        const ticket = ++version;
        const activeController = new AbortController();
        controller = activeController;
        const timeout = setTimeout(() => activeController.abort(), 15000);
        let navigating = false;

        setBusy(true, form);

        try {
            const response = await fetch(form.action, {
                method: "POST",
                body,
                credentials: "same-origin",
                mode: "same-origin",
                signal: activeController.signal,
                headers: {
                    Accept: "application/json",
                    "X-CSRFToken": csrfToken,
                },
            });

            const contentType = response.headers.get("content-type") || "";

            if (response.status === 403) {
                throw new Error("Your security token may have expired. Reload this page before trying again.");
            }

            if (response.redirected || !contentType.includes("application/json")) {
                throw new Error("The server could not confirm the change. Check Saved before trying again.");
            }

            const data = await response.json();

            if (ticket !== version || !dialog.open) return;

            if (!response.ok || !data.ok) {
                if (kind === "edit" && data.errors) {
                    setBusy(false);
                    showValidationErrors(data.errors);
                    return;
                }

                throw new Error(data.message || "The change could not be completed. Please try again.");
            }

            if (kind === "edit") {
                const comparison = data.comparison;

                if (
                    comparison?.id !== recordId
                    || typeof comparison.name !== "string"
                    || typeof comparison.notes !== "string"
                ) {
                    throw new Error("The server returned an unexpected comparison. Reload to check its saved values.");
                }

                saved = {name: comparison.name, notes: comparison.notes};
                renderSaved();
                controller = null;
                setBusy(false);
                dialog.close();
                window.showToast("Comparison updated", data.message, "success");
            } else {
                if (
                    data.comparison_id !== recordId
                    || new URL(data.redirect_url, window.location.href).href !== backLink.href
                ) {
                    throw new Error("The server returned an unexpected result. Check Saved before trying again.");
                }

                // Django messages supplies the success toast on the destination.
                navigating = true;
                controller = null;
                window.location.assign(backLink.href);
            }
        } catch (error) {
            if (ticket !== version || !dialog.open) return;

            navigating = false;
            feedback.textContent = error.name === "AbortError"
                ? "The request timed out. Check Saved before retrying; the server may have completed it."
                : error.message;
            feedback.hidden = false;

            window.showToast("Could not complete the change", feedback.textContent, "error");
        } finally {
            clearTimeout(timeout);

            if (ticket === version) {
                controller = null;
                if (!navigating) setBusy(false);
            }
        }
    }

    editForm.addEventListener("submit", event => submit(event, "edit"));
    removeForm.addEventListener("submit", event => submit(event, "remove"));

    window.addEventListener("pagehide", () => {
        version += 1;
        controller?.abort();
    });

    window.addEventListener("pageshow", event => {
        if (event.persisted) window.location.reload();
    });

    renderSaved();
});