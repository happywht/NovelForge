import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useGlobalStatusStore = defineStore('globalStatus', () => {
    const isLoading = ref(false)
    const loadingMessage = ref('')
    const progress = ref(0) // 0-100

    function startLoading(message: string = '正在处理...') {
        isLoading.value = true
        loadingMessage.value = message
        progress.value = 0
    }

    function stopLoading() {
        isLoading.value = false
        loadingMessage.value = ''
        progress.value = 100
        setTimeout(() => {
            progress.value = 0
        }, 300)
    }

    function setProgress(value: number) {
        progress.value = Math.min(100, Math.max(0, value))
    }

    function setLoadingMessage(message: string) {
        loadingMessage.value = message
    }

    return {
        isLoading,
        loadingMessage,
        progress,
        startLoading,
        stopLoading,
        setProgress,
        setLoadingMessage
    }
})
