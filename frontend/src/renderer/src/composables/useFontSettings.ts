import { ref, watch } from 'vue'

const FONT_FAMILY_KEY = 'novel-forge-font-family'
const FONT_SIZE_KEY = 'novel-forge-font-size'

export const DEFAULT_FONT_FAMILY = 'system-ui, -apple-system, sans-serif'
export const DEFAULT_FONT_SIZE = '14px'

export function useFontSettings() {
    const fontFamily = ref(localStorage.getItem(FONT_FAMILY_KEY) || DEFAULT_FONT_FAMILY)
    const fontSize = ref(localStorage.getItem(FONT_SIZE_KEY) || DEFAULT_FONT_SIZE)

    const applyFontSettings = () => {
        const html = document.documentElement
        html.style.setProperty('--el-font-family', fontFamily.value)
        html.style.setProperty('--font-family-base', fontFamily.value)
        html.style.setProperty('--el-font-size-base', fontSize.value)

        localStorage.setItem(FONT_FAMILY_KEY, fontFamily.value)
        localStorage.setItem(FONT_SIZE_KEY, fontSize.value)
    }

    // Initialize
    applyFontSettings()

    // Watch for changes
    watch([fontFamily, fontSize], applyFontSettings)

    return {
        fontFamily,
        fontSize,
        applyFontSettings
    }
}
