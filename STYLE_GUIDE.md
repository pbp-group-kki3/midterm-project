# SpoonFeed Style Guide

How to make your module look like the rest of SpoonFeed.

- **Figma:** [DESIGN-SYSTEM](https://www.figma.com/design/CPywGGQPpltri1IsAXi0hK/DESIGN-SYSTEM). The "FINAL WIREFRAME" section on the Mockup page is what we build.
- **Live styleguide:** every color and component, working, with code to copy. See below for how to open it.

---

## 0. Opening the live styleguide

1. Open a terminal in the `midterm-project` folder.
2. Turn on the virtual environment:
    ```
    env\Scripts\activate
    ```
3. Start the server:
    ```
    python manage.py runserver
    ```
4. Open **http://127.0.0.1:8000/styleguide/** in your browser.

You can also get there from **http://127.0.0.1:8000/modules/** → Styleguide card.

---

## 1. Setup

Every page extends `base.html`. That already loads all the shared CSS, Tailwind, the navbar and the footer.

```html
{% extends 'base.html' %}
{% load static %}

{% block title %}Recipes | SpoonFeed{% endblock %}

{% block extra_head %}
    <!-- only if you need your own CSS -->
    <link rel="stylesheet" href="{% static 'meal_plan/meal_plan.css' %}">
{% endblock %}

{% block content %}
    <header class="page-header">
        <div>
            <h1 class="page-title">Recipes</h1>
            <p class="page-subtitle">Meals planned around your diet.</p>
        </div>
    </header>

    ...the rest of your page...
{% endblock %}
```

Your own CSS goes in your app: `meal_plan/static/meal_plan/meal_plan.css`.
Don't edit the shared files in `static/css/` without telling the group first, because it changes everyone's pages.

## 2. The 4 rules

1. **No raw colors or sizes.** Don't write `#447241` or `padding: 13px`. Use a variable (`var(--color-bg-brand)`, `var(--space-lg)`) or a Tailwind class (`bg-brand`, `p-4`).
2. **Check the shared classes first.** If it's a button, card, chip, badge, input, table, popup or avatar, it already exists. Look at `/styleguide/`.
3. **Never rename a variable.** If a color changes in Figma, we change the value in `tokens.css` and every page updates by itself.
4. **Indent with 4 spaces.** The `.editorconfig` file does this for you if you install the "EditorConfig for VS Code" extension.

## 3. Where the files are

| File | What's in it |
|---|---|
| `static/css/tokens.css` | All the variables: colors, spacing, corners, shadows, sizes |
| `static/css/base.css` | Page defaults + text styles (`.type-*`) |
| `static/css/components.css` | Shared components (buttons, cards, avatar, ...). Each one has a comment with example HTML |
| `static/css/pages.css` | Styles for one-off pages (modules hub, coming soon, styleguide) |
| `static/js/tailwind-config.js` | Connects Tailwind to our variables |
| `static/img/logo.svg` | The logo as a file |
| `templates/components/logo.html` | The logo, to include in templates |
| `templates/components/avatar.html` | Profile picture circle, to include in templates |
| `midterm_project/styleguide.py` | The examples shown on `/styleguide/` |

## 4. Variables

### Colors

| Variable | Tailwind | Use it for |
|---|---|---|
| `--color-bg-canvas` | `bg-canvas` | Page background (the cream) |
| `--color-bg-surface` | `bg-surface` | Cards, inputs, popups (white) |
| `--color-bg-subtle` | `bg-subtle` | Gray buttons, image placeholders, empty score tiles, read-only inputs |
| `--color-bg-muted` | `bg-muted` | Hover on gray things, disabled |
| `--color-bg-brand` | `bg-brand` | Main green: primary buttons, navbar, footer |
| `--color-bg-brand-hover` | `bg-brand-hover` | Hover on green |
| `--color-bg-brand-subtle` | `bg-brand-subtle` | Selected chip, active side menu item, avatar without a photo |
| `--color-bg-accent` | `bg-accent` | Yellow Login button only |
| `--color-bg-feature` | `bg-feature` | Dark green hero (Meal of the Day, login panel) |
| `--color-bg-success-subtle` | `bg-success-subtle` | "Better" cells, good tags |
| `--color-bg-danger` / `-subtle` | `bg-danger` / `bg-danger-subtle` | Delete button / Remove button, error box |
| `--color-text-primary` | `text-primary` | Normal text and headings |
| `--color-text-secondary` | `text-secondary` | Subtitles, descriptions |
| `--color-text-tertiary` | `text-tertiary` | Placeholders, tiny meta text, "Optional" |
| `--color-text-brand` | `text-brand` | Green links, category labels |
| `--color-text-success` | `text-success` | "Better", good stuff |
| `--color-text-danger` | `text-danger` | Error messages |
| `--color-text-on-brand` | `text-on-brand` | Text on green |
| `--color-text-on-feature` | `text-on-feature` | Text on the dark hero |
| `--color-border-subtle` | `border-subtle` | Table row lines |
| `--color-border-default` | `border-default` | Cards, inputs, chips |
| `--color-border-brand` | `border-brand` | Selected chip, outline button |
| `--color-border-danger` | `border-danger` | Input with an error |
| `--grade-a` … `--grade-e` | `bg-grade-a` … | A–E score colors |

The raw palette (`--brand-600`, `--neutral-500`, ...) is also there, but use the named ones above.

### Spacing (4px grid)

| Variable | Size | Tailwind | Use it for |
|---|---|---|---|
| `--space-xs` | 4px | `p-1`, `gap-1` | Icon next to text |
| `--space-sm` | 8px | `p-2`, `gap-2` | Between buttons, chips |
| `--space-md` | 12px | `p-3`, `gap-3` | Inside small things |
| `--space-lg` | 16px | `p-4`, `gap-4` | Card body, grid gaps |
| `--space-xl` | 24px | `p-6`, `gap-6` | Card padding, between blocks |
| `--space-2xl` | 32px | `p-8` | Big blocks |
| `--space-3xl` | 40px | `p-10` | Between page sections |
| `--space-4xl` | 64px | `p-16` | Above the footer |

### Corners and shadows

| Variable | Size | Tailwind | Use it for |
|---|---|---|---|
| `--radius-sm` | 8px | `rounded-sm` | Score tiles, small tags |
| `--radius-md` | 12px | `rounded-md` | Buttons, inputs |
| `--radius-lg` | 16px | `rounded-lg` | Cards |
| `--radius-xl` | 24px | `rounded-xl` | Hero blocks |
| `--radius-full` | round | `rounded-full` | Pills, chips, avatars |
| `--shadow-card` | | `shadow-card` | Resting card |
| `--shadow-md` | | `shadow-md` | Hover, floating buttons |
| `--shadow-lg` | | `shadow-lg` | Popups |

### Reading Figma

In Figma Dev Mode you'll see things like `var(--space-sm)`, `var(--radius-md)`, `var(--color-text-secondary)`. Those exact names exist in our CSS, so you can copy them straight across.

## 5. Text styles

Font is **Inter**. **Young Serif** is only for big hero titles.

| Class | Looks like | Use it for |
|---|---|---|
| `.type-heading-l` | 36 bold | Big page title ("Compare", username on profile) |
| `.type-heading-m` | 28 bold | Normal page title ("Discover products") |
| `.type-serif` | 36 serif | Hero titles |
| `.type-h3` | 20 bold | Section title ("Your articles") |
| `.type-title` | 18 semibold | Popup title |
| `.type-card-title` | 16 semibold | Name on a card |
| `.type-body-lg` | 16 | Paragraphs |
| `.type-body-sm` | 14 | Subtitles, table text |
| `.type-label-md` | 14 semibold | Form labels |
| `.type-caption` | 12 | Meta text ("200 ml") |
| `.type-overline` | 12 bold caps | Section labels ("SCORES"). Add `text-brand` for green |

## 6. Components

Full code for each is on `/styleguide/`, and every one has a comment with example HTML in `components.css`.

| What | Classes | Who uses it |
|---|---|---|
| Buttons | `.btn` + `.btn-primary` / `-secondary` / `-outline` / `-white` / `-ghost` / `-danger` / `-danger-subtle` / `-accent` / `-on-feature` / `-load-more`. Sizes `.btn-sm` `.btn-lg`. Shape `.btn-pill` `.btn-block` | Everyone |
| Icon button | `.icon-btn` (+ `.is-active`, `.icon-btn-dark`, `.icon-btn-plain`) | Heart on cards, carousel, popup close |
| Links | `.link`, `.back-link` | Everyone |
| Card | `.card`, `.card-title` (+ `.card-elevated`, `.card-flush`) | Everyone |
| Image card | `.media-card` > `.media-card-img`, `.media-card-body`, `.media-card-footer` | Discover, Compare, Meal Plan, Blog, Home |
| Card grid | `.card-grid` (+ `.card-grid-4`) | Lists of cards |
| Score tiles | `.score-row` > `.score-tile` + `.grade-a` … `.grade-e` | Discover, Compare, Product detail |
| Filter chips | `.chip-row` > `.chip` (+ `.is-selected`) | Discover, Blog |
| Badges | `.badge` (+ `-success` `-warning` `-danger` `-info` `-brand` `-on-feature`), `.badge-row` | Cards everywhere |
| Form | `.form-stack` > `.field` > `.field-label`, `.input`, `.field-helper` / `.field-error`. `.input.is-error`. `.input-group`. `.checkbox` | Profile, Meal Plan, Blog, Compare |
| Search bar | `.search-bar` | Discover, Blog, Meal Plan |
| Alerts | `.alert` + `-success` / `-warning` / `-danger` / `-info` | Forms, Django messages |
| Data table | `.data-table` > `.data-table-section` > `.data-table-title`, `.data-table-row` > `.data-table-label`, `.data-table-cell` (+ `.is-better`), `.better-tag` | Compare, Product detail |
| Popup | `<dialog class="dialog">` > `.dialog-header`, `.dialog-title`, `.dialog-text`, `.dialog-body`, `.dialog-actions` | Compare save, Blog delete, Profile delete |
| Empty state | `.empty-state` | Any empty list |
| Avatar | `.avatar` (+ `-sm` `-lg` `-xl`), `.user-chip` | Navbar, Profile, comments |
| Photo picker | `.photo-picker`, `.photo-picker-hint` | Profile |
| Side menu | `.side-nav` > `.side-nav-link` (+ `.is-active`) | Profile |
| Feature card | `.feature-card` | Home (Meal / Food of the Day) |
| Page header | `.page-header` > `.page-title`, `.page-subtitle`, `.page-actions`. Profile: `.page-header-user`, `.page-title-lg` | Top of every module page |

### Profile picture

Use the template, it picks the photo or the first letter for you:

```html
{% include 'components/avatar.html' with name=user.username photo=photo_url size='lg' %}
```

- `name`: the user's name (needed for the letter)
- `photo`: the photo URL. Leave it out if there's no photo, and the first letter shows instead
- `size`: `'sm'` 32px (navbar), nothing for 40px, `'lg'` 72px (profile header), `'xl'` 96px (photo picker)

For the Profile module: once the Profile model has a photo field, pass its URL in the navbar too (there's a TODO in `templates/header.html`).

### Logo

The logo is an SVG from Figma. Don't type "SpoonFeed" in a fancy font, include it:

```html
{% include 'components/logo.html' %}
```

The word is cream by default (for green backgrounds). On a light background, wrap it:

```html
<span class="logo-on-light">{% include 'components/logo.html' %}</span>
```

Need it as an image file? `{% static 'img/logo.svg' %}`.

### Popups (dialogs)

Two kinds, both on `/styleguide/`:

- **Confirm dialog** (`.dialog`): question + sentence + buttons on the right. "Delete your account?", "Clear your viewing history?"
- **Form dialog** (`.dialog .dialog-form`): title + sentence + fields + buttons on the right. "Change password", "Save comparison"

Use `{% include 'components/dialog_close.html' %}` for the × button. Open a dialog with:

```html
<button class="btn btn-danger" onclick="document.getElementById('delete-dialog').showModal()">Delete account</button>
<dialog class="dialog" id="delete-dialog">...</dialog>
```

Widths: 560px by default, `.dialog-sm` 480, `.dialog-lg` 640, `.dialog-xl` 720.

### Checking your page against Figma

1. In Figma, open **Dev Mode** (top right, or Shift + D) and click the thing you want to check. The right panel shows its width, height, padding and the variables it uses.
2. In the browser, right-click the same thing on your page → **Inspect**. Hover the element in the Elements panel: Chrome shows its size on the page, and the **Computed** tab shows padding, font size and colors.
3. Compare the numbers. Make sure the browser zoom is 100% (Ctrl + 0) and the window is at least as wide as the Figma frame (1440px for desktop screens).

Faster for a whole screen: in Figma select the frame → **Export** → PNG 1x, then put it next to a screenshot of your page at the same width.

## 7. How we use Tailwind

Tailwind is already set up. It's loaded in `base.html` from the Tailwind CDN, and `static/js/tailwind-config.js` tells it to use **our** colors and corners. You don't need to install anything or run any build command.

**The split:**

- **Shared classes** for how things *look*: `.btn`, `.card`, `.badge`, `.media-card`, `.avatar` ...
- **Tailwind** for how things are *laid out*: `flex`, `grid`, `gap-4`, `mt-6`, `px-4`, `md:grid-cols-2`, `hidden md:block` ...

```html
<!-- Tailwind does the layout, our classes do the look -->
<div class="grid md:grid-cols-3 gap-6 mt-8">
    <article class="media-card">...</article>
    <article class="media-card">...</article>
    <article class="media-card">...</article>
</div>
```

**Colors in Tailwind:** only use our names, because they match Figma:

✅ `bg-canvas` `bg-surface` `bg-subtle` `bg-brand` `bg-brand-subtle` `bg-feature` `bg-success-subtle` `bg-danger-subtle`
✅ `text-primary` `text-secondary` `text-tertiary` `text-brand` `text-success` `text-danger`
✅ `border-default` `border-subtle` `border-brand`
✅ `rounded-sm` (8) `rounded-md` (12) `rounded-lg` (16) `rounded-xl` (24) `rounded-full`
✅ `shadow-card` `shadow-md` `shadow-lg`

❌ `bg-green-500`, `text-gray-600`, `bg-white`: Tailwind's own colors, they don't match ours
❌ `bg-[#447241]`, `p-[13px]`, `rounded-[10px]`: made-up values

**Spacing:** Tailwind's numbers already match our 4px grid: `p-1` = 4px, `p-2` = 8px, `p-3` = 12px, `p-4` = 16px, `p-6` = 24px, `p-8` = 32px, `p-10` = 40px.

**When to make a class instead:** if you're writing the same 6+ Tailwind classes on many elements, it should be a class in your module's CSS file (or a shared one, ask the group).

**Phones:** Tailwind's `sm:` `md:` `lg:` prefixes work as usual (`md:` = 768px and up). Our shared components are already responsive.

## 8. Naming your own classes

Same pattern as the shared ones:

- `.thing` is the base
- `.thing-part` is a piece inside it (`.recipe-card-meta`)
- `.thing-variant` is a version of it (`.btn-outline`)
- `.is-state` is a state you switch on with JS or Django (`.is-selected`, `.is-open`)

**Start your own classes with your module name** so they don't clash: `.blog-`, `.mealplan-`, `.compare-`, `.discover-`, `.fotd-`, `.profile-`.

Write CSS like the shared files: 4-space indent, one property per line, a short comment above each class saying what it's for.

```css
/* Recipe info under the title, e.g. "45 min · 2 servings" */
.mealplan-recipe-meta {
    display: flex;
    gap: var(--space-sm);
    color: var(--color-text-secondary);
}
```

## 9. Need something new?

- **A new color or size:** ask in the group, then add it to `tokens.css` (and `tailwind-config.js` if you want a Tailwind class for it).
- **A new component two or more modules need:** add it to `components.css` with a comment like the others, and add an example to `EXAMPLES` in `midterm_project/styleguide.py` so it shows up on `/styleguide/`.
- **Only your module needs it:** put it in your own CSS file.
