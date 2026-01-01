<template>
  <div class="chapter-studio">
    <div class="toolbar">
      <div class="toolbar-row">
        <!-- 编辑功能组 -->
        <div class="toolbar-group">
          <span class="group-label">编辑</span>
          <el-dropdown @command="(c:any) => fontSize = c" size="small">
            <el-button size="small">
              {{ fontSize }}px
              <el-icon class="el-icon--right"><arrow-down /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item :command="14">小 (14px)</el-dropdown-item>
                <el-dropdown-item :command="16">中 (16px)</el-dropdown-item>
                <el-dropdown-item :command="18">大 (18px)</el-dropdown-item>
                <el-dropdown-item :command="20">特大 (20px)</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          
          <el-dropdown @command="(c:any) => lineHeight = c" size="small">
            <el-button size="small">
              {{ lineHeight }}
              <el-icon class="el-icon--right"><arrow-down /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item :command="1.4">紧凑</el-dropdown-item>
                <el-dropdown-item :command="1.6">适中</el-dropdown-item>
                <el-dropdown-item :command="1.8">舒适</el-dropdown-item>
                <el-dropdown-item :command="2.0">宽松</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>

        <div class="toolbar-divider"></div>
        
        <!-- AI功能组 -->
        <div class="toolbar-group">
          <span class="group-label">AI</span>
          <el-button type="primary" size="small" :loading="aiLoading" @click="executeAIContinuation">
            <el-icon><MagicStick /></el-icon> 续写
          </el-button>
          
          <el-button-group size="small">
            <el-button plain :loading="aiLoading" @click="executePolish">
              <el-icon><Document /></el-icon> 润色
            </el-button>
            <el-dropdown @command="handlePolishPromptChange" trigger="click">
              <el-button plain :loading="aiLoading">
                <el-icon><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item 
                    v-for="p in polishPrompts" 
                    :key="p" 
                    :command="p"
                    :class="{ 'is-selected': p === currentPolishPrompt }"
                  >
                    <div class="prompt-item">
                      <span>{{ p }}</span>
                      <el-icon v-if="p === currentPolishPrompt" class="check-icon"><Select /></el-icon>
                    </div>
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </el-button-group>
          
          <el-button-group size="small">
            <el-button plain :loading="aiLoading" @click="executeExpand">
              <el-icon><MagicStick /></el-icon> 扩写
            </el-button>
            <el-dropdown @command="handleExpandPromptChange" trigger="click">
              <el-button plain :loading="aiLoading">
                <el-icon><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item 
                    v-for="p in expandPrompts" 
                    :key="p" 
                    :command="p"
                    :class="{ 'is-selected': p === currentExpandPrompt }"
                  >
                    <div class="prompt-item">
                      <span>{{ p }}</span>
                      <el-icon v-if="p === currentExpandPrompt" class="check-icon"><Select /></el-icon>
                    </div>
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </el-button-group>
          
          <el-button type="danger" plain size="small" :disabled="!streamHandle" @click="interruptStream">
            <el-icon><CircleClose /></el-icon> 中断
          </el-button>

          <!-- 流式状态显示 -->
          <div v-if="aiLoading && streamingStatus" class="streaming-status">
            <el-icon class="is-loading"><Loading /></el-icon>
            <span class="status-text">{{ streamingStatus }}</span>
          </div>
          
          <!-- AI模型配置 -->
          <AIPerCardParams :card-id="props.card.id" :card-type-name="props.card.card_type?.name" />
        </div>
      </div>
    </div>

    <div class="editor-content-wrapper">
      <div class="chapter-header">
        <div class="title-section">
          <h1 
            class="chapter-title" 
            contenteditable="true"
            @blur="handleTitleBlur"
            @keydown.enter.prevent="handleTitleEnter"
            ref="titleElement"
          >{{ localCard.title }}</h1>
          <div class="title-meta">
            <el-icon class="word-count-icon"><Timer /></el-icon>
            <span class="word-count-text">{{ wordCount }} 字</span>
          </div>
        </div>
      </div>

      <div ref="cmRoot" class="editor-content"></div>
    </div>

    <!-- 右键快速编辑菜单 -->
    <EditorContextMenu
      v-model:requirement="contextMenu.userRequirement"
      :visible="contextMenu.visible"
      :expanded="contextMenu.expanded"
      :x="contextMenu.x"
      :y="contextMenu.y"
      :ai-loading="aiLoading"
      @expand="expandContextMenu"
      @polish="handleContextMenuPolish"
      @expand-text="handleContextMenuExpand"
      @close="closeContextMenu"
    />

    <!-- 预览对话框 -->
    <EditorDialogs
      v-model:previewVisible="previewDialogVisible"
      v-model:relationsVisible="relationsPreviewVisible"
      :preview-data="previewData"
      :relations-preview="relationsPreview"
      @confirm-dynamic="confirmApplyUpdates"
      @confirm-relations="confirmIngestRelationsFromPreview"
      @remove-item="removePreviewItem"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { storeToRefs } from 'pinia'
