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
            if (await handleBlockedResponse(response)) {               // change: 401 -> login page, 429 -> "slow down" toast
                return;
            }
            if (response.status >= 500) {
                throw new ServerProblem();                             // change: step 3b. our server broke -> toast below, page stays
            }
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
            if (reportConnectionProblem(error)) {                      // change: step 3b. no internet / server error -> toast, page stays
                return;
            }
            form.submit();                                             // anything else: fall back to the normal reload
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
            if (await handleBlockedResponse(response)) {               // change: too many requests -> toast, the button comes back
                link.classList.remove("is-disabled");
                link.textContent = "Load more products";
                return;
            }
            if (!response.ok) {
                throw response.status >= 500 ? new ServerProblem() : new Error("load more failed");   // change: step 3b
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
            if (reportConnectionProblem(error)) {                      // change: step 3b. keep the cards, give the button back
                link.classList.remove("is-disabled");
                link.textContent = "Load more products";
                return;
            }
            window.location.href = link.href;                          // something went wrong: fall back to the normal reload
        }
    });

    // "Filters" button opens the <dialog> (the browser's built-in popup)
    // change: step 4. Listen on the whole document: HTMX replaces the button and the dialog after a live search,
    // and a listener attached to the old button would be lost
    document.addEventListener("click", (event) => {
        if (!event.target.closest("#filter-open")) {
            return;
        }
        const dialog = document.getElementById("filter-dialog");     // change: looked up on every click (it may be new)
        const quickFilters = document.getElementById("quick-filters");
        if (quickFilters) {
            quickFilters.classList.remove("is-hidden");   // show the quick chips under the search row
        }
        if (dialog) {
            dialog.showModal();
        }
    });

    // Each chip in the panel wraps a hidden checkbox or radio. Keep .is-selected in sync with it
    // change: same idea, one listener on the document for every chip, old or new
    document.addEventListener("change", (event) => {
        const input = event.target.closest(".discover-filter-chip input");
        if (!input) {
            return;
        }
        // radios: switching one on switches the others in the group off, so update the whole group
        // change: look only inside this filter form. Every Compare button also has a hidden input called "grade",
        // and searching the whole page picked those up too, crashed on them (no <label>) and the grade chips stopped working
        const group = input.form.querySelectorAll(`input[name="${input.name}"]`);
        group.forEach((other) => {
            other.closest("label").classList.toggle("is-selected", other.checked);
        });
    });

    // change: step 4. The server can ask for the shared toast in an HTMX answer (HX-Trigger header).
    // htmx fires it as the "spoonfeed:toast" event; we pass it on to showToast from static/js/toast.js
    document.addEventListener("spoonfeed:toast", (event) => {
        const detail = event.detail || {};
        if (typeof window.showToast === "function" && detail.message) {
            window.showToast(detail.title || "Notification", detail.message, detail.type || "info");
        }
    });

    const pendingFavorites = new Set();

    function matchingFavoriteForms(action) {
        return [...document.querySelectorAll(".js-favorite-form")]
            .filter((form) => form.action === action);
    }

    function showFavoriteError(form, message) {
        let feedback = form.querySelector(".product-action-feedback");

        if (!feedback) {
            feedback = document.createElement("p");
            feedback.className =
                "product-action-feedback field-error mt-2";
            feedback.setAttribute("role", "alert");
            form.append(feedback);
        }

        feedback.textContent = message;

        const loginURL = form.closest(
            ".product-detail-content"
        )?.dataset.loginUrl;

        if (loginURL) {
            const link = document.createElement("a");
            link.href = loginURL;
            link.className = "link";
            link.textContent = "Sign in";

            feedback.append(
                document.createTextNode(" "),
                link
            );
        }
    }

    document.addEventListener("submit", async (event) => {
        const form = event.target.closest(".js-favorite-form");

        if (!form) {
            return;
        }

        event.preventDefault();

        const action = form.action;
        const inOverlay = Boolean(
            form.closest("[data-product-overlay]")
        );

        if (pendingFavorites.has(action)) {
            return;
        }

        const body = new FormData(form);

        pendingFavorites.add(action);

        matchingFavoriteForms(action).forEach((matchingForm) => {
            matchingForm.querySelector(
                ".product-action-feedback"
            )?.remove();

            matchingForm.setAttribute("aria-busy", "true");

            const button = matchingForm.querySelector("button");

            if (button) {
                button.disabled = true;
            }
        });

        try {
            const response = await fetch(action, {
                method: "POST",
                body,
                credentials: "same-origin",
                mode: "same-origin",
                headers: {
                    Accept: "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                    "X-CSRFToken": (
                        body.get("csrfmiddlewaretoken") || ""
                    ),
                },
            });

            if (await handleBlockedResponse(response)) {               // change: 401 -> login page, 429 -> "slow down" toast
                return;                                                // ("finally" below still re-enables the heart)
            }

            if (response.redirected || !response.ok) {
                if (!inOverlay) {
                    window.location.href = response.url;
                    return;
                }

                throw new Error(
                    response.status === 403
                        ? "Your session or security token needs refreshing. "
                          + "Reload the page before trying again."
                        : "We couldn't confirm the favorite change."
                );
            }

            const contentType =
                response.headers.get("Content-Type") || "";

            if (!contentType.includes("application/json")) {
                throw new Error(
                    "The server returned an unexpected response."
                );
            }

            const data = await response.json();

            if (typeof data.saved !== "boolean") {
                throw new Error(
                    "The server did not confirm the favorite state."
                );
            }

            matchingFavoriteForms(action).forEach((matchingForm) => {
                const button = matchingForm.querySelector("button");

                if (button) {
                    showFavorite(button, data.saved);
                }
            });

            // change: step 6. the same toast as saving a comparison (Alyssa's comparison.js uses "Saved" + success too)
            if (data.message && typeof window.showToast === "function") {
                window.showToast(data.saved ? "Saved" : "Removed", data.message, data.saved ? "success" : "info");
            }

            document.dispatchEvent(
                new CustomEvent("spoonfeed:favorite-changed", {
                    detail: {
                        action,
                        saved: data.saved,
                    },
                })
            );
        } catch (error) {
            if (!inOverlay) {
                if (reportConnectionProblem(error)) {                  // change: step 3b. no internet -> toast, the heart stays as it was
                    return;
                }
                // Preserve the existing standalone fallback.
                form.submit();
                return;
            }

            matchingFavoriteForms(action).forEach((matchingForm) => {
                showFavoriteError(
                    matchingForm,
                    error.message
                    + " Reopen the product to check its current state "
                    + "before retrying."
                );
            });
        } finally {
            pendingFavorites.delete(action);

            matchingFavoriteForms(action).forEach((matchingForm) => {
                matchingForm.removeAttribute("aria-busy");

                const button = matchingForm.querySelector("button");

                if (button) {
                    button.disabled = false;
                }
            });
        }
    });

    // Long ingredient lists: show "Show all ingredients" only when the text is really cut off
    initProductDetails(document);
});

