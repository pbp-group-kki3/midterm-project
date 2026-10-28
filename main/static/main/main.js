// Discover page: open the filter panel, and highlight a chip when its box is ticked
document.addEventListener("DOMContentLoaded", () => {
    // "Filters" button opens the <dialog> (the browser's built-in popup)
    const dialog = document.getElementById("filter-dialog");
    const openButton = document.getElementById("filter-open");
    const quickFilters = document.getElementById("quick-filters");
    if (dialog && openButton) {
        openButton.addEventListener("click", () => {
            if (quickFilters) {
                quickFilters.classList.remove("is-hidden");   // show the quick chips under the search row
            }
            dialog.showModal();
        });
    }

    // Each chip in the panel wraps a hidden checkbox or radio. Keep .is-selected in sync with it
    document.querySelectorAll(".discover-filter-chip input").forEach((input) => {
        input.addEventListener("change", () => {
            // radios: switching one on switches the others in the group off, so update the whole group
            const group = document.querySelectorAll(`input[name="${input.name}"]`);
            group.forEach((other) => {
                other.closest("label").classList.toggle("is-selected", other.checked);
            });
        });
    });

    // Heart / Save button: send the form in the background so the page doesn't reload and jump to the top
    document.querySelectorAll(".js-favorite-form").forEach((form) => {
        form.addEventListener("submit", async (event) => {
            event.preventDefault();                                   // stop the normal page reload
            const button = form.querySelector("button");
            try {
                const response = await fetch(form.action, {
                    method: "POST",
                    body: new FormData(form),                         // includes the csrf token
                    headers: { "X-Requested-With": "XMLHttpRequest" },   // tells the view to answer with JSON
                });
                if (response.redirected || !response.ok) {            // e.g. logged out -> login page
                    window.location.href = response.url;
                    return;
                }
                const data = await response.json();                   // {"saved": true} or {"saved": false}
                showFavorite(button, data.saved);
            } catch (error) {
                form.submit();                                        // network problem: fall back to the normal form
            }
        });
    });

    // Long ingredient lists: show "Show all ingredients" only when the text is really cut off
    document.querySelectorAll(".discover-clamp-toggle").forEach((toggle) => {
        const text = document.getElementById(toggle.dataset.clampTarget);
        if (text && text.scrollHeight > text.clientHeight) {
            toggle.classList.remove("is-hidden");
        }
        toggle.addEventListener("click", () => {
            const open = text.classList.toggle("is-open");
            toggle.textContent = open ? "Show less" : "Show all ingredients";
        });
    });
});

// Switch a heart or Save button between saved and not saved, using the shared classes
function showFavorite(button, saved) {
    button.setAttribute("aria-pressed", saved ? "true" : "false");
    if (button.dataset.favoriteStyle === "icon") {
        button.classList.toggle("is-active", saved);                  // shared: red heart
        button.textContent = saved ? "\u2665" : "\u2661";             // filled or empty heart
        button.setAttribute("aria-label", saved ? "Remove from favorites" : "Save to favorites");
    } else {
        button.classList.toggle("btn-danger-subtle", saved);          // shared light red
        button.classList.toggle("btn-outline", !saved);
        button.textContent = saved ? "\u2665 Saved" : "\u2661 Save";
    }
}
