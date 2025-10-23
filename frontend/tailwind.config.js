/** @type {import('tailwindcss').Config} */
export default {
	content: ['./src/**/*.{html,js,svelte,ts}'],
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
				secondary: {
					500: '#f59e0b',
				},
				success: {
					500: '#10b981',
				},
				warning: {
					500: '#f59e0b',
				},
				error: {
					500: '#ef4444',
				},
				environmental: '#8b5cf6', // purple
				molecular: '#06b6d4', // cyan
				biomarker: '#ec4899', // pink
				genetic: '#f97316', // orange
			},
		},
	},
	plugins: [],
}
