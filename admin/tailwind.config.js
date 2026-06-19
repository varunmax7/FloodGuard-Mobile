/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{ts,tsx,js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Brand
        'navy-900': '#0B2545',
        'navy-700': '#13315C',
        'blue-600': '#2563EB',
        // Risk
        'risk-low': '#22C55E',
        'risk-moderate': '#FACC15',
        'risk-high': '#F97316',
        'risk-severe': '#EF4444',
        // Text
        'text-primary': '#0F172A',
        'text-muted': '#64748B',
        // Alerts
        'severe-bg': '#FEF2F2',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        'card': '16px',
      },
      boxShadow: {
        'card': '0 2px 8px rgba(15, 23, 42, 0.08)',
      },
      backgroundImage: {
        'navy-gradient': 'linear-gradient(180deg, #0B2545 0%, #13315C 100%)',
      },
    },
  },
  plugins: [],
}