import { useCardStore } from '@renderer/stores/useCardStore'
import { useProjectStore } from '@renderer/stores/useProjectStore'
import { usePerCardAISettingsStore, type PerCardAIParams } from '@renderer/stores/usePerCardAISettingsStore'
import { useEditorStore } from '@renderer/stores/useEditorStore'
import type { CardRead, CardUpdate } from '@renderer/api/cards'
import { getAIConfigOptions, type AIConfigOptions, type ContinuationRequest } from '@renderer/api/ai'
import { getCardAIParams } from '@renderer/api/setting'
import { updateDynamicInfoOnly, type UpdateDynamicInfoOutput, ingestRelationsFromPreview, type RelationExtractionOutput } from '@renderer/api/memory'
import { ArrowDown, Document, MagicStick, CircleClose, Timer, Select, Loading } from '@element-plus/icons-vue'
import AIPerCardParams from '../common/AIPerCardParams.vue'
import { resolveTemplate } from '@renderer/services/contextResolver'

import { EditorState, StateEffect, StateField } from '@codemirror/state'
import { EditorView, keymap, Decoration, DecorationSet } from '@codemirror/view'
import { defaultKeymap, history, historyKeymap, insertNewline } from '@codemirror/commands'

// 新组件和 Composable
import EditorDialogs from './cm-editor/EditorDialogs.vue'
import EditorContextMenu from './cm-editor/EditorContextMenu.vue'
import { useEditorAI } from './cm-editor/useEditorAI'

const props = defineProps<{ 
  card: CardRead; 
  chapter?: any; 
  prefetched?: any | null; 
  contextParams?: { 
    project_id?: number; 
    volume_number?: number; 
    chapter_number?: number; 
    participants?: string[]; 
    extra_context_fn?: Function 
  } 
}>()

const emit = defineEmits<{ 
  (e: 'update:chapter', value: any): void
  (e: 'save'): void
  (e: 'switch-tab', tab: string): void
  (e: 'update:dirty', value: boolean): void
}>()

const cardStore = useCardStore()
const projectStore = useProjectStore()
const perCardStore = usePerCardAISettingsStore()
const editorStore = useEditorStore()
const { cards } = storeToRefs(cardStore)

const ready = ref(false)
const cmRoot = ref<HTMLElement | null>(null)
const titleElement = ref<HTMLElement | null>(null)
let view: EditorView | null = null

// 自定义高亮系统
const setHighlightEffect = StateEffect.define<{ from: number; to: number } | null>()

const highlightField = StateField.define<DecorationSet>({
  create() { return Decoration.none },
  update(highlights, tr) {
    highlights = highlights.map(tr.changes)
    for (const effect of tr.effects) {
      if (effect.is(setHighlightEffect)) {
        if (effect.value === null) {
          highlights = Decoration.none
        } else {
          const decoration = Decoration.mark({ class: 'cm-ai-highlight' }).range(effect.value.from, effect.value.to)
          highlights = Decoration.set([decoration])
        }
      }
    }
    return highlights
  },
  provide: f => EditorView.decorations.from(f)
})

