// Discover page: open the filter panel, and highlight a chip when its box is ticked
document.addEventListener("DOMContentLoaded", () => {
    // change: hero carousel (welcome slide + Meal of the Day). Slides by itself, or with the arrows and dots
    setUpCarousel();

    // change: Discover link in the navbar + "Discover More" on the hero = smooth scroll down to "Discover products"
    // (we're already on the Discover page, so no need to load it again)
    document.addEventListener("click", (event) => {
        const link = event.target.closest(".js-scroll-discover, .navbar-link[href='/']");
        const target = document.getElementById("discover");
        if (!link || !target) {
            return;
        }
        event.preventDefault();
        target.scrollIntoView({ behavior: "smooth" });
        history.replaceState(null, "", "#discover");                  // so refreshing keeps you there
    });

    // change: the SpoonFeed logo = back to the main page, from the very top
    // already on the plain main page? just scroll up smoothly instead of reloading
    document.addEventListener("click", (event) => {
        const logo = event.target.closest(".navbar-logo");
        if (!logo || window.location.pathname !== "/" || window.location.search) {
            return;                                                    // other pages, or "/?q=susu": let it load the clean "/" page
        }
        event.preventDefault();
        window.scrollTo({ top: 0, behavior: "smooth" });
        history.replaceState(null, "", "/");                           // drop the #discover from the address
    });

    // change: "+ Compare", "✓ Added" and the tray's x are sent in the background now, so the page doesn't reload.
    // The server answers with the new tray and the new button for every card (same templates as a normal load).
    // We listen on the whole document because the buttons get replaced, and new buttons need to work too
    document.addEventListener("submit", async (event) => {
        const form = event.target.closest(".js-compare-form");
        if (!form) {
            return;                                                    // some other form, leave it alone
        }
        event.preventDefault();

        // every card on the page, so the server can redraw each one's button ("Limit reached" etc.)
        const slots = [...document.querySelectorAll(".js-compare-slot")].map((slot) => ({
            code: slot.dataset.code,
            name: slot.dataset.name,
            grade: slot.dataset.grade,
            style: slot.dataset.style,
        }));
        const body = new FormData(form);                               // includes the csrf token
        body.append("slots", JSON.stringify(slots));

        try {
            const response = await fetch(form.action, {
                method: "POST",
                body: body,
                headers: { "X-Requested-With": "XMLHttpRequest" },
            });
            if (response.redirected || !response.ok) {                  // e.g. logged out -> login page
                window.location.href = response.url;
                return;
            }
            const data = await response.json();                        // {"tray": "<div...>", "buttons": {"8998...": "<form...>"}}
            const holder = document.getElementById("compare-tray-holder");
            if (holder) {
                holder.innerHTML = data.tray;
            }
            document.querySelectorAll(".js-compare-slot").forEach((slot) => {
                if (data.buttons[slot.dataset.code] !== undefined) {
                    slot.innerHTML = data.buttons[slot.dataset.code];
                }
            });
        } catch (error) {
            form.submit();                                             // network problem: fall back to the normal reload
        }
    });

    // change: "Load more products" adds the next 6 cards to the bottom of the grid instead of reloading the page
    document.addEventListener("click", async (event) => {
        const link = event.target.closest(".js-load-more");
        if (!link) {
            return;
        }
        event.preventDefault();
        link.classList.add("is-disabled");                             // shared disabled look while it loads
        link.textContent = "Loading...";
        try {
            const response = await fetch(link.href, { headers: { "X-Requested-With": "XMLHttpRequest" } });
            if (!response.ok) {
                throw new Error("load more failed");
            }
            const data = await response.json();                        // {"cards": "<article...>", "has_more": true, "more_url": "?show=18"}
            document.getElementById("discover-grid").insertAdjacentHTML("beforeend", data.cards);
            history.replaceState(null, "", link.href);                 // the address bar remembers how many are shown (refresh keeps them)
            if (data.has_more) {
                link.href = data.more_url;                             // next click asks for the next 6
                link.classList.remove("is-disabled");
                link.textContent = "Load more products";
            } else {
                document.getElementById("load-more-holder").remove();  // everything is shown: no more button
            }
        } catch (error) {
            window.location.href = link.href;                          // something went wrong: fall back to the normal reload
        }
    });

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
    // change: listens on the whole page now (not on each heart), so hearts on cards added by "Load more" work too
    document.addEventListener("submit", async (event) => {
        const form = event.target.closest(".js-favorite-form");
        if (!form) {
            return;
        }
        event.preventDefault();                                       // stop the normal page reload
        const button = form.querySelector("button");
        try {
            const response = await fetch(form.action, {
                method: "POST",
                body: new FormData(form),                             // includes the csrf token
                headers: { "X-Requested-With": "XMLHttpRequest" },    // tells the view to answer with JSON
            });
            if (response.redirected || !response.ok) {                // e.g. logged out -> login page
                window.location.href = response.url;
                return;
            }
            const data = await response.json();                       // {"saved": true} or {"saved": false}
            showFavorite(button, data.saved);
        } catch (error) {
            form.submit();                                            // network problem: fall back to the normal form
        }
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

// change: the hero carousel. Shows one slide at a time and moves to the next one every 6 seconds
function setUpCarousel() {
    const carousel = document.querySelector(".js-carousel");
    if (!carousel) {
        return;
    }

    // Aryan's Meal of the Day slide is empty when there's no meal today, so throw that slide away
    carousel.querySelectorAll("[data-slide]").forEach((slide) => {
        if (!slide.querySelector("*")) {
            slide.remove();
        }
    });
    const slides = [...carousel.querySelectorAll("[data-slide]")];
    const dots = [...carousel.querySelectorAll(".js-carousel-dot")];
    dots.slice(slides.length).forEach((dot) => dot.remove());           // one dot per slide
    if (slides.length < 2) {
        carousel.classList.add("is-single");                            // CSS hides the arrows and dots
        return;
    }

    let current = 0;
    let paused = false;

    // the arrows and dots sit on the big card, so tell the CSS how tall the card on this slide is
    function measure() {
        const card = slides[current].querySelector("[data-slide-stage], .feature-card");
        if (card) {
            carousel.style.setProperty("--stage-h", card.offsetHeight + "px");
        }
    }

    function show(index, fromLeft) {
        current = (index + slides.length) % slides.length;               // wraps around: after the last comes the first
        slides.forEach((slide, i) => {
            slide.classList.toggle("is-active", i === current);
            slide.classList.toggle("is-from-left", i === current && fromLeft);
        });
        dots.forEach((dot, i) => {
            dot.classList.toggle("is-active", i === current);
            if (i === current) {
                dot.setAttribute("aria-current", "true");
            } else {
                dot.removeAttribute("aria-current");
            }
        });
        measure();
    }

    carousel.querySelector(".js-carousel-prev").addEventListener("click", () => show(current - 1, true));
    carousel.querySelector(".js-carousel-next").addEventListener("click", () => show(current + 1, false));
    dots.forEach((dot, i) => dot.addEventListener("click", () => show(i, i < current)));

    // don't slide away while the mouse is on it, or while someone is using the buttons with the keyboard
    carousel.addEventListener("mouseenter", () => { paused = true; });
    carousel.addEventListener("mouseleave", () => { paused = false; });
    carousel.addEventListener("focusin", () => { paused = true; });
    carousel.addEventListener("focusout", () => { paused = false; });

    // and never while the Meal of the Day recipe is open, they're reading it!
    function recipeOpen() {
        const panel = document.getElementById("recipe-expanded-panel");
        return panel && !panel.classList.contains("hidden");
    }

    // people who turned off animations in their settings don't get the auto slide
    const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!calm) {
        setInterval(() => {
            if (!paused && !recipeOpen() && !document.hidden) {
                show(current + 1, false);
            }
        }, 6000);
    }

    window.addEventListener("resize", measure);
    measure();
}

