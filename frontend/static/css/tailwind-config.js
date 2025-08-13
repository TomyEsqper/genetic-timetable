// Configuración local de Tailwind CSS
// Este archivo reemplaza el CDN de Tailwind para desarrollo local

tailwind.config = {
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
        },
        success: {
          50: '#f0fdf4',
          100: '#dcfce7',
          200: '#bbf7d0',
          300: '#86efac',
          400: '#4ade80',
          500: '#22c55e',
          600: '#16a34a',
          700: '#15803d',
          800: '#166534',
          900: '#14532d',
        },
        warning: {
          50: '#fffbeb',
          100: '#fef3c7',
          200: '#fde68a',
          300: '#fcd34d',
          400: '#fbbf24',
          500: '#f59e0b',
          600: '#d97706',
          700: '#b45309',
          800: '#92400e',
          900: '#78350f',
        },
        error: {
          50: '#fef2f2',
          100: '#fee2e2',
          200: '#fecaca',
          300: '#fca5a5',
          400: '#f87171',
          500: '#ef4444',
          600: '#dc2626',
          700: '#b91c1c',
          800: '#991b1b',
          900: '#7f1d1d',
        }
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-in-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'bounce-gentle': 'bounceGentle 2s infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        bounceGentle: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-5px)' },
        }
      }
    }
  },
  plugins: [
    // Plugin personalizado para tooltips
    function({ addUtilities }) {
      const newUtilities = {
        '.tooltip': {
          position: 'relative',
          cursor: 'help',
        },
        '.tooltip::after': {
          content: 'attr(data-tooltip)',
          position: 'absolute',
          bottom: '100%',
          left: '50%',
          transform: 'translateX(-50%)',
          backgroundColor: '#1f2937',
          color: 'white',
          padding: '0.5rem 0.75rem',
          borderRadius: '0.5rem',
          fontSize: '0.875rem',
          whiteSpace: 'nowrap',
          zIndex: '50',
          opacity: '0',
          pointerEvents: 'none',
          transition: 'opacity 0.2s ease-in-out',
        },
        '.tooltip:hover::after': {
          opacity: '1',
        }
      }
      addUtilities(newUtilities)
    }
  ]
}

// Configuración adicional para componentes específicos
if (typeof window !== 'undefined') {
  // Configuración para formularios
  window.formConfig = {
    inputFocus: 'ring-2 ring-blue-500 border-blue-500',
    inputError: 'ring-2 ring-red-500 border-red-500',
    inputSuccess: 'ring-2 ring-green-500 border-green-500',
    buttonPrimary: 'bg-blue-600 hover:bg-blue-700 text-white',
    buttonSuccess: 'bg-green-600 hover:bg-green-700 text-white',
    buttonWarning: 'bg-yellow-600 hover:bg-yellow-700 text-white',
    buttonError: 'bg-red-600 hover:bg-red-700 text-white'
  }
  
  console.log('🎨 Tailwind CSS configurado localmente')
} 