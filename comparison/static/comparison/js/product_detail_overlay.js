(() => {
    const dialog = document.getElementById(
        "compare-product-dialog"
    );

    if (
        !dialog
        || typeof dialog.showModal !== "function"
        || dialog.dataset.overlayInitialized === "true"
    ) {
        return;
    }

    const closeButton = document.getElementById(
        "compare-detail-close"
    );
    const scrollArea = document.getElementById(
        "compare-detail-scroll"
    );
    const host = document.getElementById(
        "compare-detail-content"
    );
    const status = document.getElementById(
        "compare-detail-status"
    );
    const errorBox = document.getElementById(
        "compare-detail-error"
    );
    const errorText = document.getElementById(
        "compare-detail-error-text"
    );
    const retryButton = document.getElementById(
        "compare-detail-retry"
    );

    if (
        !closeButton
        || !scrollArea
        || !host
        || !status
        || !errorBox
        || !errorText
        || !retryButton
    ) {
        return;
    }

    dialog.dataset.overlayInitialized = "true";

    let opener = null;
    let currentProduct = null;
    let controller = null;
    let requestVersion = 0;
    let lockState = null;
    let cleanupWidgets = () => {};

    let favoriteVersion = 0;
    const favoriteUpdates = new Map();

    document.addEventListener(
        "spoonfeed:favorite-changed",
        (event) => {
            const detail = event.detail;

            if (
                !detail
                || typeof detail.action !== "string"
                || typeof detail.saved !== "boolean"
            ) {
                return;
            }

            favoriteVersion += 1;

            favoriteUpdates.set(detail.action, {
                version: favoriteVersion,
                saved: detail.saved,
            });
        }
    );

    function clearContent() {
        cleanupWidgets();
        cleanupWidgets = () => {};
        host.replaceChildren();

        dialog.removeAttribute("aria-labelledby");
        dialog.setAttribute("aria-label", "Product details");
    }

    function invalidateRequest() {
        requestVersion += 1;
        controller?.abort();
        controller = null;
    }

    function lockBackground() {
        if (lockState) {
            return;
        }

        lockState = {
            x: window.scrollX,
            y: window.scrollY,
            bodyStyle: document.body.style.cssText,
            htmlStyle: document.documentElement.style.cssText,
        };

        const width = document.body.getBoundingClientRect().width;

        document.body.style.position = "fixed";
        document.body.style.top = `-${lockState.y}px`;
        document.body.style.left = `-${lockState.x}px`;
        document.body.style.width = `${width}px`;
        document.body.style.overflow = "hidden";

        document.documentElement.style.overflow = "hidden";
    }

    function unlockBackground() {
        if (!lockState) {
            return;
        }

        const saved = lockState;
        lockState = null;

        document.body.style.cssText = saved.bodyStyle;
        document.documentElement.style.cssText = saved.htmlStyle;

        window.scrollTo({
            left: saved.x,
            top: saved.y,
            behavior: "instant",
        });

        if (opener?.isConnected) {
            opener.focus({ preventScroll: true });
        }
    }

    function cleanupClosedDialog() {
        invalidateRequest();
        clearContent();

        host.removeAttribute("aria-busy");
        errorBox.hidden = true;
        status.textContent = "";
        status.hidden = true;

        unlockBackground();
    }

    function closeOverlay() {
        invalidateRequest();

        if (dialog.open) {
            dialog.close();
        }

        cleanupClosedDialog();
    }

    async function loadCurrentProduct() {
        if (!currentProduct || !dialog.open) {
            return;
        }

        invalidateRequest();

        const version = requestVersion;
        const requestedProduct = { ...currentProduct };
        const favoritesAtStart = favoriteVersion;
        const activeController = new AbortController();

        controller = activeController;

        clearContent();

        errorBox.hidden = true;
        errorText.textContent = "";
        host.setAttribute("aria-busy", "true");
        scrollArea.scrollTop = 0;

        status.hidden = false;
        status.textContent =
            `Loading details for ${requestedProduct.name}…`;

        let timedOut = false;

        const timeout = window.setTimeout(() => {
            timedOut = true;
            activeController.abort();
        }, 30000);

        try {
            const response = await fetch(
                requestedProduct.url,
                {
                    method: "GET",
                    credentials: "same-origin",
                    mode: "same-origin",
                    cache: "no-store",
                    signal: activeController.signal,
                    headers: {
                        Accept: "application/json",
                        "X-Requested-With": "XMLHttpRequest",
                    },
                }
            );

            const contentType =
                response.headers.get("Content-Type") || "";

            if (
                response.redirected
                || !contentType.includes("application/json")
            ) {
                throw new Error(
                    "The server returned an unexpected response. "
                    + "Please try again."
                );
            }

            const data = await response.json();

            if (!response.ok) {
                throw new Error(
                    data.message
                    || "We couldn't load this product. Please try again."
                );
            }

            if (
                typeof data.html !== "string"
                || String(data.barcode) !== requestedProduct.barcode
            ) {
                throw new Error(
                    "The server returned details for an unexpected product."
                );
            }

            if (
                version !== requestVersion
                || !dialog.open
                || activeController.signal.aborted
            ) {
                return;
            }

            const template = document.createElement("template");
            template.innerHTML = data.html;

            const content = template.content.firstElementChild;

            if (
                !content?.matches(".product-detail-content")
                || content.dataset.productBarcode
                    !== requestedProduct.barcode
                || template.content.querySelector(
                    "script, iframe, .site-header, .site-footer, "
                    + "#compare-tray-holder"
                )
            ) {
                throw new Error(
                    "The product detail response could not be displayed."
                );
            }

            host.replaceChildren(
                template.content.cloneNode(true)
            );

            cleanupWidgets = initProductDetails(host);

            // A favorite POST may have completed while this GET was
            // loading. Apply only updates newer than this request.
            host.querySelectorAll(".js-favorite-form").forEach(
                (form) => {
                    const update = favoriteUpdates.get(form.action);
                    const button = form.querySelector("button");

                    if (
                        button
                        && update
                        && update.version > favoritesAtStart
                    ) {
                        showFavorite(button, update.saved);
                    }
                }
            );

            const heading = host.querySelector(
                '[id^="product-detail-heading-"]'
            );

            if (heading) {
                dialog.removeAttribute("aria-label");
                dialog.setAttribute(
                    "aria-labelledby",
                    heading.id
                );
            } else {
                dialog.setAttribute(
                    "aria-label",
                    data.product_name || "Product details"
                );
            }

            status.textContent = "";
            status.hidden = true;
        } catch (error) {
            if (
                version !== requestVersion
                || !dialog.open
            ) {
                return;
            }

            clearContent();

            status.textContent = "";
            status.hidden = true;

            errorText.textContent = timedOut
                ? "Loading took too long. Please try again."
                : error.message
                    || "We couldn't load this product. Please try again.";

            errorBox.hidden = false;
        } finally {
            window.clearTimeout(timeout);

            if (version === requestVersion) {
                host.removeAttribute("aria-busy");

                if (controller === activeController) {
                    controller = null;
                }
            }
        }
    }

    document.addEventListener("click", (event) => {
        const link = event.target.closest(
            "a.js-product-detail"
        );

        if (
            !link
            || event.defaultPrevented
            || event.button !== 0
            || event.metaKey
            || event.ctrlKey
            || event.shiftKey
            || event.altKey
        ) {
            return;
        }

        const url = new URL(link.href, window.location.href);
        const barcode = link.dataset.productBarcode;

        if (
            url.origin !== window.location.origin
            || !barcode
        ) {
            return;
        }

        event.preventDefault();

        url.searchParams.set("fragment", "1");
        url.searchParams.set("source", "comparison");

        currentProduct = {
            url: url.href,
            barcode,
            name: link.dataset.productName || "this product",
        };

        if (!dialog.open) {
            opener = link;
            lockBackground();

            try {
                dialog.showModal();
            } catch (error) {
                unlockBackground();
                throw error;
            }
        }

        closeButton.focus({ preventScroll: true });
        loadCurrentProduct();
    });

    closeButton.addEventListener(
        "click",
        closeOverlay
    );

    retryButton.addEventListener(
        "click",
        loadCurrentProduct
    );

    dialog.addEventListener("cancel", (event) => {
        event.preventDefault();
        closeOverlay();
    });

    dialog.addEventListener("close", () => {
        // An older queued close event must not clear a reopened dialog.
        if (!dialog.open) {
            cleanupClosedDialog();
        }
    });

    dialog.addEventListener("keydown", (event) => {
        if (event.key !== "Tab") {
            return;
        }

        const focusable = [...dialog.querySelectorAll(
            'button:not([disabled]), '
            + 'a[href], '
            + 'input:not([disabled]):not([type="hidden"]), '
            + 'select:not([disabled]), '
            + 'textarea:not([disabled]), '
            + '[tabindex]:not([tabindex="-1"])'
        )].filter((element) => (
            !element.closest("[hidden], [inert]")
            && element.getClientRects().length > 0
        ));

        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (!first || !last) {
            event.preventDefault();
            closeButton.focus({ preventScroll: true });
            return;
        }

        if (
            event.shiftKey
            && document.activeElement === first
        ) {
            event.preventDefault();
            last.focus({ preventScroll: true });
        } else if (
            !event.shiftKey
            && document.activeElement === last
        ) {
            event.preventDefault();
            first.focus({ preventScroll: true });
        }
    });
})();