<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { ElMessage } from 'element-plus'
import AssistantPanel from './AssistantPanel.vue'
import ContextPanel from '@renderer/components/panels/ContextPanel.vue'
import ChapterToolsPanel from '@renderer/components/panels/ChapterToolsPanel.vue'
import OutlinePanel from '@renderer/components/panels/OutlinePanel.vue'
import HistoryPanel from '@renderer/components/panels/HistoryPanel.vue'
import { useCardStore } from '@renderer/stores/useCardStore'
import { useProjectStore } from '@renderer/stores/useProjectStore'
import { useAssistantStore } from '@renderer/stores/useAssistantStore'
import { getCardSchema } from '@renderer/api/setting'
import { getCardAIParams } from '@renderer/api/cards'
import { useSuggestionsStore } from '@renderer/stores/useSuggestionsStore'
import SuggestionsPanel from '@renderer/components/editors/cm-editor/SuggestionsPanel.vue'

const props = defineProps<{
  width: number
  activeCard: any
  prefetchedContext: any
}>()

const emit = defineEmits<{
  (e: 'jump-to-card', payload: { projectId: number; cardId: number }): void
  (e: 'history-restored', content: string): void
}>()

const cardStore = useCardStore()
const projectStore = useProjectStore()
const assistantStore = useAssistantStore()
const suggestionsStore = useSuggestionsStore()
const { cards } = storeToRefs(cardStore)
const { suggestions } = storeToRefs(suggestionsStore)

const activeRightTab = ref('assistant')
const assistantResolvedContext = ref<string>('')
const assistantEffectiveSchema = ref<any>(null)
const assistantSelectionCleared = ref<boolean>(false)
const assistantParams = ref<{
  llm_config_id: number | null
  prompt_name: string | null
  temperature: number | null
  max_tokens: number | null
  timeout: number | null
}>({
  llm_config_id: null,
  prompt_name: '灵感对话',
  temperature: null,
  max_tokens: null,
  timeout: null
})

// 判断当前是否为章节正文卡片
const isChapterContent = computed(() => {
  return props.activeCard?.card_type?.name === '章节正文'
})

// 章节信息提取
const chapterVolumeNumber = computed(() => {
  if (!isChapterContent.value) return null
  const content: any = props.activeCard?.content || {}
  return content.volume_number ?? null
})

const chapterChapterNumber = computed(() => {
  if (!isChapterContent.value) return null
  const content: any = props.activeCard?.content || {}
  return content.chapter_number ?? null
})

const chapterParticipants = computed(() => {
  if (!isChapterContent.value) return []
  const content: any = props.activeCard?.content || {}
  const list = content.entity_list || []
  if (Array.isArray(list)) {
    return list
      .map((x: any) => (typeof x === 'string' ? x : x?.name || ''))
      .filter(Boolean)
      .slice(0, 6)
  }
  return []
})

async function refreshAssistantContext() {
  try {
    const card = assistantSelectionCleared.value ? null : (props.activeCard as any)
    if (!card) {
      assistantResolvedContext.value = ''
      assistantEffectiveSchema.value = null
      return
    }
    const { resolveTemplate } = await import('@renderer/services/contextResolver')
    const resolved = resolveTemplate({
      template: card.ai_context_template || '',
      cards: cards.value,
      currentCard: card
    })
    assistantResolvedContext.value = resolved
    const resp = await getCardSchema(card.id)
    assistantEffectiveSchema.value = resp?.effective_schema || resp?.json_schema || null
    try {
      const ai = await getCardAIParams(card.id)
      const eff = (ai?.effective_params || {}) as any
      assistantParams.value = {
        llm_config_id: eff.llm_config_id ?? null,
        prompt_name: (eff.prompt_name ?? '灵感对话') as any,
        temperature: eff.temperature ?? null,
        max_tokens: eff.max_tokens ?? null,
        timeout: eff.timeout ?? null
      }
    } catch {
      const p = (card?.ai_params || {}) as any
      assistantParams.value = {
        llm_config_id: p.llm_config_id ?? null,
        prompt_name: (p.prompt_name ?? '灵感对话') as any,
        temperature: p.temperature ?? null,
        max_tokens: p.max_tokens ?? null,
        timeout: p.timeout ?? null
      }
    }
  } catch {
    assistantResolvedContext.value = ''
  }
}

watch(
  () => props.activeCard,
  () => {
    if (!assistantSelectionCleared.value) refreshAssistantContext()
  }
)

function resetAssistantSelection() {
  assistantSelectionCleared.value = true
  assistantResolvedContext.value = ''
  assistantEffectiveSchema.value = null
}

const assistantFinalize = async (summary: string) => {
  try {
    const card = props.activeCard as any
    if (!card) return
    assistantStore.finalizeAssistant(card.id, summary)
    ElMessage.success('已发送定稿要点到编辑器页')
  } catch {}
}

