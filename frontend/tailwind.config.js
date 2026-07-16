/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        cb: {
          bg: '#05050a',
          surface: '#0a0a14',
          card: '#0f0f1a',
          'card-hover': '#141425',
          input: '#0a0a14',
          border: '#1a1a2e',
          'border-light': '#2a2a40',
          'border-glow': '#8C52FF',
          muted: '#5a5a7a',
          text: '#c8c8e0',
          'text-bright': '#e8e8ff',
          'text-glow': '#ffffff',
          neon: '#8C52FF',
          'neon-dim': '#6b3dc4',
          'neon-bright': '#a76bff',
          cyan: '#00f0ff',
          'cyan-dim': '#0090aa',
          pink: '#ff2d7b',
          'pink-dim': '#b8205a',
          gold: '#ffaa00',
          'gold-dim': '#cc8800',
          red: '#ff3355',
          'red-dim': '#cc2244',
          green: '#00ff88',
          'green-dim': '#00cc6a',
        },
      },
      boxShadow: {
        'neon': '0 0 15px rgba(140,82,255,0.3), 0 0 45px rgba(140,82,255,0.1)',
        'neon-sm': '0 0 8px rgba(140,82,255,0.2), 0 0 20px rgba(140,82,255,0.05)',
        'neon-lg': '0 0 20px rgba(140,82,255,0.4), 0 0 60px rgba(140,82,255,0.15), 0 0 100px rgba(140,82,255,0.05)',
        'cyan': '0 0 15px rgba(0,240,255,0.3), 0 0 45px rgba(0,240,255,0.1)',
        'cyan-sm': '0 0 8px rgba(0,240,255,0.2), 0 0 20px rgba(0,240,255,0.05)',
        'pink': '0 0 15px rgba(255,45,123,0.3), 0 0 45px rgba(255,45,123,0.1)',
        'pink-sm': '0 0 8px rgba(255,45,123,0.2), 0 0 20px rgba(255,45,123,0.05)',
        'gold': '0 0 15px rgba(255,170,0,0.3), 0 0 45px rgba(255,170,0,0.1)',
        'red': '0 0 15px rgba(255,51,85,0.3), 0 0 45px rgba(255,51,85,0.1)',
        'green': '0 0 15px rgba(0,255,136,0.3), 0 0 45px rgba(0,255,136,0.1)',
      },
      animation: {
        'glow-pulse': 'glow-pulse 2s ease-in-out infinite',
        'scan-line': 'scan-line 8s linear infinite',
        'flicker': 'flicker 0.15s infinite',
        'border-glow': 'border-glow 3s ease-in-out infinite',
        'fade-in': 'fade-in 0.2s ease-out',
        'slide-in': 'slide-in 0.2s ease-out',
      },
      keyframes: {
        'glow-pulse': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.6' },
        },
        'scan-line': {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100vh)' },
        },
        'flicker': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.8' },
        },
        'border-glow': {
          '0%, 100%': { borderColor: 'rgba(140,82,255,0.3)' },
          '50%': { borderColor: 'rgba(140,82,255,0.6)' },
        },
        'fade-in': {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-in': {
          '0%': { opacity: '0', transform: 'translateY(-8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}
