// SpoonFeed Tailwind setup
//
// This makes Tailwind use OUR colors and sizes from static/css/tokens.css,
// so bg-brand, text-secondary, rounded-lg, etc. match Figma exactly.
//
// Use Tailwind for layout and spacing:   flex, grid, gap-4, mt-6, md:grid-cols-2
// Use our named colors:                  bg-brand, bg-surface, text-secondary, border-default
// Don't use Tailwind's own colors:       bg-green-500, text-gray-600  (they don't match our design)
//
// Full list with examples: STYLE_GUIDE.md section 7, or /styleguide/

// Helper: turns ('brand', [50, 100]) into { 50: 'var(--brand-50)', 100: 'var(--brand-100)' }
const ramp = (name, steps) =>
    Object.fromEntries(steps.map((step) => [step, `var(--${name}-${step})`]));

tailwind.config = {
    theme: {
        extend: {

            // font-sans (Inter, default) and font-display (Young Serif, hero titles)
            fontFamily: {
                sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
                display: ['Young Serif', 'Georgia', 'serif'],
            },

            // Raw palette, e.g. bg-brand-600, text-neutral-500. Try the named ones below first.
            colors: {
                brand: ramp('brand', [50, 100, 200, 300, 400, 500, 600, 700, 800, 900]),
                neutral: ramp('neutral', [0, 50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950]),
                green: ramp('green', [50, 500, 600, 700]),
                amber: ramp('amber', [50, 500, 600]),
                red: ramp('red', [50, 500, 600, 700]),
                blue: ramp('blue', [50, 500, 600]),
                grade: {
                    a: 'var(--grade-a)',
                    b: 'var(--grade-b)',
                    c: 'var(--grade-c)',
                    d: 'var(--grade-d)',
                    e: 'var(--grade-e)',
                },
            },

            // Backgrounds: bg-canvas, bg-surface, bg-subtle, bg-brand, bg-brand-subtle, bg-feature ...
            backgroundColor: {
                canvas: 'var(--color-bg-canvas)',
                surface: 'var(--color-bg-surface)',
                subtle: 'var(--color-bg-subtle)',
                muted: 'var(--color-bg-muted)',
                brand: {
                    DEFAULT: 'var(--color-bg-brand)',
                    hover: 'var(--color-bg-brand-hover)',
                    subtle: 'var(--color-bg-brand-subtle)',
                },
                accent: {
                    DEFAULT: 'var(--color-bg-accent)',
                    hover: 'var(--color-bg-accent-hover)',
                },
                feature: 'var(--color-bg-feature)',
                success: {
                    DEFAULT: 'var(--color-bg-success)',
                    subtle: 'var(--color-bg-success-subtle)',
                },
                warning: {
                    DEFAULT: 'var(--color-bg-warning)',
                    subtle: 'var(--color-bg-warning-subtle)',
                },
                danger: {
                    DEFAULT: 'var(--color-bg-danger)',
                    subtle: 'var(--color-bg-danger-subtle)',
                },
                info: {
                    DEFAULT: 'var(--color-bg-info)',
                    subtle: 'var(--color-bg-info-subtle)',
                },
            },

            // Text: text-primary, text-secondary, text-tertiary, text-brand, text-danger ...
            textColor: {
                primary: 'var(--color-text-primary)',
                secondary: 'var(--color-text-secondary)',
                tertiary: 'var(--color-text-tertiary)',
                disabled: 'var(--color-text-disabled)',
                'on-brand': 'var(--color-text-on-brand)',
                brand: {
                    DEFAULT: 'var(--color-text-brand)',
                },
                'on-feature': {
                    DEFAULT: 'var(--color-text-on-feature)',
                    muted: 'var(--color-text-on-feature-muted)',
                },
                'feature-accent': 'var(--color-text-feature-accent)',
                success: 'var(--color-text-success)',
                warning: 'var(--color-text-warning)',
                danger: 'var(--color-text-danger)',
                info: 'var(--color-text-info)',
            },

            // Borders: border-subtle, border-default, border-strong, border-brand ...
            borderColor: {
                subtle: 'var(--color-border-subtle)',
                default: 'var(--color-border-default)',
                strong: 'var(--color-border-strong)',
                brand: {
                    DEFAULT: 'var(--color-border-brand)',
                },
                focus: 'var(--color-border-focus)',
                danger: 'var(--color-border-danger)',
            },

            // Corners, same as Figma: rounded-sm 8px, rounded-md 12px, rounded-lg 16px, rounded-xl 24px
            borderRadius: {
                sm: 'var(--radius-sm)',
                md: 'var(--radius-md)',
                lg: 'var(--radius-lg)',
                xl: 'var(--radius-xl)',
                full: 'var(--radius-full)',
            },

            // Shadows: shadow-card, shadow-md, shadow-lg
            boxShadow: {
                card: 'var(--shadow-card)',
                md: 'var(--shadow-md)',
                lg: 'var(--shadow-lg)',
            },
        },
    },
};