function handleJumpToCard(payload: { projectId: number; cardId: number }) {
  emit('jump-to-card', payload)
}

function handleHistoryRestored(content: string) {
  emit('history-restored', content)
}

defineExpose({
  refreshAssistantContext
})
</script>

<template>
  <el-aside class="sidebar assistant-sidebar" :style="{ width: width + 'px' }">
    <!-- 章节正文卡片：显示4个Tab -->
    <template v-if="isChapterContent">
      <el-tabs v-model="activeRightTab" type="card" class="right-tabs">
        <el-tab-pane label="助手" name="assistant">
          <AssistantPanel
            :resolved-context="assistantResolvedContext"
            :llm-config-id="assistantParams.llm_config_id as any"
            :prompt-name="'灵感对话'"
            :temperature="assistantParams.temperature as any"
            :max_tokens="assistantParams.max_tokens as any"
            :timeout="assistantParams.timeout as any"
            :effective-schema="assistantEffectiveSchema"
            :generation-prompt-name="assistantParams.prompt_name as any"
            :current-card-title="assistantSelectionCleared ? '' : (activeCard?.title as any)"
            :current-card-content="assistantSelectionCleared ? null : (activeCard?.content as any)"
            @refresh-context="refreshAssistantContext"
            @reset-selection="resetAssistantSelection"
            @finalize="assistantFinalize"
            @jump-to-card="handleJumpToCard"
          />
        </el-tab-pane>

        <el-tab-pane label="参与实体" name="context">
          <ContextPanel
            :project-id="projectStore.currentProject?.id"
            :prefetched="prefetchedContext"
            :volume-number="chapterVolumeNumber"
            :chapter-number="chapterChapterNumber"
            :participants="chapterParticipants"
          />
        </el-tab-pane>

        <el-tab-pane label="提取" name="extract">
          <ChapterToolsPanel />
        </el-tab-pane>

        <el-tab-pane label="大纲" name="outline">
          <OutlinePanel
            :active-card="activeCard"
            :volume-number="chapterVolumeNumber"
            :chapter-number="chapterChapterNumber"
          />
        </el-tab-pane>

        <el-tab-pane name="suggestions">
          <template #label>
            <el-badge
              :value="suggestions.length"
              :hidden="suggestions.length === 0"
              :max="99"
              class="suggestion-badge"
            >
              建议
            </el-badge>
          </template>
          <SuggestionsPanel
            :context="{
              participants: chapterParticipants,
              volume_number: chapterVolumeNumber,
              chapter_number: chapterChapterNumber
            }"
          />
        </el-tab-pane>

        <el-tab-pane label="历史" name="history">
          <HistoryPanel :card-id="activeCard?.id" @restored="handleHistoryRestored" />
        </el-tab-pane>
      </el-tabs>
    </template>

    <!-- 其他卡片：仅显示助手 -->
    <AssistantPanel
      v-else
      :resolved-context="assistantResolvedContext"
      :llm-config-id="assistantParams.llm_config_id as any"
      :prompt-name="'灵感对话'"
      :temperature="assistantParams.temperature as any"
      :max_tokens="assistantParams.max_tokens as any"
      :timeout="assistantParams.timeout as any"
      :effective-schema="assistantEffectiveSchema"
      :generation-prompt-name="assistantParams.prompt_name as any"
      :current-card-title="assistantSelectionCleared ? '' : (activeCard?.title as any)"
      :current-card-content="assistantSelectionCleared ? null : (activeCard?.content as any)"
      @refresh-context="refreshAssistantContext"
      @reset-selection="resetAssistantSelection"
      @finalize="assistantFinalize"
      @jump-to-card="handleJumpToCard"
    />
  </el-aside>
</template>

<style scoped>
.sidebar {
  display: flex;
  flex-direction: column;
  background-color: var(--el-fill-color-lighter);
  transition: width 0.2s;
  flex-shrink: 0;
  overflow: hidden;
}

.assistant-sidebar {
  border-left: none;
  background: transparent;
  flex-shrink: 0;
  padding: 16px 8px 16px 0;
}

.right-tabs {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--el-bg-color);
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  overflow: hidden;
}
.right-tabs :deep(.el-tabs__header) {
  margin: 0;
  border-bottom: 1px solid var(--el-border-color-light);
  padding: 12px 12px 0 12px;
  background: var(--el-fill-color-lighter);
}
.right-tabs :deep(.el-tabs__nav-wrap) {
  padding: 0;
}
.right-tabs :deep(.el-tabs__item) {
  font-size: 13px;
  font-weight: 500;
  padding: 0 16px;
  height: 36px;
  line-height: 36px;
}
.right-tabs :deep(.el-tabs__item.is-active) {
  color: var(--el-color-primary);
}
.right-tabs :deep(.el-tabs__content) {
  flex: 1;
  overflow: hidden;
  padding: 0;
}
.right-tabs :deep(.el-tab-pane) {
  height: 100%;
  overflow-y: auto;
}
</style>