const localCard = reactive({
  ...props.card,
  content: {
    content: typeof (props.chapter as any)?.content === 'string'
      ? (props.chapter as any).content
      : (typeof (props.card.content as any)?.content === 'string' ? (props.card.content as any).content : ''),
    word_count: typeof (props.chapter as any)?.content === 'string' ? ((props.chapter as any).content as string).length : (typeof (props.card.content as any)?.word_count === 'number' ? (props.card.content as any).word_count : 0),
    volume_number: (props.chapter as any)?.volume_number ?? ((props.contextParams as any)?.volume_number ?? ((props.card.content as any)?.volume_number ?? undefined)),
    chapter_number: (props.chapter as any)?.chapter_number ?? ((props.contextParams as any)?.chapter_number ?? ((props.card.content as any)?.chapter_number ?? undefined)),
    title: (props.chapter as any)?.title ?? ((props.card.content as any)?.title ?? props.card.title ?? ''),
    entity_list: (props.chapter as any)?.entity_list ?? ((props.card.content as any)?.entity_list ?? []),
    ...(props.card.content as any || {})
  }
})

// 每卡片参数
const editingParams = ref<PerCardAIParams>({})
const aiOptions = ref<AIConfigOptions | null>(null)
async function loadAIOptions() { try { aiOptions.value = await getAIConfigOptions() } catch {} }
const perCardParams = computed(() => perCardStore.getByCardId(props.card.id))

watch(() => props.card, async (newCard) => {
  if (!newCard) return
  await loadAIOptions()
  try {
    const resp = await getCardAIParams(newCard.id)
    const eff = (resp as any)?.effective_params
    if (eff && Object.keys(eff).length) {
      editingParams.value = { ...eff }
      perCardStore.setForCard(newCard.id, { ...eff })
      return
    }
  } catch {}
  const saved = perCardStore.getByCardId(newCard.id)
  if (saved) editingParams.value = { ...saved }
  else {
    const preset = getPresetForType(newCard.card_type?.name) || {}
    if (!preset.llm_config_id) { const first = aiOptions.value?.llm_configs?.[0]; if (first) preset.llm_config_id = first.id }
    editingParams.value = { ...preset }
    perCardStore.setForCard(newCard.id, editingParams.value)
  }
}, { immediate: true })

function getPresetForType(typeName?: string) : PerCardAIParams | undefined {
  const map: Record<string, PerCardAIParams> = {
    '章节大纲': { prompt_name: '章节大纲', llm_config_id: 1, temperature: 0.6, max_tokens: 4096, timeout: 60 },
    '内容生成': { prompt_name: '内容生成', llm_config_id: 1, temperature: 0.7, max_tokens: 8192, timeout: 60 },
  }
  return map[typeName || '']
}

// AI Composable
const {
  aiLoading,
  streamHandle,
  streamingStatus,
  interruptStream,
  executeAIGeneration,
  executeAIEdit,
  extractDynamicInfoWithLlm,
  extractRelationsWithLlm
} = useEditorAI({
  getText,
  setText,
  appendAtEnd,
  getSelectedText,
  replaceSelectedText,
  setHighlight,
  clearHighlight,
  updateHighlight,
  getCard: () => props.card,
  getCards: () => cards.value,
  getPrefetched: () => props.prefetched,
  getContextParams: () => props.contextParams,
  resolveLlmConfigId,
  resolveSampling,
  formatFactsFromContext,
  extractParticipantsForCurrentChapter,
  dispatch: (specs: any) => view?.dispatch(specs)
})

const wordCount = ref(0)
const previewBeforeUpdate = ref(true)
const originalContent = ref<string>('')
const isDirty = ref(false)
const previewDialogVisible = ref(false)
const previewData = ref<UpdateDynamicInfoOutput | null>(null)
const relationsPreviewVisible = ref(false)
const relationsPreview = ref<RelationExtractionOutput | null>(null)
const fontSize = ref<number>(16)
const lineHeight = ref<number>(1.8)
const polishPrompts = ref<string[]>([])
const expandPrompts = ref<string[]>([])
const currentPolishPrompt = ref('润色')
const currentExpandPrompt = ref('扩写')
const fontSizePx = computed(() => `${fontSize.value}px`)
const lineHeightStr = computed(() => String(lineHeight.value))

