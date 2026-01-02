import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { UpdateDynamicInfoOutput, RelationExtractionOutput } from '@renderer/api/memory'
import { updateDynamicInfoOnly, ingestRelationsFromPreview } from '@renderer/api/memory'
import { ElMessage } from 'element-plus'
import { useCardStore } from './useCardStore'

export interface Suggestion {
  id: string
  type: 'dynamic_info' | 'relation'
  title: string
  description: string
  data: any
  timestamp: number
}

export const useSuggestionsStore = defineStore('suggestions', () => {
  const suggestions = ref<Suggestion[]>([])
  const loading = ref(false)
  const cardStore = useCardStore()

  function addDynamicInfoSuggestion(data: UpdateDynamicInfoOutput): void {
    const id = `dyn_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
    suggestions.value.push({
      id,
      type: 'dynamic_info',
      title: '角色属性变更建议',
      description: `检测到 ${data.info_list.length} 个角色的属性可能发生了变化`,
      data,
      timestamp: Date.now()
    })
  }

  function addRelationSuggestion(data: RelationExtractionOutput): void {
    const id = `rel_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
    suggestions.value.push({
      id,
      type: 'relation',
      title: '关系更新建议',
      description: `检测到新的实体关系或别名`,
      data,
      timestamp: Date.now()
    })
  }

  async function approveSuggestion(suggestion: Suggestion, projectId: number, context?: { participants?: string[], volume_number?: number, chapter_number?: number }): Promise<void> {
    loading.value = true
    try {
      if (suggestion.type === 'dynamic_info') {
        const resp = await updateDynamicInfoOnly({
          project_id: projectId,
          data: suggestion.data,
          queue_size: 5
        })
        if (resp.success) {
          ElMessage.success(`已更新 ${resp.updated_card_count} 个角色卡`)
          removeSuggestion(suggestion.id)
          // 刷新卡片列表以同步更新内容
          await cardStore.fetchCards(projectId)
        }
      } else if (suggestion.type === 'relation') {
        const participants = (context?.participants || []).map((p: any) => {
          if (typeof p === 'string') return { name: p, type: '角色' }
          return { name: p.name || '', type: p.type || '角色' }
        })
        const resp = await ingestRelationsFromPreview({
          project_id: projectId,
          data: suggestion.data,
          participants,
          volume_number: context?.volume_number,
          chapter_number: context?.chapter_number
        })
        ElMessage.success(`已写入 ${resp.written} 条关系/别名`)
        removeSuggestion(suggestion.id)
        // 刷新卡片列表以同步更新内容
        await cardStore.fetchCards(projectId)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      ElMessage.error(`应用建议失败: ${msg}`)
    } finally {
      loading.value = false
    }
  }

  function removeSuggestion(id: string): void {
    const index = suggestions.value.findIndex(s => s.id === id)
    if (index !== -1) {
      suggestions.value.splice(index, 1)
    }
  }

  function clearAll(): void {
    suggestions.value = []
  }

  return {
    suggestions,
    loading,
    addDynamicInfoSuggestion,
    addRelationSuggestion,
    approveSuggestion,
    removeSuggestion,
    clearAll
  }
})
