(() => {
    if (window.spoonFeedBlogInitialized) return;
    window.spoonFeedBlogInitialized = true;

    let busy = false;
    let confirming = false;
    let dirty = false;

    function notify(message, type = "success") {
        if (typeof window.showToast === "function") {
            window.showToast(
                type === "error" ? "Article action failed" : "Blog",
                message,
                type
            );
        }
    }

    function confirmation(message, trigger) {
        const dialog = document.getElementById("blog-confirm-dialog");
        if (!dialog || confirming || dialog.open) return Promise.resolve(false);

        confirming = true;
        dialog.returnValue = "";
        document.getElementById("blog-confirm-description").textContent = message;

        return new Promise((resolve) => {
            dialog.addEventListener("close", () => {
                confirming = false;
                if (trigger?.isConnected) trigger.focus({preventScroll: true});
                resolve(dialog.returnValue === "confirm");
            }, {once: true});

            dialog.querySelector("[data-blog-confirm-cancel]").onclick = () => dialog.close();
            dialog.querySelector("[data-blog-confirm-accept]").onclick = () => dialog.close("confirm");
            dialog.showModal();
            dialog.querySelector("[data-blog-confirm-cancel]").focus();
        });
    }

    function showError(form, message, errors = {}) {
        const messages = [message];

        for (const [field, entries] of Object.entries(errors)) {
            for (const entry of entries) {
                messages.push(`${field === "__all__" ? "Form" : field}: ${entry.message}`);
            }

            const input = form.elements.namedItem(field);
            if (input instanceof HTMLElement) {
                input.classList.add("is-error");
                input.setAttribute("aria-invalid", "true");
            }
        }

        const feedback = form.querySelector(".blog-form-errors");
        if (feedback) {
            feedback.textContent = messages.join(" ");
            feedback.hidden = false;
        }

        notify(message, "error");
    }

    function updateSaveButtons(action, saved) {
        document.querySelectorAll('.js-blog-form[data-blog-mode="save"]').forEach((form) => {
            const formUrl = new URL(
                form.getAttribute("action") || window.location.href,
                window.location.href
            ).href;

            if (formUrl !== action) return;

            const button = form.querySelector("[data-blog-save-button]");
            if (!button) return;

            button.classList.toggle("btn-danger-subtle", saved);
            button.classList.toggle("btn-outline", !saved);
            button.setAttribute("aria-pressed", String(saved));
            button.textContent = saved ? "♥ Saved" : "♡ Save";
            form.elements.namedItem("saved").value = saved ? "0" : "1";

        });
    }

    async function refreshSavedCollection() {
        const response = await fetch(window.location.href, {
            headers: {"X-Blog-Saved-Fragment": "1"},
            credentials: "same-origin",
            mode: "same-origin",
            cache: "no-store",
        });

        if (!response.ok || response.redirected) {
            throw new Error("The article was removed, but the Saved list could not refresh. Reload the page.");
        }

        const documentFragment = new DOMParser().parseFromString(await response.text(), "text/html");
        const incoming = documentFragment.querySelector(".profile-saved-collection");
        const current = document.querySelector(".profile-saved-collection");

        if (!incoming || !current) {
            throw new Error("The article was removed, but the Saved list could not refresh. Reload the page.");
        }

        current.replaceWith(incoming);
        document.querySelector(".profile-saved-filters a.is-selected")?.focus({preventScroll: true});
    }

    async function submitForm(form) {
        const body = new FormData(form);
        // Read the HTML attribute because an input named "action" shadows form.action.
        const actionUrl = new URL(
            form.getAttribute("action") || window.location.href,
            window.location.href
        ).href;
        const controls = [...document.querySelectorAll(".js-blog-form button[type='submit']")];
        const previousStates = controls.map((button) => [button, button.disabled]);

        busy = true;
        controls.forEach((button) => { button.disabled = true; });
        form.setAttribute("aria-busy", "true");

        const feedback = form.querySelector(".blog-form-errors");
        if (feedback) {
            feedback.hidden = true;
            feedback.textContent = "";
        }

        form.querySelectorAll(".is-error").forEach((input) => {
            input.classList.remove("is-error");
            input.removeAttribute("aria-invalid");
        });

        try {
                        const response = await fetch(actionUrl, {
                method: "POST",
                body,
                headers: {"X-Requested-With": "XMLHttpRequest"},
                credentials: "same-origin",
                mode: "same-origin",
            });

            if (response.status === 403) {
                throw new Error("This action was not permitted or failed its security check. Reload the page and try again.");
            }

            if (response.redirected || !response.headers.get("content-type")?.includes("application/json")) {
                throw new Error("The server returned an unexpected response. Reload the page and check the action's result.");
            }

            const data = await response.json();

            if (!response.ok || !data.ok) {
                showError(form, data.message || "The action could not be completed.", data.errors);

                if (data.login_url && feedback) {
                    const link = document.createElement("a");
                    link.href = data.login_url;
                    link.className = "link";
                    link.textContent = "Log in";
                    feedback.append(document.createTextNode(" "), link);
                }

                return;
            }

            if (data.redirect_url) {
                dirty = false;
                window.location.assign(data.redirect_url);
                return;
            }

            if (form.dataset.blogMode === "save") {
                updateSaveButtons(actionUrl, data.saved);
            }

            if (data.comments_html) {
                document.getElementById("blog-comments").innerHTML = data.comments_html;
                const heading = document.getElementById("blog-comments-title");
                heading?.setAttribute("tabindex", "-1");
                heading?.focus({preventScroll: true});
            }

            if (form.dataset.blogMode === "profile-remove") {
                await refreshSavedCollection();
            }

            notify(data.message || "Action completed.");
        } catch (error) {
            showError(form, error.message || "The request failed. Check the result before trying again.");
        } finally {
            busy = false;
            form.removeAttribute("aria-busy");
            previousStates.forEach(([button, disabled]) => {
                if (button.isConnected) button.disabled = disabled;
            });
        }
    }

    document.addEventListener("submit", async (event) => {
        const form = event.target;
        if (!(form instanceof HTMLFormElement) || !form.matches(".js-blog-form")) return;

        event.preventDefault();
        if (busy || confirming) return;

        if (form.dataset.blogConfirm) {
            const accepted = await confirmation(form.dataset.blogConfirm, event.submitter);
            if (!accepted) return;
        }

        await submitForm(form);
    });

    document.addEventListener("click", async (event) => {
        const reply = event.target.closest("[data-blog-reply]");
        if (reply) {
            const form = document.getElementById(reply.dataset.blogReply);
            if (!form) return;

            form.hidden = !form.hidden;
            reply.setAttribute("aria-expanded", String(!form.hidden));
            if (!form.hidden) form.querySelector("textarea")?.focus();
        }

        const exit = event.target.closest("[data-blog-exit]");
        if (!exit || !dirty || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;

        event.preventDefault();
        const accepted = await confirmation("Discard your unsaved article changes?", exit);

        if (accepted) {
            dirty = false;
            window.location.assign(exit.href);
        }
    });

    document.addEventListener("input", (event) => {
        if (event.target.closest("[data-blog-editor]")) dirty = true;
    });

    document.addEventListener("change", (event) => {
        if (event.target.closest("[data-blog-editor]")) dirty = true;

        if (event.target.id === "cover_image_input") {
            const label = document.querySelector("[data-blog-image-name]");
            if (label) label.textContent = event.target.files[0]?.name || "No image selected";
        }
    });

    window.addEventListener("beforeunload", (event) => {
        if (!dirty) return;
        event.preventDefault();
        event.returnValue = "";
    });
})();