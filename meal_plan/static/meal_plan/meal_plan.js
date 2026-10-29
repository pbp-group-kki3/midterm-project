(function () {
    'use strict';

    const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const openSelects = new Set();

    function closeAllSelects(except) {
        openSelects.forEach(function (control) {
            if (control !== except) {
                control.close(false);
            }
        });
    }

    function enhanceSelect(wrapper) {
        const select = wrapper.querySelector('select');
        if (!select || wrapper.dataset.enhanced === 'true') {
            return;
        }
        wrapper.dataset.enhanced = 'true';

        const label = select.id ? document.querySelector('label[for="' + select.id + '"]') : null;
        const button = document.createElement('button');
        const value = document.createElement('span');
        const arrow = document.createElement('span');
        const menu = document.createElement('div');
        const backdrop = document.createElement('div');
        const items = [];
        let activeIndex = -1;
        let typed = '';
        let typedTimer = null;

        button.type = 'button';
        button.className = 'input mealplan-select-button' + (select.classList.contains('is-error') ? ' is-error' : '');
        button.id = select.id + '-button';
        button.setAttribute('role', 'combobox');
        button.setAttribute('aria-haspopup', 'listbox');
        button.setAttribute('aria-expanded', 'false');
        value.className = 'mealplan-select-value';
        arrow.className = 'mealplan-select-arrow';
        arrow.setAttribute('aria-hidden', 'true');
        arrow.textContent = '▾';
        button.append(value, arrow);

        menu.className = 'mealplan-select-menu';
        menu.id = select.id + '-menu';
        menu.setAttribute('role', 'listbox');
        menu.hidden = true;
        button.setAttribute('aria-controls', menu.id);

        if (label) {
            label.id = label.id || select.id + '-label';
            label.htmlFor = button.id;
            menu.setAttribute('aria-labelledby', label.id);
            button.setAttribute('aria-labelledby', label.id + ' ' + button.id);
        }

        if (wrapper.dataset.sheetTitle) {
            const head = document.createElement('div');
            const title = document.createElement('p');
            const text = document.createElement('p');
            head.className = 'mealplan-select-sheet-head';
            title.className = 'type-h3';
            title.textContent = wrapper.dataset.sheetTitle;
            text.className = 'type-body-sm text-secondary';
            text.textContent = wrapper.dataset.sheetText || '';
            head.append(title, text);
            menu.append(head);
        }

        Array.from(select.options).forEach(function (option, index) {
            const item = document.createElement('div');
            const radio = document.createElement('span');
            const text = document.createElement('span');
            const name = document.createElement('span');
            const check = document.createElement('span');

            item.className = 'mealplan-select-option';
            item.id = select.id + '-option-' + index;
            item.setAttribute('role', 'option');
            radio.className = 'mealplan-select-radio';
            radio.setAttribute('aria-hidden', 'true');
            text.className = 'mealplan-select-label';
            name.textContent = option.textContent.trim();
            text.append(name);
            if (option.dataset.helper) {
                const helper = document.createElement('span');
                helper.className = 'mealplan-select-helper';
                helper.textContent = option.dataset.helper;
                text.append(helper);
            }
            check.className = 'mealplan-select-check';
            check.setAttribute('aria-hidden', 'true');
            check.textContent = '✓';
            item.append(radio, text, check);

            item.addEventListener('click', function () {
                choose(index);
            });
            item.addEventListener('mousemove', function () {
                setActive(index);
            });
            items.push(item);
            menu.append(item);
        });

        const foot = document.createElement('div');
        const done = document.createElement('button');
        foot.className = 'mealplan-select-sheet-foot';
        done.type = 'button';
        done.className = 'btn btn-primary btn-block';
        done.textContent = 'Done';
        done.addEventListener('click', function () {
            close(true);
        });
        foot.append(done);
        menu.append(foot);

        backdrop.className = 'mealplan-select-backdrop';
        backdrop.hidden = true;
        backdrop.addEventListener('click', function () {
            close(true);
        });

        select.hidden = true;
        select.tabIndex = -1;
        select.setAttribute('aria-hidden', 'true');
        wrapper.append(button, menu, backdrop);

        function sync() {
            const selected = select.selectedIndex < 0 ? 0 : select.selectedIndex;
            value.textContent = select.options[selected] ? select.options[selected].textContent.trim() : '';
            button.classList.toggle('is-placeholder', selected === 0);
            items.forEach(function (item, index) {
                item.setAttribute('aria-selected', index === selected ? 'true' : 'false');
            });
        }

        function setActive(index) {
            activeIndex = Math.max(0, Math.min(index, items.length - 1));
            items.forEach(function (item, itemIndex) {
                item.classList.toggle('is-active', itemIndex === activeIndex);
            });
            button.setAttribute('aria-activedescendant', items[activeIndex].id);
            const item = items[activeIndex];
            if (item.offsetTop < menu.scrollTop) {
                menu.scrollTop = item.offsetTop;
            } else if (item.offsetTop + item.offsetHeight > menu.scrollTop + menu.clientHeight) {
                menu.scrollTop = item.offsetTop + item.offsetHeight - menu.clientHeight;
            }
        }

        function open() {
            closeAllSelects(control);
            menu.hidden = false;
            backdrop.hidden = false;
            button.setAttribute('aria-expanded', 'true');
            setActive(select.selectedIndex < 0 ? 0 : select.selectedIndex);
            openSelects.add(control);
        }

        function close(returnFocus) {
            menu.hidden = true;
            backdrop.hidden = true;
            button.setAttribute('aria-expanded', 'false');
            button.removeAttribute('aria-activedescendant');
            items.forEach(function (item) {
                item.classList.remove('is-active');
            });
            openSelects.delete(control);
            if (returnFocus) {
                button.focus();
            }
        }

        function choose(index) {
            if (select.selectedIndex !== index) {
                select.selectedIndex = index;
                select.dispatchEvent(new Event('change', { bubbles: true }));
            }
            sync();
            close(true);
        }

        function isOpen() {
            return !menu.hidden;
        }

        function jumpTo(character) {
            clearTimeout(typedTimer);
            typed += character.toLowerCase();
            typedTimer = setTimeout(function () {
                typed = '';
            }, 600);
            const start = isOpen() ? activeIndex + 1 : select.selectedIndex + 1;
            const order = items.map(function (_, index) {
                return (start + index) % items.length;
            });
            const match = order.find(function (index) {
                return select.options[index].textContent.trim().toLowerCase().startsWith(typed);
            });
            if (match === undefined) {
                return;
            }
            if (isOpen()) {
                setActive(match);
            } else {
                select.selectedIndex = match;
                select.dispatchEvent(new Event('change', { bubbles: true }));
                sync();
            }
        }

        button.addEventListener('click', function () {
            if (isOpen()) {
                close(false);
            } else {
                open();
            }
        });

        button.addEventListener('keydown', function (event) {
            const key = event.key;
            if (!isOpen()) {
                if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(key)) {
                    event.preventDefault();
                    open();
                } else if (key.length === 1 && /\S/.test(key)) {
                    jumpTo(key);
                }
                return;
            }
            if (key === 'ArrowDown') {
                event.preventDefault();
                setActive(activeIndex + 1);
            } else if (key === 'ArrowUp') {
                event.preventDefault();
                setActive(activeIndex - 1);
            } else if (key === 'Home') {
                event.preventDefault();
                setActive(0);
            } else if (key === 'End') {
                event.preventDefault();
                setActive(items.length - 1);
            } else if (key === 'Enter' || key === ' ') {
                event.preventDefault();
                choose(activeIndex);
            } else if (key === 'Escape') {
                event.preventDefault();
                close(true);
            } else if (key === 'Tab') {
                choose(activeIndex);
            } else if (key.length === 1 && /\S/.test(key)) {
                jumpTo(key);
            }
        });

        select.addEventListener('change', sync);
        const form = select.form;
        if (form) {
            form.addEventListener('reset', function () {
                setTimeout(sync, 0);
            });
        }

        const control = { close: close, wrapper: wrapper };
        sync();
    }

    document.addEventListener('click', function (event) {
        openSelects.forEach(function (control) {
            if (!control.wrapper.contains(event.target)) {
                control.close(false);
            }
        });
    });

    document.querySelectorAll('[data-mealplan-select]').forEach(enhanceSelect);

    function shortDate(date) {
        return date.getDate() + ' ' + MONTHS[date.getMonth()];
    }

    function setupPlanForm(form) {
        const startInput = form.querySelector('[data-plan-start]');
        const daysInput = form.querySelector('[data-plan-days]');
        const snackInput = form.querySelector('[data-plan-snack]');
        const caloriesInput = form.querySelector('[data-plan-calories]');
        const dietInputs = Array.from(form.querySelectorAll('[data-plan-diet]'));
        const allergyInputs = Array.from(form.querySelectorAll('[data-plan-allergy]'));
        const submit = form.querySelector('[data-plan-submit]');
        const submitLabel = submit ? submit.textContent : '';
        const profileTarget = parseInt(form.dataset.profileTarget, 10);
        const defaultCalories = parseInt(form.dataset.defaultCalories, 10) || 2000;
        const output = {};

        document.querySelectorAll('[data-summary]').forEach(function (element) {
            output[element.dataset.summary] = element;
        });

        function write(name, text) {
            if (output[name]) {
                output[name].textContent = text;
            }
        }

        function update() {
            let days = parseInt(daysInput.value, 10);
            if (!Number.isFinite(days)) {
                days = 7;
            }
            days = Math.max(1, Math.min(days, 14));
            let duration = days === 1 ? '1 day' : days + ' days';
            if (startInput.value) {
                const start = new Date(startInput.value + 'T00:00:00');
                if (!Number.isNaN(start.getTime())) {
                    const end = new Date(start);
                    end.setDate(start.getDate() + days - 1);
                    duration += ' · ' + shortDate(start) + (days > 1 ? ' – ' + shortDate(end) : '');
                }
            }
            write('duration', duration);
            write('meals', snackInput.checked ? 'Breakfast, lunch, dinner, snack' : 'Breakfast, lunch, dinner');
            const diets = dietInputs.filter(function (input) {
                return input.checked;
            }).map(function (input) {
                return input.dataset.name;
            });
            write('diet', diets.length ? diets.join(', ') : 'No preference');
            const avoiding = allergyInputs.filter(function (input) {
                return input.checked;
            }).map(function (input) {
                return input.dataset.name;
            });
            write('avoiding', avoiding.length ? avoiding.join(', ') : 'Nothing selected');
            const goal = parseInt(caloriesInput.value, 10);
            if (Number.isFinite(goal) && goal > 0) {
                write('calories', goal.toLocaleString('en-US') + ' kcal/day (your goal)');
            } else if (Number.isFinite(profileTarget) && profileTarget > 0) {
                write('calories', profileTarget.toLocaleString('en-US') + ' kcal/day (from your profile)');
            } else {
                write('calories', defaultCalories.toLocaleString('en-US') + ' kcal/day (general reference)');
            }
        }

        form.addEventListener('input', update);
        form.addEventListener('change', update);
        form.addEventListener('submit', function () {
            if (submit) {
                submit.disabled = true;
                submit.textContent = submit.dataset.busyLabel || submitLabel;
            }
        });
        window.addEventListener('pageshow', function () {
            if (submit) {
                submit.disabled = false;
                submit.textContent = submitLabel;
            }
        });
        update();
    }

    document.querySelectorAll('.mealplan-chip-input').forEach(function (input) {
        input.addEventListener('change', function () {
            input.closest('.chip').classList.toggle('is-selected', input.checked);
        });
    });

    const planForm = document.querySelector('[data-plan-form]');
    if (planForm) {
        setupPlanForm(planForm);
    }

    function closeOnBackdrop(dialog) {
        dialog.addEventListener('click', function (event) {
            if (event.target !== dialog) {
                return;
            }
            const box = dialog.getBoundingClientRect();
            const inside = event.clientX >= box.left && event.clientX <= box.right && event.clientY >= box.top && event.clientY <= box.bottom;
            if (!inside) {
                dialog.close();
            }
        });
    }

    document.querySelectorAll('dialog.mealplan-dialog').forEach(closeOnBackdrop);

    const replaceDialog = document.getElementById('replace-dialog');
    const replaceBody = replaceDialog ? replaceDialog.querySelector('[data-replace-body]') : null;
    let replaceRequest = 0;

    function showReplaceMessage(text) {
        const wrapper = document.createElement('div');
        const message = document.createElement('p');
        message.className = 'type-body-sm text-secondary';
        message.setAttribute('role', 'status');
        message.textContent = text;
        wrapper.className = 'mealplan-replace-loading';
        wrapper.append(message);
        replaceBody.replaceChildren(wrapper);
    }

    function showReplaceError() {
        const panel = document.createElement('div');
        const alert = document.createElement('div');
        const footer = document.createElement('div');
        const cancel = document.createElement('button');
        panel.className = 'mealplan-replace';
        alert.className = 'alert alert-warning';
        alert.setAttribute('role', 'status');
        alert.textContent = "We couldn't load other recipes right now. Please try again in a moment.";
        footer.className = 'mealplan-replace-footer';
        cancel.type = 'button';
        cancel.className = 'btn btn-secondary mealplan-dialog-button';
        cancel.dataset.dialogClose = '';
        cancel.textContent = 'Close';
        footer.append(cancel);
        panel.append(alert, footer);
        replaceBody.replaceChildren(panel);
    }

    function loadReplacePanel(url) {
        const request = ++replaceRequest;
        const current = replaceBody.querySelector('[data-replace-panel]');
        if (current) {
            current.classList.add('is-loading');
        }
        fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' }, credentials: 'same-origin' })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error('Request failed');
                }
                return response.text();
            })
            .then(function (html) {
                if (request !== replaceRequest) {
                    return;
                }
                replaceBody.innerHTML = html;
                const title = replaceBody.querySelector('.dialog-title');
                if (title) {
                    title.tabIndex = -1;
                    title.focus();
                }
            })
            .catch(function () {
                if (request === replaceRequest) {
                    showReplaceError();
                }
            });
    }

    document.addEventListener('click', function (event) {
        const opener = event.target.closest('[data-dialog-open]');
        if (opener) {
            const dialog = document.getElementById(opener.dataset.dialogOpen);
            if (dialog && typeof dialog.showModal === 'function') {
                event.preventDefault();
                dialog.showModal();
            }
            return;
        }

        const closer = event.target.closest('[data-dialog-close]');
        if (closer) {
            const dialog = closer.closest('dialog');
            if (dialog) {
                event.preventDefault();
                dialog.close();
            }
            return;
        }

        const replaceLink = event.target.closest('[data-replace-url]');
        if (replaceLink && replaceDialog && typeof replaceDialog.showModal === 'function') {
            event.preventDefault();
            showReplaceMessage('Finding recipes that fit your plan…');
            replaceDialog.showModal();
            loadReplacePanel(replaceLink.dataset.replaceUrl);
            return;
        }

        const moreLink = event.target.closest('[data-replace-more]');
        if (moreLink && replaceDialog && replaceDialog.contains(moreLink)) {
            event.preventDefault();
            loadReplacePanel(moreLink.dataset.replaceMore);
        }
    });

    if (replaceDialog) {
        replaceDialog.addEventListener('close', function () {
            replaceRequest += 1;
        });
    }

    const dayChips = Array.from(document.querySelectorAll('[data-day-chip]'));
    if (dayChips.length) {
        const chipRow = dayChips[0].parentElement;
        const sections = dayChips.map(function (chip) {
            return document.getElementById('day-' + chip.dataset.dayChip);
        });
        let ticking = false;

        function markChip(number) {
            dayChips.forEach(function (chip) {
                const selected = chip.dataset.dayChip === String(number);
                chip.classList.toggle('is-selected', selected);
                if (selected) {
                    chip.setAttribute('aria-current', 'true');
                    const left = chip.offsetLeft - chipRow.offsetLeft;
                    if (left < chipRow.scrollLeft || left + chip.offsetWidth > chipRow.scrollLeft + chipRow.clientWidth) {
                        chipRow.scrollLeft = left - 16;
                    }
                } else {
                    chip.removeAttribute('aria-current');
                }
            });
        }

        function onScroll() {
            ticking = false;
            let current = 0;
            const atBottom = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2;
            sections.forEach(function (section, index) {
                if (!section) {
                    return;
                }
                const top = section.getBoundingClientRect().top;
                if (top <= 160 || (atBottom && top < window.innerHeight * 0.6)) {
                    current = index;
                }
            });
            markChip(dayChips[current].dataset.dayChip);
        }

        window.addEventListener('scroll', function () {
            if (!ticking) {
                ticking = true;
                window.requestAnimationFrame(onScroll);
            }
        }, { passive: true });

        dayChips.forEach(function (chip) {
            chip.addEventListener('click', function () {
                markChip(chip.dataset.dayChip);
            });
        });
    }

    const loadMore = document.querySelector('[data-load-more]');
    const recipeGrid = document.querySelector('[data-recipe-grid]');
    const recipeCount = document.querySelector('[data-recipe-count]');

    if (loadMore && recipeGrid) {
        loadMore.addEventListener('click', function (event) {
            event.preventDefault();
            if (loadMore.classList.contains('is-loading')) {
                return;
            }
            const pageUrl = loadMore.href;
            const url = new URL(pageUrl, window.location.href);
            url.searchParams.set('partial', '1');
            loadMore.classList.add('is-loading');
            loadMore.setAttribute('aria-busy', 'true');
            fetch(url.toString(), { headers: { 'X-Requested-With': 'XMLHttpRequest' }, credentials: 'same-origin' })
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error('Request failed');
                    }
                    return response.json();
                })
                .then(function (data) {
                    if (data.error) {
                        throw new Error(data.error);
                    }
                    const before = recipeGrid.children.length;
                    recipeGrid.insertAdjacentHTML('beforeend', data.html);
                    if (recipeCount && data.count) {
                        recipeCount.textContent = data.count;
                    }
                    window.history.replaceState(null, '', pageUrl);
                    const firstNew = recipeGrid.children[before];
                    if (data.next_url) {
                        loadMore.href = data.next_url;
                        loadMore.classList.remove('is-loading');
                        loadMore.removeAttribute('aria-busy');
                    } else {
                        loadMore.remove();
                    }
                    if (firstNew) {
                        firstNew.focus({ preventScroll: true });
                    }
                })
                .catch(function () {
                    window.location.href = pageUrl;
                });
        });
    }
})();