const contextMenu = reactive({
  visible: false,
  expanded: false,
  x: 0,
  y: 0,
  userRequirement: '',
  selectedText: null as { text: string; from: number; to: number } | null
})

function setText(text: string) {
  if (!view) return
  view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: text || '' } })
}

function getText(): string { return view ? view.state.doc.toString() : '' }

function getSelectedText() {
  if (!view) return null
  const { from, to } = view.state.selection.main
  if (from === to) return null
  return { text: view.state.doc.sliceString(from, to), from, to }
}

function replaceSelectedText(newText: string) {
  if (!view) return
  const { from, to } = view.state.selection.main
  view.dispatch({ changes: { from, to, insert: newText }, selection: { anchor: from + newText.length } })
}

function appendAtEnd(delta: string) {
  if (!view || !delta) return
  const end = view.state.doc.length
  view.dispatch({ changes: { from: end, to: end, insert: delta }, effects: EditorView.scrollIntoView(end, { y: "end" }) })
  try {
    const scroller = (cmRoot.value?.querySelector('.cm-scroller') as HTMLElement) || cmRoot.value
    if (scroller) requestAnimationFrame(() => { scroller.scrollTop = scroller.scrollHeight })
  } catch {}
}

function setHighlight(from: number, to: number) {
  if (!view || from >= to) return
  view.dispatch({ effects: setHighlightEffect.of({ from, to }) })
}

function clearHighlight() {
  if (!view) return
  view.dispatch({ effects: setHighlightEffect.of(null) })
}

function updateHighlight(from: number, to: number) {
  if (!view || from >= to) return
  view.dispatch({ effects: setHighlightEffect.of({ from, to }) })
}

function resolveLlmConfigId(): number | undefined {
  return (perCardParams.value || editingParams.value)?.llm_config_id
}

function resolveSampling() {
  const src: any = perCardParams.value || editingParams.value || {}
  return { temperature: src.temperature, max_tokens: src.max_tokens, timeout: src.timeout }
}

function formatFactsFromContext(ctx: any): string {
  try {
    if (!ctx) return ''
    const factsStruct: any = ctx.facts_structured || {}
    const lines: string[] = []
    if (Array.isArray(factsStruct.fact_summaries)) {
      factsStruct.fact_summaries.forEach(s => lines.push(`- ${s}`))
    }
    if (Array.isArray(factsStruct.relation_summaries)) {
      factsStruct.relation_summaries.forEach(r => {
        lines.push(`- ${r.a} ↔ ${r.b}（${r.kind}）`)
        if (r.a_to_b_addressing || r.b_to_a_addressing) {
          lines.push(`  · ${[r.a_to_b_addressing, r.b_to_a_addressing].filter(Boolean).join(' | ')}`)
        }
      })
    }
    return lines.join('\n')
  } catch { return '' }
}

function extractParticipantsForCurrentChapter(): string[] {
  try {
    const list = (localCard.content as any)?.entity_list
    if (Array.isArray(list)) {
      return list.map((x:any) => typeof x === 'string' ? x : (x?.name || '')).filter(s => !!s).slice(0, 6)
    }
  } catch {}
  return []
}

function extractParticipantsWithTypeForCurrentChapter() {
  const result: { name: string, type: string }[] = []
  try {
    const entityList = (localCard.content as any)?.entity_list
    if (!Array.isArray(entityList)) return []
    const cardMap = new Map((cards.value || []).map(c => [c.title, c]))
    for (const item of entityList) {
      const name = (typeof item === 'string' ? item : item?.name)?.trim()
      if (!name) continue
      let type = 'unknown'
      if (typeof item !== 'string' && item.entity_type) type = item.entity_type
      else if (cardMap.has(name)) {
        const cardTypeName = cardMap.get(name)?.card_type?.name || ''
        if (cardTypeName.includes('角色')) type = 'character'
        else if (cardTypeName.includes('组织')) type = 'organization'
        else if (cardTypeName.includes('场景')) type = 'scene'
      }
      result.push({ name, type })
    }
  } catch {}
  return result.slice(0, 10)
}