const productDetailInitializers = new WeakMap();

function initProductDetails(root = document) {
    productDetailInitializers.get(root)?.();

    const cleanups = [];
    const measurements = [];
    let frame = null;

    function measure() {
        frame = null;

        measurements.forEach(({ toggle, text }) => {
            const open = text.classList.contains("is-open");
            const clipped =
                text.scrollHeight > text.clientHeight + 1;

            toggle.classList.toggle(
                "is-hidden",
                !open && !clipped
            );

            toggle.setAttribute(
                "aria-expanded",
                String(open)
            );
        });
    }

    function scheduleMeasure() {
        if (frame === null) {
            frame = requestAnimationFrame(measure);
        }
    }

    const observer = typeof ResizeObserver === "function"
        ? new ResizeObserver(scheduleMeasure)
        : null;

    root.querySelectorAll(".discover-clamp-toggle").forEach(
        (toggle) => {
            const targetID = toggle.dataset.clampTarget;

            if (!targetID) {
                return;
            }

            const text = root.querySelector(
                `#${CSS.escape(targetID)}`
            );

            if (!text) {
                return;
            }

            function toggleIngredients() {
                const open = text.classList.toggle("is-open");

                toggle.textContent = open
                    ? "Show less"
                    : "Show all ingredients";

                toggle.setAttribute(
                    "aria-expanded",
                    String(open)
                );

                scheduleMeasure();
            }

            toggle.addEventListener(
                "click",
                toggleIngredients
            );

            cleanups.push(() => {
                toggle.removeEventListener(
                    "click",
                    toggleIngredients
                );
            });

            measurements.push({ toggle, text });
            observer?.observe(text);
        }
    );

    window.addEventListener("resize", scheduleMeasure);
    scheduleMeasure();

    function cleanup() {
        if (frame !== null) {
            cancelAnimationFrame(frame);
        }

        observer?.disconnect();

        window.removeEventListener(
            "resize",
            scheduleMeasure
        );

        cleanups.forEach((removeListener) => {
            removeListener();
        });

        if (productDetailInitializers.get(root) === cleanup) {
            productDetailInitializers.delete(root);
        }
    }

    productDetailInitializers.set(root, cleanup);

    return cleanup;
}

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

    const track = carousel.querySelector(".discover-carousel-track");

    // change: no more fromLeft, the track itself slides the right way (left or right) on its own
    function show(index) {
        current = (index + slides.length) % slides.length;               // wraps around: after the last comes the first
        carousel.classList.add("is-moving");                             // change: freeze the rounded frame while sliding
        track.style.setProperty("--slide-index", current);              // CSS moves the track to this slide
        slides.forEach((slide, i) => {
            slide.classList.toggle("is-active", i === current);
            slide.inert = i !== current;                                 // can't tab into the hidden slide's buttons
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

    carousel.querySelector(".js-carousel-prev").addEventListener("click", () => show(current - 1));
    carousel.querySelector(".js-carousel-next").addEventListener("click", () => show(current + 1));
    dots.forEach((dot, i) => dot.addEventListener("click", () => show(i)));

    // change: slide finished moving, give the slides their own rounded corners back
    // (only the track's own slide, not e.g. a button inside finishing its hover colour change)
    track.addEventListener("transitionend", (event) => {
        if (event.target === track) {
            carousel.classList.remove("is-moving");
        }
    });

    // change: swipe with a finger on phones. The slide follows your finger, then snaps to the next one
    let startX = null;
    track.addEventListener("touchstart", (event) => {
        startX = event.touches[0].clientX;
        track.classList.add("is-dragging");                              // no delay while dragging
        carousel.classList.add("is-moving");                             // change: fixed frame while dragging too
        paused = true;
    }, { passive: true });
    track.addEventListener("touchmove", (event) => {
        if (startX === null) {
            return;
        }
        const moved = event.touches[0].clientX - startX;                 // how far the finger went (px)
        track.style.transform = `translateX(calc(${-current * 100}% + ${moved}px))`;
    }, { passive: true });
    track.addEventListener("touchend", (event) => {
        if (startX === null) {
            return;
        }
        const moved = event.changedTouches[0].clientX - startX;
        startX = null;
        track.classList.remove("is-dragging");
        track.style.transform = "";                                      // hand control back to the CSS
        paused = false;
        if (Math.abs(moved) > 50) {                                      // a real swipe, not a tap
            show(moved < 0 ? current + 1 : current - 1);
        } else {
            show(current);                                               // change: tiny drag, slide back into place
        }
    });

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
                show(current + 1);
            }
        }, 6000);
    }

    window.addEventListener("resize", measure);
    show(0);                                                             // change: start on slide 1 (also hides slide 2 from the Tab key)
    carousel.classList.remove("is-moving");                             // nothing is moving yet on page load
}


