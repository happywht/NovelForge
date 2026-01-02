import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { generateContinuationStreaming } from '@renderer/api/ai'
import type { ContinuationRequest } from '@renderer/api/ai'
import { extractDynamicInfoOnly, extractRelationsOnly } from '@renderer/api/memory'
import { resolveTemplate } from '@renderer/services/contextResolver'

export interface EditorContext {
  getText: () => string
  setText: (text: string) => void
  appendAtEnd: (text: string) => void
  getSelectedText: () => { text: string; from: number; to: number } | null
  replaceSelectedText: (text: string) => void
  setHighlight: (from: number, to: number) => void
  clearHighlight: () => void
  updateHighlight: (from: number, to: number) => void
  getCard: () => any
  getCards: () => any[]
  getPrefetched: () => any
  getContextParams: () => any
  resolveLlmConfigId: () => number | undefined
  resolveSampling: () => any
  formatFactsFromContext: (ctx: any) => string
  extractParticipantsForCurrentChapter: () => string[]
  dispatch: (specs: any) => void
}

export function useEditorAI(ctx: EditorContext) {
  const aiLoading = ref(false)
  const streamHandle = ref<any>(null)
  const streamingStatus = ref('')
  const streamedCharCount = ref(0)

  function interruptStream() {
    if (streamHandle.value) {
      streamHandle.value.cancel()
      streamHandle.value = null
      aiLoading.value = false
      streamingStatus.value = '已停止'
      ElMessage.info('已停止生成')
    }
  }

  async function executeAIGeneration(
    requestData: ContinuationRequest,
    replaceMode = false,
    taskName = 'AI生成',
    replaceFrom?: number,
    replaceTo?: number
  ) {
    if (aiLoading.value) return
    aiLoading.value = true
    streamingStatus.value = '正在连接...'
    streamedCharCount.value = 0
    ctx.clearHighlight()

    let accumulated = ''
    let currentOffset = 0
    const startTime = Date.now()

    if (replaceMode && replaceFrom !== undefined && replaceTo !== undefined) {
      currentOffset = replaceFrom
      // 先清空选中区域
      ctx.dispatch({
        changes: { from: replaceFrom, to: replaceTo, insert: '' }
      })
    } else {
      // 续写模式，从末尾开始
      currentOffset = ctx.getText().length
    }

    const startOffset = currentOffset

    try {
      streamHandle.value = generateContinuationStreaming(
        requestData,
        (delta) => {
          accumulated += delta
          streamedCharCount.value = accumulated.length

          // 计算速度
          const elapsed = (Date.now() - startTime) / 1000
          const speed = elapsed > 0 ? (accumulated.length / elapsed).toFixed(1) : '0'
          streamingStatus.value = `正在生成... ${accumulated.length}字 (${speed}字/秒)`

          // 增量更新编辑器
          ctx.dispatch({
            changes: { from: currentOffset, to: currentOffset, insert: delta },
            // 如果是续写模式，保持光标在末尾
            selection: !replaceMode ? { anchor: currentOffset + delta.length } : undefined
          })

          // 更新高亮区域
          ctx.updateHighlight(startOffset, currentOffset + delta.length)

          currentOffset += delta.length
        },
        () => {
          aiLoading.value = false
          streamHandle.value = null
          streamingStatus.value = '生成完成'
          ElMessage.success(`${taskName}完成，共 ${accumulated.length} 字`)
          setTimeout(() => {
            ctx.clearHighlight()
          }, 2000)
        },
        (err) => {
          console.error(`[AI] ${taskName}失败:`, err)
          aiLoading.value = false
          streamHandle.value = null
          streamingStatus.value = '生成失败'
          ElMessage.error(`${taskName}失败: ${err.message || '未知错误'}`)
        }
      )
    } catch (e: any) {
      aiLoading.value = false
      streamingStatus.value = '启动失败'
      ElMessage.error(`启动${taskName}失败: ${e.message}`)
    }
  }

  async function executeAIEdit(promptName: string, userRequirement?: string) {
    const selectedText = ctx.getSelectedText()
    if (!selectedText) {
      ElMessage.warning(`请先选中要${promptName}的内容`)
      return
    }

    const llmConfigId = ctx.resolveLlmConfigId()
    if (!llmConfigId) {
      ElMessage.error('请先设置有效的模型ID')
      return
    }

    const fullText = ctx.getText()
    const card = ctx.getCard()
    const cards = ctx.getCards()

    let resolvedContextTemplate = ''
    try {
      const aiContextTemplate = card?.ai_context_template || ''
      if (aiContextTemplate) {
        resolvedContextTemplate = resolveTemplate({
          template: aiContextTemplate,
          cards: cards,
          currentCard: { ...card, content: { ...card.content, content: fullText } } as any
        })
      }
    } catch (e) {
      console.error('Failed to resolve ai_context_template:', e)
    }

    let factsText = ''
    try {
      factsText = ctx.formatFactsFromContext(ctx.getPrefetched())
    } catch {}

    const contextParts: string[] = []
    if (resolvedContextTemplate) contextParts.push(`【引用上下文】\n${resolvedContextTemplate}`)
    if (factsText) contextParts.push(`【事实子图】\n${factsText}`)
    if (userRequirement) contextParts.push(`【用户要求】\n${userRequirement}`)

    const beforeText = fullText.substring(0, selectedText.from)
    if (beforeText.trim()) {
      const truncatedBefore =
        beforeText.length > 1000 ? '...' + beforeText.slice(-1000) : beforeText
      contextParts.push(`【上文】\n${truncatedBefore}`)
    }

    contextParts.push(`【需要${promptName}的内容】\n${selectedText.text}`)

    const afterText = fullText.substring(selectedText.to)
    if (afterText.trim()) {
      const truncatedAfter = afterText.length > 500 ? afterText.slice(0, 500) + '...' : afterText
      contextParts.push(`【下文】\n${truncatedAfter}`)
    }

    const requestData: ContinuationRequest = {
      previous_content: '',
      context_info: contextParts.join('\n\n'),
      llm_config_id: llmConfigId,
      stream: true,
      prompt_name: promptName,
      append_continuous_novel_directive: false,
      ...((ctx.getContextParams() || {}) as any)
    } as any

    try {
      const sampling = ctx.resolveSampling()
      if (sampling.temperature != null) (requestData as any).temperature = sampling.temperature
      if (sampling.max_tokens != null) (requestData as any).max_tokens = sampling.max_tokens
      if (sampling.timeout != null) (requestData as any).timeout = sampling.timeout
    } catch {}

    try {
      const participants = ctx.extractParticipantsForCurrentChapter()
      if (participants.length) (requestData as any).participants = participants
    } catch {}

    executeAIGeneration(requestData, true, promptName, selectedText.from, selectedText.to)
  }

  async function extractDynamicInfoWithLlm(llmConfigId: number, cardId: number, text: string) {
    try {
      aiLoading.value = true
      const data = await extractDynamicInfoOnly({
        card_id: cardId,
        text: text,
        llm_config_id: llmConfigId
      })
      return data
    } catch (e: any) {
      ElMessage.error('提取动态信息失败: ' + e.message)
      throw e
    } finally {
      aiLoading.value = false
    }
  }

  async function extractRelationsWithLlm(
    llmConfigId: number,
    text: string,
    participants: any[],
    vol: number,
    ch: number
  ) {
    try {
      aiLoading.value = true
      const data = await extractRelationsOnly({
        text,
        participants,
        llm_config_id: llmConfigId,
        volume_number: vol,
        chapter_number: ch
      } as any)
      return data
    } catch (e: any) {
      ElMessage.error('关系抽取失败: ' + e.message)
      throw e
    } finally {
      aiLoading.value = false
    }
  }

  return {
    aiLoading,
    streamHandle,
    streamingStatus,
    streamedCharCount,
    interruptStream,
    executeAIGeneration,
    executeAIEdit,
    extractDynamicInfoWithLlm,
    extractRelationsWithLlm
  }
}