async function handleSave() {
  if (props.chapter) { emit('save'); return }
  const updatePayload: CardUpdate = {
    title: localCard.title,
    content: {
      ...localCard.content,
      content: getText(),
      word_count: wordCount.value,
      volume_number: (props.contextParams as any)?.volume_number ?? (localCard.content as any)?.volume_number,
      chapter_number: (props.contextParams as any)?.chapter_number ?? (localCard.content as any)?.chapter_number,
    }
  }
  await cardStore.modifyCard(localCard.id, updatePayload)
  originalContent.value = getText()
  isDirty.value = false
  emit('update:dirty', false)

  // 非阻塞自动提取
  triggerAutoExtraction()
  return updatePayload.content
}

async function triggerAutoExtraction() {
  try {
    const typeName = (props.card as any)?.card_type?.name || ''
    if (typeName !== '章节正文') return
    
    const needDynamic = localStorage.getItem('nf:chapter:auto_extract_dynamic_on_save') === '1'
    const needRelations = localStorage.getItem('nf:chapter:auto_extract_relations_on_save') === '1'
    
    if (needDynamic || needRelations) {
      const llmConfigId = resolveLlmConfigId()
      if (llmConfigId) {
        if (needDynamic) {
          const data = await extractDynamicInfoWithLlm(llmConfigId, localCard.id, getText())
          previewData.value = data
          previewDialogVisible.value = true
        }
        if (needRelations) {
          const participants = extractParticipantsWithTypeForCurrentChapter()
          const vol = (localCard as any)?.content?.volume_number ?? (props.contextParams as any)?.volume_number
          const ch = (localCard as any)?.content?.chapter_number ?? (props.contextParams as any)?.chapter_number
          const data = await extractRelationsWithLlm(llmConfigId, getText(), participants, vol, ch)
          relationsPreview.value = data
          relationsPreviewVisible.value = true
        }
      }
    }
  } catch (e) {
    console.error('自动提取失败:', e)
  }
}

async function executeAIContinuation() {
  const llmConfigId = resolveLlmConfigId()
  if (!llmConfigId) { ElMessage.error('请先设置有效的模型ID'); return }
  const promptName = (perCardParams.value || editingParams.value)?.prompt_name
  if (!promptName) { ElMessage.error('未设置生成任务名'); return }

  let resolvedContextTemplate = ''
  try {
    const aiContextTemplate = (props.card as any)?.ai_context_template || ''
    if (aiContextTemplate) {
      resolvedContextTemplate = resolveTemplate({ 
        template: aiContextTemplate, 
        cards: cards.value, 
        currentCard: { ...props.card, content: { ...localCard.content, content: getText() } } as any 
      })
    }
  } catch {}

  const contextParts: string[] = []
  if (resolvedContextTemplate) contextParts.push(`【引用上下文】\n${resolvedContextTemplate}`)
  const factsText = formatFactsFromContext(props.prefetched)
  if (factsText) contextParts.push(`【事实子图】\n${factsText}`)

  const requestData: ContinuationRequest = {
    previous_content: getText(),
    context_info: contextParts.join('\n\n'),
    existing_word_count: wordCount.value,
    llm_config_id: llmConfigId,
    stream: true,
    prompt_name: promptName,
    ...(props.contextParams || {}) as any,
  } as any

  const sampling = resolveSampling()
  if (sampling.temperature != null) (requestData as any).temperature = sampling.temperature
  if (sampling.max_tokens != null) (requestData as any).max_tokens = sampling.max_tokens

  if (view) { view.focus(); view.dispatch({ selection: { anchor: view.state.doc.length } }) }
  executeAIGeneration(requestData, false, '续写')
}

function handlePolishPromptChange(p: string) { currentPolishPrompt.value = p }
function handleExpandPromptChange(p: string) { currentExpandPrompt.value = p }
function executePolish() { executeAIEdit(currentPolishPrompt.value) }
function executeExpand() { executeAIEdit(currentExpandPrompt.value) }

