// ==================== Phase 1: Streaming Implementation ====================
// 添加到 CodeMirrorEditor.vue 的 \u003cscript setup\u003e 部分

// Step 1: 更新状态变量（替换现有的第 456-458 行）
const wordCount = ref(0)
const aiLoading = ref(false)
const streamHandle = ref\u003cAbortController | null\u003e(null) // 用于中断流式生成
const streamingStatus = ref\u003cstring\u003e('') // 生成状态文本
const streamedCharCount = ref(0) // 已生成字符数
const previewBeforeUpdate = ref(true)

// Step 2: 添加 interruptStream 函数（在文件末尾任意位置）
function interruptStream() {
    if (streamHandle.value) {
        streamHandle.value.abort()
        streamHandle.value = null
        ElMessage.info('已停止生成')
    }
}

// Step 3: 添加 markDirty 辅助函数（如果不存在）
function markDirty() {
    if (!isDirty.value) {
        isDirty.value = true
        emit('update:dirty', true)
    }
}

// Step 4: 实现核心 executeAIGeneration 函数（替换 line 938 的调用）
async function executeAIGeneration(
    requestData: ContinuationRequest,
    isEdit: boolean,
    operationName: string
) {
    aiLoading.value = true
    streamingStatus.value = `正在${operationName}...`
    streamedCharCount.value = 0

    // 创建 AbortController
    const controller = new AbortController()
    streamHandle.value = controller

    // 保存当前光标位置
    const currentPos = view?.state.selection.main.head || getText().length
    const isAtEnd = currentPos === getText().length

    try {
        let accumulated = ''
        let chunkCount = 0
        const startTime = Date.now()

        // 调用流式 API
        await generateContinuationStreaming(
            requestData,
            (chunk) => {
                // 每次收到新内容
                accumulated += chunk
                chunkCount++
                streamedCharCount.value = accumulated.length

                // 实时追加到编辑器
                if (view && isAtEnd) {
                    const currentText = getText()
                    const newText = currentText + chunk

                    view.dispatch({
                        changes: {
                            from: currentText.length,
                            to: currentText.length,
                            insert: chunk
                        },
                        selection: { anchor: newText.length }
                    })

                    // 滚动到底部
                    view.dispatch({
                        effects: EditorView.scrollIntoView(newText.length, { y: 'end' })
                    })

                    // 更新字数
                    wordCount.value = computeWordCount(getText())
                }

                // 更新状态
                const elapsed = ((Date.now() - startTime) / 1000).toFixed(1)
                const speed = (accumulated.length / parseFloat(elapsed)).toFixed(0)
                streamingStatus.value = `${operationName}中... ${accumulated.length}字 (${speed}字/秒)`
            },
            controller.signal
        )

        // 完成
        ElMessage.success(`${operationName}完成！共生成 ${accumulated.length} 字`)
        markDirty() // 标记为已修改

    } catch (error: any) {
        if (error.name === 'AbortError') {
            ElMessage.info(`已停止${operationName}`)
        } else {
            console.error(`${operationName}失败:`, error)
            ElMessage.error(`${operationName}失败: ${error.message || '未知错误'}`)
        }
    } finally {
        aiLoading.value = false
        streamHandle.value = null
        streamingStatus.value = ''
        streamedCharCount.value = 0
    }
}
