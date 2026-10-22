const ramp = (name, steps) =>
  Object.fromEntries(steps.map((s) => [s, `var(--${name}-${s})`]));

tailwind.config = {
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        display: ['Fraunces', 'Georgia', 'serif'],
      },
      colors: {
        brand: ramp('brand', [50, 100, 200, 300, 400, 500, 600, 700, 800, 900]),
        neutral: ramp('neutral', [0, 50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950]),
        green: ramp('green', [50, 500, 600, 700]),
        amber: ramp('amber', [50, 500, 600]),
        red: ramp('red', [50, 500, 600, 700]),
        blue: ramp('blue', [50, 500, 600]),
      },
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
        success: { DEFAULT: 'var(--color-bg-success)', subtle: 'var(--color-bg-success-subtle)' },
        warning: { DEFAULT: 'var(--color-bg-warning)', subtle: 'var(--color-bg-warning-subtle)' },
        danger: { DEFAULT: 'var(--color-bg-danger)', subtle: 'var(--color-bg-danger-subtle)' },
        info: { DEFAULT: 'var(--color-bg-info)', subtle: 'var(--color-bg-info-subtle)' },
      },
      textColor: {
        primary: 'var(--color-text-primary)',
        secondary: 'var(--color-text-secondary)',
        tertiary: 'var(--color-text-tertiary)',
        disabled: 'var(--color-text-disabled)',
        'on-brand': 'var(--color-text-on-brand)',
        brand: { DEFAULT: 'var(--color-text-brand)' },
        success: 'var(--color-text-success)',
        warning: 'var(--color-text-warning)',
        danger: 'var(--color-text-danger)',
        info: 'var(--color-text-info)',
      },
      borderColor: {
        subtle: 'var(--color-border-subtle)',
        strong: 'var(--color-border-strong)',
        brand: { DEFAULT: 'var(--color-border-brand)' },
        focus: 'var(--color-border-focus)',
        danger: 'var(--color-border-danger)',
      },
    },
  },
};
