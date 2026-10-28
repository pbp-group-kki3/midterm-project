"""Data for the /styleguide/ page.

Each example is written once here. The page shows it working
and shows the same HTML as code to copy, so the two never get out of sync.

To add a new example: copy one of the blocks in EXAMPLES at the bottom and change it.
"""
from django.shortcuts import render
from django.template import engines


# Colors: (css variable, tailwind class, what it's for)
COLORS = {
    'Backgrounds': [
        ('--color-bg-canvas', 'bg-canvas', 'Page background'),
        ('--color-bg-surface', 'bg-surface', 'Cards, inputs, popups'),
        ('--color-bg-subtle', 'bg-subtle', 'Gray buttons, image placeholders'),
        ('--color-bg-muted', 'bg-muted', 'Hover on gray, disabled'),
        ('--color-bg-brand', 'bg-brand', 'Main green: buttons, navbar, footer'),
        ('--color-bg-brand-hover', 'bg-brand-hover', 'Hover on green'),
        ('--color-bg-brand-subtle', 'bg-brand-subtle', 'Selected chip, avatar without photo'),
        ('--color-bg-accent', 'bg-accent', 'Yellow Login button'),
        ('--color-bg-feature', 'bg-feature', 'Dark green hero'),
    ],
    'Status': [
        ('--color-bg-success-subtle', 'bg-success-subtle', '"Better" cells, good tags'),
        ('--color-bg-warning-subtle', 'bg-warning-subtle', 'Warning tags'),
        ('--color-bg-danger', 'bg-danger', 'Delete button'),
        ('--color-bg-danger-subtle', 'bg-danger-subtle', 'Remove button, error box'),
        ('--color-bg-info-subtle', 'bg-info-subtle', 'Info box'),
    ],
    'Text': [
        ('--color-text-primary', 'text-primary', 'Normal text, headings'),
        ('--color-text-secondary', 'text-secondary', 'Subtitles, descriptions'),
        ('--color-text-tertiary', 'text-tertiary', 'Placeholders, tiny meta'),
        ('--color-text-brand', 'text-brand', 'Green links, category labels'),
        ('--color-text-success', 'text-success', 'Good / better'),
        ('--color-text-danger', 'text-danger', 'Errors'),
        ('--color-text-feature-accent', 'text-feature-accent', 'Gold label on dark hero'),
    ],
    'Borders': [
        ('--color-border-subtle', 'border-subtle', 'Table row lines'),
        ('--color-border-default', 'border-default', 'Cards, inputs, chips'),
        ('--color-border-brand', 'border-brand', 'Selected / outline button'),
        ('--color-border-danger', 'border-danger', 'Input with error'),
    ],
    'Grades': [
        ('--grade-a', 'bg-grade-a', 'Grade A'),
        ('--grade-b', 'bg-grade-b', 'Grade B'),
        ('--grade-c', 'bg-grade-c', 'Grade C'),
        ('--grade-d', 'bg-grade-d', 'Grade D'),
        ('--grade-e', 'bg-grade-e', 'Grade E'),
    ],
}


# Text styles: (class, size / weight, example text, what it's for)
TYPE_STYLES = [
    ('type-heading-l', '36 / 700', 'Compare', 'Big page title'),
    ('type-heading-m', '28 / 700', 'Discover products', 'Normal page title'),
    ('type-serif', '36 / serif', 'Pasta with Garlic', 'Hero titles'),
    ('type-h3', '20 / 700', 'Your articles', 'Section title'),
    ('type-title', '18 / 600', 'Save comparison', 'Popup title'),
    ('type-card-title', '16 / 600', 'Diamond Susu UHT Full Cream', 'Name on a card'),
    ('type-body-lg', '16 / 400', 'Check what is in your food.', 'Paragraphs'),
    ('type-body-sm', '14 / 400', 'Search by product name.', 'Subtitles, table cells'),
    ('type-label-md', '14 / 600', 'Username', 'Form labels'),
    ('type-caption', '12 / 500', '200 ml · Ultra Jaya', 'Meta text'),
    ('type-overline', '12 / 700 caps', 'Nutrition per 100 ml', 'Section labels'),
]