function handleEditorContextMenu(e: MouseEvent) {
  const selection = getSelectedText()
  if (!selection || !selection.text.trim()) return
  e.preventDefault()
  e.stopPropagation()
  contextMenu.selectedText = selection
  contextMenu.visible = true
  contextMenu.expanded = false
  contextMenu.userRequirement = ''
  setHighlight(selection.from, selection.to)
  contextMenu.x = Math.min(e.clientX, window.innerWidth - 300)
  contextMenu.y = Math.min(e.clientY, window.innerHeight - 250)
  setTimeout(() => window.addEventListener('click', handleClickOutside, { capture: true }), 100)
}

function handleClickOutside(e: MouseEvent) {
  if (!contextMenu.visible) return
  if (!(e.target as HTMLElement).closest('.context-menu-popup')) closeContextMenu()
}

function expandContextMenu() {
  contextMenu.expanded = true
  nextTick(() => (document.querySelector('.context-menu-popup textarea') as HTMLElement)?.focus())
}

function closeContextMenu() {
  contextMenu.visible = false
  clearHighlight()
  window.removeEventListener('click', handleClickOutside, { capture: true })
}

async function handleContextMenuPolish() {
  const req = contextMenu.userRequirement.trim()
  closeContextMenu()
  await executeAIEdit(currentPolishPrompt.value, req || undefined)
}

async function handleContextMenuExpand() {
  const req = contextMenu.userRequirement.trim()
  closeContextMenu()
  await executeAIEdit(currentExpandPrompt.value, req || undefined)
}

async function confirmApplyUpdates() {
  try {
    const projectId = projectStore.currentProject?.id || (localCard as any).project_id
    if (!projectId || !previewData.value) return
    const resp = await updateDynamicInfoOnly({ project_id: projectId, data: previewData.value as any, queue_size: 5 })
    if (resp?.success) {
      ElMessage.success(`动态信息已更新：${resp.updated_card_count} 个角色卡`)
      await cardStore.fetchCards(projectId)
    }
  } finally {
    previewDialogVisible.value = false
    previewData.value = null
  }
}

async function confirmIngestRelationsFromPreview() {
  try {
    const projectId = projectStore.currentProject?.id || (localCard as any).project_id
    if (!projectId || !relationsPreview.value) return
    const vol = (localCard as any)?.content?.volume_number ?? (props.contextParams as any)?.volume_number
    const ch = (localCard as any)?.content?.chapter_number ?? (props.contextParams as any)?.chapter_number
    const participants = extractParticipantsWithTypeForCurrentChapter()
    const resp = await ingestRelationsFromPreview({ 
      project_id: projectId, 
      data: relationsPreview.value, 
      participants: participants as any,
      volume_number: vol, 
      chapter_number: ch 
    })
    ElMessage.success(`已写入关系/别名：${resp.written} 条`)
  } finally {
    relationsPreviewVisible.value = false
    relationsPreview.value = null
  }
}

function removePreviewItem(roleName: string, catKey: string, index: number) {
  if (!previewData.value) return
  const role = previewData.value.info_list.find(r => r.name === roleName)
  if (role && role.dynamic_info?.[catKey]) {
    role.dynamic_info[catKey].splice(index, 1)
  }
}

function initEditor() {
  if (!cmRoot.value) return
  const initialText = String((localCard.content as any)?.content || '')
  originalContent.value = initialText
  isDirty.value = false
  const customKeymap = [
    { key: 'Mod-s', run: () => { handleSave(); return true }, preventDefault: true }
  ]
  view = new EditorView({
    parent: cmRoot.value,
    state: EditorState.create({
      doc: initialText,
      extensions: [
        history(),
        keymap.of([...customKeymap, ...defaultKeymap, ...historyKeymap]),
        EditorView.lineWrapping,
        highlightField,
        EditorView.theme({ "&": { height: "100%" }, ".cm-scroller": { overflow: "auto" } }),
        EditorView.domEventHandlers({ mousedown: () => { clearHighlight(); return false } }),
        EditorView.updateListener.of((update) => {
          if (!update.docChanged) return
          const txt = update.state.doc.toString()
          wordCount.value = txt.replace(/\s+/g, '').length
          isDirty.value = txt !== originalContent.value
          emit('update:dirty', isDirty.value)
          localCard.content.content = txt
          if (props.chapter) emit('update:chapter', { ...localCard.content })
        })
      ]
    })
  })
  wordCount.value = getText().replace(/\s+/g, '').length
  ready.value = true
  cmRoot.value.querySelector('.cm-editor')?.addEventListener('contextmenu', handleEditorContextMenu as any)
}

