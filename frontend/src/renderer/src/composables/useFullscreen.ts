import { ref, onMounted, onUnmounted } from 'vue'

/**
 * Composable for managing fullscreen state and keyboard shortcuts
 */
export function useFullscreen() {
    const isFullscreen = ref(false)

    const toggleFullscreen = () => {
        isFullscreen.value = !isFullscreen.value
    }

    const exitFullscreen = () => {
        isFullscreen.value = false
    }

    const handleKeydown = (e: KeyboardEvent) => {
        // F11 for fullscreen toggle
        if (e.key === 'F11') {
            e.preventDefault()
            toggleFullscreen()
        }
        // Escape to exit fullscreen
        if (e.key === 'Escape' && isFullscreen.value) {
            exitFullscreen()
        }
    }

    onMounted(() => {
        window.addEventListener('keydown', handleKeydown)
    })

    onUnmounted(() => {
        window.removeEventListener('keydown', handleKeydown)
    })

    return {
        isFullscreen,
        toggleFullscreen,
        exitFullscreen
    }
}