// change: step 2. Handles the two answers from our security decorators (main/decorators.py):
// 401 = not logged in -> go to the login page (it brings you back afterwards)
// 429 = too many requests -> the shared warning toast (static/js/toast.js), the page stays as it is
// Returns true when it handled the response, so the caller stops there
async function handleBlockedResponse(response) {
    if (response.status !== 401 && response.status !== 429) {
        return false;
    }
    let data = {};
    try {
        data = await response.json();                                 // {"message": "...", "login_url": "..."}
    } catch (error) {
        data = {};                                                     // no JSON: use the defaults below
    }
    if (response.status === 401) {
        window.location.href = data.login_url || "/profiles/login/";
        return true;
    }
    if (typeof window.showToast === "function") {
        window.showToast("Slow down", data.message || "Please wait a minute and try again.", "warning");
    }
    return true;
}


// change: step 3b. What happens when OUR side fails (not Open Food Facts, that's step 3a):
// the internet is down, or our Django server crashed / was stopped.
// Before: the page tried to reload and you got Chrome's "No internet" page or Django's error page.
// Now: the page stays as it is, and the shared toast (static/js/toast.js) says what went wrong.

// thrown by our own code when the server answered with a 5xx error
class ServerProblem extends Error {}

// fetch() throws a TypeError only when the request never reached the server (no internet, server stopped)
function isNetworkProblem(error) {
    return error instanceof TypeError;
}