async function handleTitleBlur() {
  const newTitle = titleElement.value?.textContent?.trim() || ''
  if (newTitle && newTitle !== localCard.title) {
    await cardStore.modifyCard(localCard.id, { title: newTitle })
    localCard.title = newTitle
    ElMessage.success('标题已更新')
  } else if (titleElement.value) {
    titleElement.value.textContent = localCard.title
  }
}

function handleTitleEnter() { titleElement.value?.blur() }

onMounted(async () => {
  initEditor()
  const options = await getAIConfigOptions()
  const names = (options?.prompts || []).map(p => p.name)
  polishPrompts.value = names.length ? names : ['润色']
  expandPrompts.value = names.length ? names : ['扩写']
  currentPolishPrompt.value = names.includes('润色') ? '润色' : (names[0] || '润色')
  currentExpandPrompt.value = names.includes('扩写') ? '扩写' : (names[0] || '扩写')
})

onUnmounted(() => {
  view?.destroy()
  if (streamHandle.value) streamHandle.value.cancel()
})

defineExpose({ handleSave, restoreContent: (c: any) => { setText(typeof c === 'string' ? c : c.content); originalContent.value = getText(); isDirty.value = false } })
</script>

<style scoped>
.chapter-studio { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
.toolbar { padding: 8px 20px; border-bottom: 1px solid var(--el-border-color-light); background: var(--el-fill-color-lighter); flex-shrink: 0; }
.toolbar-row { display: flex; align-items: center; gap: 12px; }
.toolbar-divider { width: 1px; height: 20px; background: var(--el-border-color-light); }
.toolbar-group { display: flex; align-items: center; gap: 6px; padding: 4px 10px; background: var(--el-fill-color-blank); border-radius: 6px; border: 1px solid var(--el-border-color-lighter); }
.group-label { font-size: 12px; color: var(--el-text-color-secondary); font-weight: 500; }
.streaming-status { display: flex; align-items: center; gap: 6px; color: var(--el-color-primary); font-size: 12px; margin-left: 10px; }
.status-text { white-space: nowrap; }
.editor-content-wrapper { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.chapter-header { padding: 16px 32px 14px; border-bottom: 1px solid var(--el-border-color-light); background: var(--el-fill-color-lighter); flex-shrink: 0; }
.title-section { flex: 1; display: flex; align-items: center; gap: 16px; }
.chapter-title { margin: 0; font-size: 28px; font-weight: 600; outline: none; padding: 6px 12px; border-radius: 6px; flex: 1; color: var(--el-text-color-primary); }
.title-meta { display: flex; align-items: center; gap: 6px; color: var(--el-text-color-secondary); font-size: 14px; }
.editor-content { flex: 1; overflow: hidden; background-color: var(--el-bg-color); position: relative; }
.editor-content :deep(.cm-editor) { height: 100% !important; outline: none; }
.editor-content :deep(.cm-scroller) { overflow-y: auto !important; }
.editor-content :deep(.cm-content) { padding: 20px; font-size: v-bind(fontSizePx); line-height: v-bind(lineHeightStr); color: var(--el-text-color-primary); }
.editor-content :deep(.cm-line) { color: var(--el-text-color-primary); }
.editor-content :deep(.cm-ai-highlight) {
  background: linear-gradient(120deg, rgba(96, 165, 250, 0.2) 0%, rgba(129, 140, 248, 0.2) 50%, rgba(96, 165, 250, 0.2) 100%);
  background-size: 200% 100%;
  animation: highlightPulse 2s ease-in-out infinite;
  border-radius: 2px;
}
@keyframes highlightPulse { 0%, 100% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } }
</style>