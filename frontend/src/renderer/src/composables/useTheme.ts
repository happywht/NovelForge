import { ref, watch } from 'vue'

const THEME_KEY = 'novel-forge-theme'

export function useTheme() {
    const isDark = ref(localStorage.getItem(THEME_KEY) === 'dark')

    const toggleTheme = () => {
        isDark.value = !isDark.value
    }

    const applyTheme = () => {
        const html = document.documentElement
        if (isDark.value) {
            html.classList.add('dark')
            localStorage.setItem(THEME_KEY, 'dark')
        } else {
            html.classList.remove('dark')
            localStorage.setItem(THEME_KEY, 'light')
        }
    }

    // Initialize
    applyTheme()

    // Watch for changes
    watch(isDark, applyTheme)

    return {
        isDark,
        toggleTheme
    }
}
