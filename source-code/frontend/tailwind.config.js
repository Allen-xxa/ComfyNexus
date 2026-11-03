/** @type {import('tailwindcss').Config} */
const typography = require('@tailwindcss/typography')

export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
          hover: 'hsl(var(--color-primary-hover))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        
        surface: {
          DEFAULT: 'hsl(var(--bg-surface))',
          hover: 'hsl(var(--bg-surface-hover))',
          active: 'hsl(var(--bg-surface-active))',
        },
        theater: 'hsl(var(--theater-backdrop))',
        content: {
          primary: 'hsl(var(--text-primary))',
          secondary: 'hsl(var(--text-secondary))',
          muted: 'hsl(var(--text-muted))',
        },
        'border-subtle': 'hsl(var(--border-subtle))',
        'border-strong': 'hsl(var(--border-strong))',
        brand: {
          DEFAULT: 'hsl(var(--color-primary))',
          hover: 'hsl(var(--color-primary-hover))',
        },
        danger: 'hsl(var(--color-danger))',
        success: {
          DEFAULT: 'hsl(var(--color-success))',
          foreground: 'hsl(var(--color-success-foreground, var(--color-success)))',
        },
        warning: {
          DEFAULT: 'hsl(var(--color-warning))',
          foreground: 'hsl(var(--color-warning-foreground, var(--color-warning)))',
        },
        info: 'hsl(var(--color-info))',

        'dark-primary': 'hsl(var(--bg-base))',
        'dark-secondary': 'hsl(var(--bg-surface))',
        'dark-tertiary': 'hsl(var(--bg-surface-hover))',
        'dark-bg-primary': 'hsl(var(--bg-base))',
        'dark-bg-secondary': 'hsl(var(--bg-surface))',
        'dark-bg-tertiary': 'hsl(var(--bg-surface-hover))',
        'dark-background': 'hsl(var(--bg-base))',
        'dark-surface': 'hsl(var(--bg-surface))',
        'dark-border': 'hsl(var(--border-strong))',
        'dark-text-primary': 'hsl(var(--text-primary))',
        'dark-text-secondary': 'hsl(var(--text-secondary))',
        'dark-text-tertiary': 'hsl(var(--text-muted))',
        'dark-foreground': 'hsl(var(--text-primary))',
        
        'plugin-primary': 'hsl(var(--color-primary))',
        'plugin-primary-dark': 'hsl(var(--color-primary-hover))',
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
        xl: "1rem",
        '2xl': "1.5rem",
        '3xl': "2rem",
      },
      boxShadow: {
        'soft': '0 4px 24px -8px rgba(0, 0, 0, 0.04)',
        'soft-md': '0 8px 32px -8px rgba(0, 0, 0, 0.06)',
        'soft-lg': '0 12px 40px -8px rgba(0, 0, 0, 0.08)',
        'plugin-card': '0 1px 3px hsl(var(--text-primary) / 0.1), 0 1px 2px hsl(var(--text-primary) / 0.06)',
        'plugin-card-hover': '0 10px 15px -3px hsl(var(--color-primary) / 0.1), 0 4px 6px -2px hsl(var(--color-primary) / 0.05)',
        'plugin-button': '0 1px 2px hsl(var(--color-primary) / 0.2)',
        'glass': '0 4px 16px hsl(var(--text-primary) / 0.1)',
        'glass-hover': '0 16px 40px hsl(var(--text-primary) / 0.15), 0 0 20px hsl(var(--color-primary) / 0.05)',
        'modal': '0 32px 80px hsl(var(--text-primary) / 0.4), inset 0 1px 0 hsl(var(--bg-surface) / 0.25)',
        'pagination': '0 4px 24px hsl(var(--text-primary) / 0.15)',
      },
      backgroundImage: {
        'gradient-primary': 'linear-gradient(135deg, hsl(var(--color-primary)) 0%, hsl(var(--color-primary-hover)) 100%)',
        'gradient-success': 'linear-gradient(135deg, hsl(var(--color-success)) 0%, hsl(160 84.1% 30%) 100%)',
        'gradient-card': 'linear-gradient(135deg, hsl(var(--color-primary) / 0.05) 0%, hsl(var(--color-primary-hover) / 0.05) 100%)',
        'gradient-logo': 'linear-gradient(135deg, hsl(var(--color-warning)), hsl(25 95% 53%))',
        'gradient-accent': 'linear-gradient(135deg, hsl(var(--color-primary) / 0.12), hsl(var(--color-primary-hover) / 0.04))',
        'gradient-header': 'linear-gradient(180deg, hsl(var(--bg-surface) / 0.03) 0%, transparent 100%)',
        'gradient-border-top': 'linear-gradient(90deg, transparent, hsl(var(--bg-surface) / 0.25), transparent)',
        'ambient-glow': 'radial-gradient(circle at 10% 10%, hsl(var(--color-primary) / 0.06), transparent 40vw), radial-gradient(circle at 90% 90%, hsl(270 70% 60% / 0.04), transparent 40vw)',
      },
      backdropBlur: {
        xs: '2px',
        sm: '4px',
        DEFAULT: '8px',
        md: '12px',
        lg: '16px',
        xl: '24px',
        '2xl': '40px',
        '3xl': '64px',
      },
      transitionDuration: {
        '400': '400ms',
      },
      transitionTimingFunction: {
        'smooth': 'cubic-bezier(0.25, 0.8, 0.25, 1)',
        'bounce': 'cubic-bezier(0.34, 1.56, 0.64, 1)',
      },
      animation: {
        'fade-in': 'fadeIn 0.4s cubic-bezier(0.25, 0.8, 0.25, 1)',
        'scale-in': 'scaleIn 0.4s cubic-bezier(0.25, 0.8, 0.25, 1)',
        'slide-up': 'slideUp 0.4s cubic-bezier(0.25, 0.8, 0.25, 1)',
        'animate-in': 'animateIn 0.2s ease-out',
        'fade-in-0': 'fadeIn0 0.2s ease-out',
        'zoom-in-95': 'zoomIn95 0.2s ease-out',
        'slide-in-from-bottom-2': 'slideInFromBottom2 0.2s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        scaleIn: {
          '0%': { transform: 'scale(0.96) translateY(20px)', opacity: '0' },
          '100%': { transform: 'scale(1) translateY(0)', opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        animateIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        fadeIn0: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        zoomIn95: {
          '0%': { transform: 'scale(0.95)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
        slideInFromBottom2: {
          '0%': { transform: 'translateY(8px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
    },
  },
  plugins: [
    typography(),
  ],
}
