// Opens and closes the phone menu when you tap the ☰ button in the navbar.
// It just adds or removes .is-open on #navbar-mobile (styled in components.css).

document.addEventListener('DOMContentLoaded', () => {
    const toggle = document.getElementById('navbar-toggle');
    const menu = document.getElementById('navbar-mobile');

    if (!toggle || !menu) {
        return;
    }

    toggle.addEventListener('click', () => {
        const isOpen = menu.classList.toggle('is-open');
        toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    });
});