// Shows the right toast and returns true when the error was a connection or server problem
function reportConnectionProblem(error) {
    if (!isNetworkProblem(error) && !(error instanceof ServerProblem)) {
        return false;                                                  // some other bug: let the caller do its usual fallback
    }
    if (typeof window.showToast === "function") {
        if (isNetworkProblem(error)) {
            window.showToast("No connection", "We couldn't reach SpoonFeed. Check your internet and try again.", "error");
        } else {
            window.showToast("Something went wrong", "Our server had a problem. Please try again in a moment.", "error");
        }
    }
    return true;
}

// HTMX (live search, filters, chips, sort) has its own error events
// htmx:sendError = the request never got an answer (no internet / server stopped)
// htmx:responseError = the server answered with an error (401, 429, 500...)
// HTMX doesn't swap error answers in, so the old results stay on screen
document.addEventListener("htmx:sendError", (event) => {
    reportConnectionProblem(new TypeError("htmx send error"));
    showRetry(requestUrl(event));
});

document.addEventListener("htmx:responseError", async (event) => {
    const xhr = event.detail.xhr;
    if (xhr.status === 401 || xhr.status === 429) {
        // same answers as our fetch() calls: reuse the step 2 handler (login page / "Slow down" toast)
        await handleBlockedResponse(new Response(xhr.responseText, { status: xhr.status }));
        return;
    }
    reportConnectionProblem(new ServerProblem());
    if (xhr.status >= 500) {
        showRetry(requestUrl(event));
    }
});

// the address HTMX was asking for, with the search text and filters
function requestUrl(event) {
    const info = event.detail.pathInfo || {};
    return info.finalRequestPath || info.requestPath || window.location.href;
}

// A "Try again" box above the results. Clicking it asks for the same results again
function showRetry(url) {
    const results = document.getElementById("discover-results");
    if (!results || typeof window.htmx === "undefined") {
        return;
    }
    let box = document.getElementById("discover-retry");
    if (!box) {
        box = document.createElement("div");
        box.id = "discover-retry";
        box.className = "alert alert-warning mt-6";
        box.setAttribute("role", "alert");
        box.innerHTML = '<p class="m-0">These results may be out of date because the last update failed.</p>'
            + '<button type="button" class="btn btn-secondary mt-2">Try again</button>';
        results.before(box);                                           // outside #discover-results, so a successful swap doesn't need to remove it
    }
    box.querySelector("button").onclick = async () => {
        box.querySelector("button").disabled = true;
        await window.htmx.ajax("GET", url, { target: "#discover-results", indicator: "#search-indicator" });
        history.replaceState(null, "", url);                           // the address bar matches what is shown again
    };
}

// a successful HTMX answer means we're connected again: the "Try again" box goes away
document.addEventListener("htmx:afterSwap", (event) => {
    if (event.detail.target && event.detail.target.id === "discover-results") {
        document.getElementById("discover-retry")?.remove();
    }
});

