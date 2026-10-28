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
});