# Spacing: (variable, size, what it's for)
SPACING = [
    ('--space-xs', '4px', 'Icon next to text'),
    ('--space-sm', '8px', 'Between buttons, chips'),
    ('--space-md', '12px', 'Inside small things'),
    ('--space-lg', '16px', 'Card body padding, grid gaps'),
    ('--space-xl', '24px', 'Card padding, between blocks'),
    ('--space-2xl', '32px', 'Big blocks'),
    ('--space-3xl', '40px', 'Between page sections'),
    ('--space-4xl', '64px', 'Above the footer'),
]


# Corners: (variable, size, what it's for)
RADIUS = [
    ('--radius-sm', '8px', 'Score tiles, small tags'),
    ('--radius-md', '12px', 'Buttons, inputs'),
    ('--radius-lg', '16px', 'Cards'),
    ('--radius-xl', '24px', 'Hero blocks'),
    ('--radius-full', '999px', 'Pills, chips, avatars'),
]


# Live examples, in the order they show on the page.
#     id     used for the jump link at the top of the page
#     title  heading above the example
#     note   one line explaining it (can be empty)
#     html   the example itself, shown working and as code to copy
EXAMPLES = [
    {
        'id': 'buttons',
        'title': 'Buttons',
        'note': 'Always .btn plus one color. Add .btn-sm / .btn-lg for size, .btn-pill for round ends, .btn-block for full width.',
        'html': '''<button class="btn btn-primary">Search</button>
<button class="btn btn-secondary">Cancel</button>
<button class="btn btn-outline">+ Compare</button>
<button class="btn btn-white">Filters (1)</button>
<button class="btn btn-ghost">Clear filters</button>
<button class="btn btn-danger-subtle">Remove</button>
<button class="btn btn-danger">Delete account</button>
<button class="btn btn-accent btn-pill">Login</button>
<button class="btn btn-primary" disabled>Disabled</button>''',
    },
    {
        'id': 'button-sizes',
        'title': 'Button sizes',
        'note': 'Small 36px, normal 44px, large 52px.',
        'html': '''<button class="btn btn-primary btn-sm">Small</button>
<button class="btn btn-primary">Normal</button>
<button class="btn btn-primary btn-lg">Large</button>
<button class="btn btn-load-more">Load more products ⌄</button>''',
    },
    {
        'id': 'icons',
        'title': 'Icons',
        'note': 'All 16 original Figma variants. Use .icon plus .icon-name. Every icon is 20 × 20. bookmark includes a plus for saving; saved is the plain bookmark outline. Hide decorative icons with aria-hidden="true".',
        'html': '''<div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 w-full">
    <div class="flex items-center gap-3">
        <span class="icon icon-trash icon-default" aria-hidden="true"></span>
        <code>icon-trash</code>
    </div>
    <div class="flex items-center gap-3">
        <span class="icon icon-preferences icon-default" aria-hidden="true"></span>
        <code>icon-preferences</code>
    </div>
    <div class="flex items-center gap-3">
        <span class="icon icon-saved icon-default" aria-hidden="true"></span>
        <code>icon-saved</code>
    </div>
    <div class="flex items-center gap-3">
        <span class="icon icon-check icon-default" aria-hidden="true"></span>
        <code>icon-check</code>
    </div>
    <div class="flex items-center gap-3">
        <span class="icon icon-plus icon-default" aria-hidden="true"></span>
        <code>icon-plus</code>
    </div>
    <div class="flex items-center gap-3">
        <span class="icon icon-arrow-left icon-default" aria-hidden="true"></span>
        <code>icon-arrow-left</code>
    </div>
    <div class="flex items-center gap-3">
        <span class="icon icon-chevron-right icon-default" aria-hidden="true"></span>
        <code>icon-chevron-right</code>
    </div>
    <div class="flex items-center gap-3">
        <span class="icon icon-x icon-default" aria-hidden="true"></span>
        <code>icon-x</code>
    </div>
    <div class="flex items-center gap-3">
        <span class="icon icon-star icon-default" aria-hidden="true"></span>
        <code>icon-star</code>
    </div>
    <div class="flex items-center gap-3">
        <span class="icon icon-home icon-default" aria-hidden="true"></span>
        <code>icon-home</code>
    </div>
    <div class="flex items-center gap-3">
        <span class="icon icon-chart icon-default" aria-hidden="true"></span>
        <code>icon-chart</code>
    </div>
    <div class="flex items-center gap-3">
        <span class="icon icon-user icon-default" aria-hidden="true"></span>
        <code>icon-user</code>
    </div>
    <div class="flex items-center gap-3">
        <span class="icon icon-bell icon-default" aria-hidden="true"></span>
        <code>icon-bell</code>
    </div>
    <div class="flex items-center gap-3">
        <span class="icon icon-bookmark icon-default" aria-hidden="true"></span>
        <code>icon-bookmark</code>
    </div>
    <div class="flex items-center gap-3">
        <span class="icon icon-edit icon-default" aria-hidden="true"></span>
        <code>icon-edit</code>
    </div>
    <div class="flex items-center gap-3">
        <span class="icon icon-history icon-default" aria-hidden="true"></span>
        <code>icon-history</code>
    </div>
</div>''',
    },
    {
        'id': 'icons-in-actions',
        'title': 'Icons in actions',
        'note': 'Icons inherit text color, including white on primary buttons and the disabled color. For standalone colors, use .icon-default, .icon-primary, .icon-secondary or .icon-on-brand.',
        'html': '''<button type="button" class="btn btn-primary">
    Save comparison
    <span class="icon icon-bookmark" aria-hidden="true"></span>
</button>
<button type="button" class="btn btn-danger-subtle">
    <span class="icon icon-trash" aria-hidden="true"></span>
    Remove
</button>
<a href="#icons" class="back-link">
    <span class="icon icon-arrow-left" aria-hidden="true"></span>
    Back to Discover
</a>
<button type="button" class="btn btn-primary" disabled>
    Saved
    <span class="icon icon-saved" aria-hidden="true"></span>
</button>''',
    },
    {
        'id': 'icon-buttons',
        'title': 'Icon buttons',
        'note': 'Round buttons with only an icon. Always add an accessible label and hide the decorative icon. .is-active changes the icon color.',
        'html': '''<button type="button" class="icon-btn" aria-label="Save comparison">
    <span class="icon icon-bookmark" aria-hidden="true"></span>
</button>
<button type="button" class="icon-btn is-active" aria-label="Saved comparison">
    <span class="icon icon-saved" aria-hidden="true"></span>
</button>
<button type="button" class="icon-btn icon-btn-dark" aria-label="Previous">
    <span class="icon icon-arrow-left" aria-hidden="true"></span>
</button>
<button type="button" class="icon-btn icon-btn-plain" aria-label="Close">
    <span class="icon icon-x" aria-hidden="true"></span>
</button>''',
    },
    {
        'id': 'links',
        'title': 'Links',
        'note': '',
        'html': '''<a href="#" class="link">Sign up</a>
<a href="#" class="back-link">← Back to Discover</a>''',
    },
    {
        'id': 'chips',
        'title': 'Chips (filters)',
        'note': 'Filters you can click on and off. Put .is-selected on the ones that are on.',
        'html': '''<div class="chip-row">
    <button class="chip is-selected">Halal</button>
    <button class="chip">Grade A–B</button>
    <button class="chip">Not ultra-processed</button>
    <button class="chip">Vegan</button>
</div>''',
    },
    {
        'id': 'badges',
        'title': 'Badges',
        'note': "Small labels on cards. You can't click them.",
        'html': '''<div class="badge-row">
    <span class="badge badge-success">✓ Fits your preferences</span>
    <span class="badge badge-success">Halal</span>
    <span class="badge">No preservatives</span>
    <span class="badge">? Can't verify Halal</span>
    <span class="badge">Optional</span>
    <span class="badge badge-warning">Coming soon</span>
    <span class="badge badge-danger">Allergen</span>
    <span class="badge badge-info">New</span>
</div>''',
    },
    {
        'id': 'scores',
        'title': 'Score tiles',
        'note': 'Grade / Nutri / Green / NOVA. Add .grade-a to .grade-e to color one. No grade class = gray.',
        'html': '''<div class="score-row">
    <div class="score-tile grade-b">
        <span class="score-tile-label">Grade</span>
        <span class="score-tile-value">B</span>
    </div>
    <div class="score-tile">
        <span class="score-tile-label">Nutri</span>
        <span class="score-tile-value">B</span>
    </div>
    <div class="score-tile">
        <span class="score-tile-label">Green</span>
        <span class="score-tile-value">C</span>
    </div>
    <div class="score-tile">
        <span class="score-tile-label">NOVA</span>
        <span class="score-tile-value">1</span>
    </div>
</div>''',
    },
    {
        'id': 'grades',
        'title': 'All grade colors',
        'note': '',
        'html': '''<div class="score-row max-w-sm grid-cols-5">
    <div class="score-tile grade-a">
        <span class="score-tile-label">Grade</span>
        <span class="score-tile-value">A</span>
    </div>
    <div class="score-tile grade-b">
        <span class="score-tile-label">Grade</span>
        <span class="score-tile-value">B</span>
    </div>
    <div class="score-tile grade-c">
        <span class="score-tile-label">Grade</span>
        <span class="score-tile-value">C</span>
    </div>
    <div class="score-tile grade-d">
        <span class="score-tile-label">Grade</span>
        <span class="score-tile-value">D</span>
    </div>
    <div class="score-tile grade-e">
        <span class="score-tile-label">Grade</span>
        <span class="score-tile-value">E</span>
    </div>
</div>''',
    },
    {
        'id': 'product-card',
        'title': 'Product card',
        'note': 'A .media-card with score tiles and two buttons. The same base works for recipes and articles.',
        'html': '''<article class="media-card max-w-sm">
    <div class="media-card-img">Front photo</div>
    <div class="media-card-corner">
        <button class="icon-btn" aria-label="Save">♡</button>
    </div>
    <div class="media-card-body">
        <div>
            <h3 class="media-card-title">Diamond Susu UHT Full Cream</h3>
            <p class="media-card-subtitle">200 ml</p>
        </div>
        <div class="score-row">
            <div class="score-tile grade-b">
                <span class="score-tile-label">Grade</span>
                <span class="score-tile-value">B</span>
            </div>
            <div class="score-tile">
                <span class="score-tile-label">Nutri</span>
                <span class="score-tile-value">B</span>
            </div>
            <div class="score-tile">
                <span class="score-tile-label">Green</span>
                <span class="score-tile-value">C</span>
            </div>
            <div class="score-tile">
                <span class="score-tile-label">NOVA</span>
                <span class="score-tile-value">1</span>
            </div>
        </div>
        <div class="badge-row">
            <span class="badge badge-success">✓ Fits your preferences</span>
        </div>
    </div>
    <div class="media-card-footer">
        <button class="btn btn-outline">+ Compare</button>
        <a href="#" class="btn btn-primary">Details</a>
    </div>
</article>''',
    },
    {
        'id': 'recipe-card',
        'title': 'Recipe / article card',
        'note': 'Same .media-card, different stuff inside. Put many cards in .card-grid (add .card-grid-4 for 4 columns).',
        'html': '''<div class="card-grid card-grid-4">
    <a href="#" class="media-card">
        <div class="media-card-img">Recipe photo, 3:2</div>
        <div class="media-card-body">
            <div class="badge-row">
                <span class="badge badge-success">Vegan</span>
                <span class="badge">Dairy free</span>
            </div>
            <h3 class="media-card-title">Mango Fried Rice</h3>
            <p class="media-card-subtitle">45 min · 4 servings</p>
        </div>
    </a>
    <a href="#" class="media-card">
        <div class="media-card-img">Cover image</div>
        <div class="media-card-body">
            <span class="type-overline text-brand">Packaging</span>
            <h3 class="media-card-title">Example article</h3>
            <p class="media-card-subtitle">[Author] | 5 min read</p>
        </div>
    </a>
</div>''',
    },
    {
        'id': 'card',
        'title': 'Card',
        'note': 'White box for any group of content. .card-title for the heading inside.',
        'html': '''<div class="card">
    <h2 class="card-title">
        Personal Information
        <span class="badge">Optional</span>
    </h2>
    <p class="type-body-sm text-secondary">Anything goes in here.</p>
</div>''',
    },
    {
        'id': 'forms',
        'title': 'Forms',
        'note': "Wrap each input in .field. When it's wrong: .is-error on the input and a .field-error under it. Read-only inputs turn gray.",
        'html': '''<form class="form-stack max-w-md">
    <div class="field">
        <label class="field-label" for="sg-user">Username</label>
        <input class="input" id="sg-user" placeholder="[username]">
    </div>
    <div class="field">
        <label class="field-label" for="sg-name">Comparison name *</label>
        <input class="input is-error" id="sg-name" placeholder="e.g. UHT milk comparison">
        <p class="field-error">Enter a comparison name.</p>
    </div>
    <div class="field">
        <label class="field-label" for="sg-fullname">Full name</label>
        <input class="input" id="sg-fullname" placeholder="Enter your full name" readonly>
        <p class="field-helper">Read-only: click "Edit profile" to change it.</p>
    </div>
    <div class="field">
        <label class="field-label" for="sg-diet">Diet</label>
        <select class="input" id="sg-diet">
            <option>No preference</option>
            <option>Vegan</option>
        </select>
    </div>
    <div class="field">
        <label class="field-label" for="sg-notes">Notes (optional)</label>
        <textarea class="input" id="sg-notes" placeholder="Add a note"></textarea>
    </div>
    <label class="checkbox"><input type="checkbox" checked> Gluten free</label>
</form>''',
    },
    {
        'id': 'input-group',
        'title': 'Input with a link inside',
        'note': 'For things like the password field on the profile page.',
        'html': '''<div class="field max-w-md">
    <label class="field-label" for="sg-password">Password</label>
    <div class="input-group">
        <input class="input" id="sg-password" type="password" value="secretpassword" readonly>
        <a href="#" class="link">Change password</a>
    </div>
</div>''',
    },
    {
        'id': 'search',
        'title': 'Search bar',
        'note': 'The input stretches, buttons sit after it. Wraps on phones.',
        'html': '''<form class="search-bar">
    <input class="input" placeholder="susu uht">
    <button class="btn btn-primary">Search</button>
    <button class="btn btn-white" type="button">Filters (1)</button>
    <button class="btn btn-white" type="button">Sort: Best grade</button>
</form>''',
    },
    {
        'id': 'alerts',
        'title': 'Alerts',
        'note': 'Message box. Good for Django messages.',
        'html': '''<div class="form-stack">
    <div class="alert alert-success">Comparison saved.</div>
    <div class="alert alert-warning">Some data is missing for this product.</div>
    <div class="alert alert-danger">Wrong username or password.</div>
    <div class="alert alert-info">Log in to save products.</div>
</div>''',
    },
    {
        'id': 'table',
        'title': 'Data table',
        'note': 'For Compare and Product detail. Put .is-better on the cell that wins. Works with 2 or 3 products.',
        'html': '''<div class="card">
    <div class="data-table">
        <section class="data-table-section">
            <h3 class="data-table-title">Scores</h3>
            <div class="data-table-row">
                <span class="data-table-label">SpoonFeed grade</span>
                <div class="data-table-cell">C (56)</div>
                <div class="data-table-cell is-better">
                    B (70)
                    <span class="better-tag">✓ Better</span>
                </div>
            </div>
            <div class="data-table-row">
                <span class="data-table-label">Nutri-Score</span>
                <div class="data-table-cell">B</div>
                <div class="data-table-cell">B</div>
            </div>
            <div class="data-table-row">
                <span class="data-table-label">Green-Score</span>
                <div class="data-table-cell">D (37)</div>
                <div class="data-table-cell is-better">
                    C (51)
                    <span class="better-tag">✓ Better</span>
                </div>
            </div>
        </section>
        <section class="data-table-section">
            <h3 class="data-table-title">Nutrition per 100 ml</h3>
            <div class="data-table-row">
                <span class="data-table-label">Energy</span>
                <div class="data-table-cell is-better">
                    44 kcal
                    <span class="better-tag">✓ Better</span>
                </div>
                <div class="data-table-cell">60 kcal</div>
            </div>
            <div class="data-table-row">
                <span class="data-table-label">Sugars</span>
                <div class="data-table-cell">4.4 g</div>
                <div class="data-table-cell is-better">
                    3 g
                    <span class="better-tag">✓ Better</span>
                </div>
            </div>
        </section>
    </div>
</div>''',
    },
    {
        'id': 'dialog',
        'title': 'Confirm dialog (popup)',
        'note': 'A question, a sentence, buttons on the right. Shown open here. On a real page it starts hidden: remove "open" and call document.getElementById("delete-dialog").showModal().',
        'html': '''<dialog class="dialog" id="delete-dialog" open>
    <div class="dialog-header">
        <h2 class="dialog-title">Delete your account?</h2>
        {% include 'components/dialog_close.html' %}
    </div>
    <p class="dialog-text">This removes your profile, saved items, history and meal plans. It cannot be undone.</p>
    <div class="dialog-actions">
        <button type="button" class="btn btn-secondary">Cancel</button>
        <form method="post" action="#">
            {% csrf_token %}
            <button type="button" class="btn btn-danger">Delete account</button>
        </form>
    </div>
</dialog>''',
    },
    {
        'id': 'dialog-form',
        'title': 'Form dialog (popup)',
        'note': 'Add .dialog-form: smaller sentence, fields, buttons on the right.',
        'html': '''<dialog class="dialog dialog-form" id="password-dialog" open>
    <h2 class="dialog-title">Change password</h2>
    <p class="dialog-text">Enter your current password and choose a new one.</p>
    <form method="post" action="#">
        {% csrf_token %}
        <div class="dialog-body">
            <div class="field">
                <label class="field-label" for="current-password">Current password</label>
                <input class="input" type="password" id="current-password" placeholder="[Password]">
            </div>
            <div class="field">
                <label class="field-label" for="new-password">New password</label>
                <input class="input" type="password" id="new-password" placeholder="[Password]">
            </div>
            <div class="field">
                <label class="field-label" for="confirm-password">Confirm new password</label>
                <input class="input" type="password" id="confirm-password" placeholder="[Password]">
            </div>
        </div>
        <div class="dialog-actions">
            <button type="button" class="btn btn-secondary">Cancel</button>
            <button type="button" class="btn btn-primary">Save changes</button>
        </div>
    </form>
</dialog>''',
    },
    {
        'id': 'empty',
        'title': 'Empty state',
        'note': 'What to show when a list is empty.',
        'html': '''<div class="empty-state">
    <span class="empty-state-icon">📝</span>
    <h3 class="empty-state-title">No articles yet</h3>
    <p class="empty-state-text">Write your first article and it will show up here.</p>
    <a href="#" class="btn btn-primary">+ Create article</a>
</div>''',
    },
    {
        'id': 'avatar',
        'title': 'Avatar (profile picture)',
        'note': "Shows the photo, or the first letter if there's no photo yet. Easiest way: {% include 'components/avatar.html' with name=... photo=... size=... %}",
        'html': '''<span class="avatar avatar-sm">V</span>
<span class="avatar">V</span>
<span class="avatar avatar-lg">V</span>
<span class="avatar avatar-xl">V</span>

<span class="avatar avatar-sm"><img src="/static/img/avatar-example.svg" alt="VegetableLover"></span>
<span class="avatar"><img src="/static/img/avatar-example.svg" alt="VegetableLover"></span>
<span class="avatar avatar-lg"><img src="/static/img/avatar-example.svg" alt="VegetableLover"></span>
<span class="avatar avatar-xl"><img src="/static/img/avatar-example.svg" alt="VegetableLover"></span>''',
    },
    {
        'id': 'user-chip',
        'title': 'Navbar user pill',
        'note': 'Small avatar + username. Only works on green, like in the navbar.',
        'html': '''<span class="bg-brand rounded-full p-3 inline-flex gap-3">
    <a href="#" class="user-chip">
        <span class="avatar avatar-sm">R</span>
        Reyhan
    </a>
    <a href="#" class="user-chip">
        <span class="avatar avatar-sm"><img src="/static/img/avatar-example.svg" alt=""></span>
        Reyhan
    </a>
</span>''',
    },
    {
        'id': 'photo-picker',
        'title': 'Profile photo picker',
        'note': 'On the Profile page. Left: no photo yet. Right: has a photo.',
        'html': '''<div class="flex gap-12">
    <div class="photo-picker">
        <span class="avatar avatar-xl">V</span>
        <label class="btn btn-secondary btn-sm btn-block" for="sg-photo">Add photo</label>
        <input type="file" id="sg-photo" accept="image/*" hidden>
        <span class="photo-picker-hint">Optional</span>
    </div>
    <div class="photo-picker">
        <span class="avatar avatar-xl"><img src="/static/img/avatar-example.svg" alt=""></span>
        <button class="btn btn-secondary btn-sm btn-block">Change photo</button>
        <button class="btn btn-danger-subtle btn-sm btn-block">Remove</button>
    </div>
</div>''',
    },
    {
        'id': 'profile-header',
        'title': 'Profile header',
        'note': 'Page header with the picture next to the name.',
        'html': '''<header class="page-header">
    <div class="page-header-user">
        <span class="avatar avatar-lg">V</span>
        <div>
            <h1 class="page-title page-title-lg">VegetableLover</h1>
            <p class="page-subtitle">VegieGoblin@gmail.com</p>
        </div>
    </div>
    <div class="page-actions">
        <a href="#" class="btn btn-secondary">
            Edit profile
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M4 20h4L19 9l-4-4L4 16v4z"/>
            </svg>
        </a>
    </div>
</header>''',
    },
    {
        'id': 'side-nav',
        'title': 'Side menu',
        'note': "Menu on the left of the Profile page. .is-active on the page you're on.",
        'html': '''<nav class="side-nav">
    <a href="#" class="side-nav-link is-active">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
            <circle cx="12" cy="8" r="4"/>
            <path d="M4 21c1-4 4-6 8-6s7 2 8 6"/>
        </svg>
        Account
    </a>
    <a href="#" class="side-nav-link">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
            <path d="M4 7h10M18 7h2M4 17h2M10 17h10"/>
            <circle cx="16" cy="7" r="2"/>
            <circle cx="8" cy="17" r="2"/>
        </svg>
        Preferences
    </a>
    <a href="#" class="side-nav-link">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" aria-hidden="true">
            <path d="M6 3h12v18l-6-4-6 4z"/>
        </svg>
        Saved
    </a>
    <a href="#" class="side-nav-link">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
            <path d="M3 12a9 9 0 1 0 3-6.7L3 8"/>
            <path d="M3 3v5h5M12 7v5l3 2"/>
        </svg>
        History
    </a>
</nav>''',
    },
    {
        'id': 'feature',
        'title': 'Feature card',
        'note': 'Dark green hero for Meal / Food of the Day. Text left, image right.',
        'html': '''<section class="feature-card">
    <div class="feature-card-text">
        <span class="feature-card-overline">Meal of the day</span>
        <h2 class="feature-card-title">Pasta with Garlic, Scallions &amp; Breadcrumbs</h2>
        <p class="feature-card-meta">45 min | Serves 2 | 584 kcal per serving</p>
        <div class="badge-row">
            <span class="badge badge-on-feature">Lunch</span>
            <span class="badge badge-on-feature">Main course</span>
        </div>
        <a href="#" class="btn btn-on-feature btn-pill btn-sm">Show recipe ↑</a>
    </div>
    <div class="feature-card-img"></div>
</section>''',
    },
    {
        'id': 'page-header',
        'title': 'Page header',
        'note': 'Put this at the top of every module page so titles line up across the app.',
        'html': '''<header class="page-header">
    <div>
        <h1 class="page-title">Recipes</h1>
        <p class="page-subtitle">Meals planned around your diet and goals.</p>
    </div>
    <div class="page-actions">
        <a href="#" class="btn btn-secondary">My plans</a>
        <a href="#" class="btn btn-primary">Create meal plan</a>
    </div>
</header>''',
    },
    {
        'id': 'logo',
        'title': 'Logo',
        'note': 'An SVG from Figma. Cream on green, or wrap it in .logo-on-light to make it green. Need an image file instead? Use static/img/logo.svg.',
        'html': '''<span class="bg-brand rounded-lg p-4 inline-block">
    {% include 'components/logo.html' %}
</span>

<span class="logo-on-light border border-default rounded-lg p-4 inline-block">
    {% include 'components/logo.html' %}
</span>''',
    },
    {
        'id': 'tailwind',
        'title': 'Mixing with Tailwind',
        'note': 'Shared classes for the look (card, btn, badge). Tailwind for layout and spacing (grid, gap, mt).',
        'html': '''<div class="grid md:grid-cols-2 gap-4">
    <div class="card">
        <h3 class="type-card-title">Left card</h3>
        <p class="type-body-sm text-secondary mt-1">grid + gap-4 come from Tailwind.</p>
        <button class="btn btn-primary btn-sm mt-4">Button</button>
    </div>
    <div class="bg-surface border border-default rounded-lg p-6">
        <h3 class="type-card-title">Right card</h3>
        <p class="type-body-sm text-secondary mt-1">Built only with Tailwind, using our colors.</p>
    </div>
</div>''',
    },
]


def styleguide(request):
    """Shows every color, text style and component with code to copy."""
    django_templates = engines['django']

    # Run each example through Django so {% include %} and {% csrf_token %} work in the live version.
    # The code box still shows the original html, which is what teammates should copy.
    examples = []
    for example in EXAMPLES:
        rendered = django_templates.from_string(example['html']).render(request=request)
        examples.append({**example, 'rendered': rendered})

    context = {
        'colors': COLORS,
        'type_styles': TYPE_STYLES,
        'spacing': SPACING,
        'radius': RADIUS,
        'examples': examples,
    }
    return render(request, 'placeholders/styleguide.html', context)
