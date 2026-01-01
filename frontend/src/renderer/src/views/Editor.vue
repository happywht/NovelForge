<template>
  <div class="editor-layout">
    <!-- 左侧卡片导航树 -->
    <CardNavigationSidebar 
      :left-sidebar-width="leftSidebarWidth" 
      @open-import-free-cards="openImportFreeCards"
      @active-tab-change="(tab: string) => activeTab = tab"
    />
    
    <!-- 拖拽条 -->
    <div class="resizer left-resizer" @mousedown="startResizing('left')"></div>

    <!-- 中栏主内容区 -->
    <el-main class="main-content">
      <el-tabs v-model="activeTab" type="border-card" class="main-tabs">
        <el-tab-pane label="卡片库" name="market">
          <CardMarket @edit-card="handleEditCard" />
        </el-tab-pane>
        <el-tab-pane label="编辑器" name="editor">
          <template v-if="activeCard">
            <CardEditorHost :card="activeCard" :prefetched="prefetchedContext" />
          </template>
          <el-empty v-else description="请从左侧选择一个卡片进行编辑" />
        </el-tab-pane>
      </el-tabs>
    </el-main>

    <!-- 右侧助手面板分隔条与面板 -->
    <div class="resizer right-resizer" @mousedown="startResizing('right')"></div>
    <el-aside class="sidebar assistant-sidebar" :style="{ width: rightSidebarWidth + 'px' }">
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
  </div>

  <!-- 导入卡片对话框 -->
  <el-dialog v-model="importDialog.visible" title="导入卡片" width="900px" class="nf-import-dialog">
    <div style="display:flex; gap:12px; align-items:center; margin-bottom:8px; flex-wrap: wrap;">
      <el-select v-model="importDialog.sourcePid" placeholder="来源项目" style="width:220px" @change="onImportSourceChange($event as any)">
        <el-option v-for="p in importDialog.projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-input v-model="importDialog.search" placeholder="搜索来源卡片标题..." clearable style="flex:1; min-width: 200px" />
      <el-select v-model="importFilter.types" multiple collapse-tags placeholder="类型筛选" style="min-width:220px;" :max-collapse-tags="2">
        <el-option v-for="t in cardStore.cardTypes" :key="t.id" :label="t.name" :value="t.id!" />
      </el-select>
      <el-tree-select
        v-model="importDialog.parentId"
        :data="cardTree"
        :props="treeSelectProps"
        check-strictly
        :render-after-expand="false"
        placeholder="目标父级 (可选)"
        clearable
        popper-class="nf-tree-select-popper"
        style="width: 300px"
      />
    </div>
    <el-table :data="filteredImportCards" height="360px" border @selection-change="onImportSelectionChange">
      <el-table-column type="selection" width="48" />
      <el-table-column label="标题" prop="title" min-width="220" />
      <el-table-column label="类型" min-width="160">
        <template #default="{ row }">{{ row.card_type?.name }}</template>
      </el-table-column>
      <el-table-column label="创建时间" min-width="160">
        <template #default="{ row }">{{ (row as any).created_at }}</template>
      </el-table-column>
    </el-table>
    <template #footer>
      <el-button @click="importDialog.visible = false">取消</el-button>
      <el-button type="primary" :disabled="!selectedImportIds.length" @click="confirmImportCards">导入所选</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive, defineAsyncComponent, onBeforeUnmount, computed, watch, nextTick } from 'vue'
import { storeToRefs } from 'pinia'
import { ElMessageBox, ElMessage } from 'element-plus'
import type { components } from '@renderer/types/generated'
import { useSidebarResizer } from '@renderer/composables/useSidebarResizer'
import AssistantPanel from '@renderer/components/assistants/AssistantPanel.vue'
import ContextPanel from '@renderer/components/panels/ContextPanel.vue'
import ChapterToolsPanel from '@renderer/components/panels/ChapterToolsPanel.vue'
import OutlinePanel from '@renderer/components/panels/OutlinePanel.vue'
import HistoryPanel from '@renderer/components/panels/HistoryPanel.vue'
import { useCardStore } from '@renderer/stores/useCardStore'
import { useEditorStore } from '@renderer/stores/useEditorStore'
import { useProjectStore } from '@renderer/stores/useProjectStore'
import { useAssistantStore } from '@renderer/stores/useAssistantStore'
import { getCardSchema } from '@renderer/api/setting'
import { getProjects } from '@renderer/api/projects'
import { getCardsForProject, copyCard, getCardAIParams } from '@renderer/api/cards'
import { generateAIContent } from '@renderer/api/ai'
import CardNavigationSidebar from '@renderer/components/cards/CardNavigationSidebar.vue'

 // Mock components that will be created later
 const CardEditorHost = defineAsyncComponent(() => import('@renderer/components/cards/CardEditorHost.vue'));
 const CardMarket = defineAsyncComponent(() => import('@renderer/components/cards/CardMarket.vue'));

 type Project = components['schemas']['ProjectRead']
 type CardRead = components['schemas']['CardRead']

 // 导入卡片对话框状态
 const importDialog = ref<{ visible: boolean; search: string; parentId: number | null; sourcePid: number | null; projects: Array<{id:number; name:string}> }>({ visible: false, search: '', parentId: null, sourcePid: null, projects: [] })
 const importSourceCards = ref<CardRead[]>([])
 const selectedImportIds = ref<number[]>([])
 
 // 过滤：类型 + 标题
 const importFilter = ref<{ types: number[] }>({ types: [] })
 
 const filteredImportCards = computed(() => {
   const q = (importDialog.value.search || '').trim().toLowerCase()
   let list = importSourceCards.value || []
   if (importFilter.value.types.length) {
     const typeSet = new Set(importFilter.value.types)
     list = list.filter(c => c.card_type?.id && typeSet.has(c.card_type.id))
   }
   if (q) {
     list = list.filter(c => (c.title || '').toLowerCase().includes(q))
   }
   return list
 })

 async function openImportFreeCards() {
   try {
     const list = await getProjects()
     const currentId = projectStore.currentProject?.id
     importDialog.value.projects = (list || []).filter(p => p.id !== currentId).map(p => ({ id: p.id!, name: p.name! }))
     importDialog.value.sourcePid = importDialog.value.projects[0]?.id ?? null
     selectedImportIds.value = []
     await onImportSourceChange(importDialog.value.sourcePid as any)
     importDialog.value.visible = true
   } catch { ElMessage.error('加载来源项目失败') }
 }

 async function onImportSourceChange(pid: number | null) {
   importSourceCards.value = []
   if (!pid) return
   try { importSourceCards.value = await getCardsForProject(pid) } catch { importSourceCards.value = [] }
 }

 function onImportSelectionChange(rows: any[]) {
   selectedImportIds.value = (rows || []).map(r => Number(r.id)).filter(n => Number.isFinite(n))
 }

 async function confirmImportCards() {
   try {
     const pid = projectStore.currentProject?.id
     if (!pid) return
     const targetParent = importDialog.value.parentId || null
     for (const id of selectedImportIds.value) {
       await copyCard(id, { target_project_id: pid, parent_id: targetParent as any })
     }
     await cardStore.fetchCards(pid)
     ElMessage.success('已导入所选卡片')
     importDialog.value.visible = false
   } catch { ElMessage.error('导入失败') }
 }

 // Props
 const props = defineProps<{
   initialProject: Project
 }>()

 // Store
 const cardStore = useCardStore()
 const { cardTree, activeCard, cards } = storeToRefs(cardStore)
 const editorStore = useEditorStore()
 const projectStore = useProjectStore()
 const assistantStore = useAssistantStore()

 // Local State
 const activeTab = ref('market')
 const activeRightTab = ref('assistant')
 const prefetchedContext = ref<any>(null)

 // 统一 TreeSelect 样式/属性，确保选项可见
 const treeSelectProps = {
   value: 'id',
   label: 'title',
   children: 'children'
 } as const

 // Composables
 const { leftSidebarWidth, rightSidebarWidth, startResizing } = useSidebarResizer()

 // 助手面板上下文
 const assistantResolvedContext = ref<string>('')
 const assistantEffectiveSchema = ref<any>(null)
 const assistantSelectionCleared = ref<boolean>(false)
 const assistantParams = ref<{ llm_config_id: number | null; prompt_name: string | null; temperature: number | null; max_tokens: number | null; timeout: number | null }>({ llm_config_id: null, prompt_name: '灵感对话', temperature: null, max_tokens: null, timeout: null })

 // 判断当前是否为章节正文卡片
 const isChapterContent = computed(() => {
   return activeCard.value?.card_type?.name === '章节正文'
 })

 // 章节信息提取
 const chapterVolumeNumber = computed(() => {
   if (!isChapterContent.value) return null
   const content: any = activeCard.value?.content || {}
   return content.volume_number ?? null
 })

 const chapterChapterNumber = computed(() => {
   if (!isChapterContent.value) return null
   const content: any = activeCard.value?.content || {}
   return content.chapter_number ?? null
 })

 const chapterParticipants = computed(() => {
   if (!isChapterContent.value) return []
   const content: any = activeCard.value?.content || {}
   const list = content.entity_list || []
   if (Array.isArray(list)) {
     return list.map((x: any) => typeof x === 'string' ? x : (x?.name || '')).filter(Boolean).slice(0, 6)
   }
   return []
 })

 // 自动装配章节上下文
 watch(isChapterContent, async (val) => {
   if (val && activeCard.value) {
     await assembleChapterContext()
   }
 }, { immediate: true })

 async function assembleChapterContext() {
   if (!isChapterContent.value || !projectStore.currentProject?.id) return
   
   try {
     const { assembleContext } = await import('@renderer/api/ai')
     const res = await assembleContext({
       project_id: projectStore.currentProject.id,
       volume_number: chapterVolumeNumber.value ?? undefined,
       chapter_number: chapterChapterNumber.value ?? undefined,
       participants: chapterParticipants.value,
       current_draft_tail: ''
     })
     prefetchedContext.value = res
   } catch (e) {
     console.error('Failed to assemble chapter context:', e)
   }
 }

 async function refreshAssistantContext() {
   try {
     const card = assistantSelectionCleared.value ? null : (activeCard.value as any)
     if (!card) { assistantResolvedContext.value = ''; assistantEffectiveSchema.value = null; return }
     const { resolveTemplate } = await import('@renderer/services/contextResolver')
     const resolved = resolveTemplate({ template: card.ai_context_template || '', cards: cards.value, currentCard: card })
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
         timeout: eff.timeout ?? null,
       }
     } catch {
       const p = (card?.ai_params || {}) as any
       assistantParams.value = {
         llm_config_id: p.llm_config_id ?? null,
         prompt_name: (p.prompt_name ?? '灵感对话') as any,
         temperature: p.temperature ?? null,
         max_tokens: p.max_tokens ?? null,
         timeout: p.timeout ?? null,
       }
     }
   } catch { assistantResolvedContext.value = '' }
 }

 watch(activeCard, () => { if (!assistantSelectionCleared.value) refreshAssistantContext() })

 function resetAssistantSelection() {
   assistantSelectionCleared.value = true
   assistantResolvedContext.value = ''
   assistantEffectiveSchema.value = null
 }

 const assistantFinalize = async (summary: string) => {
   try {
     const card = activeCard.value as any
     if (!card) return
     const evt = new CustomEvent('nf:assistant-finalize', { detail: { cardId: card.id, summary } })
     window.dispatchEvent(evt)
     ElMessage.success('已发送定稿要点到编辑器页')
   } catch {}
 }

 async function handleJumpToCard(cardId: number) {
   cardStore.setActiveCard(cardId)
   activeTab.value = 'editor'
 }

 async function handleAIAssist(workflowName: string) {
   const project = projectStore.currentProject
   const cardId = activeCard.value?.id
   if (!project?.id || !cardId) {
     ElMessage.warning('请先选择一个卡片')
     return
   }

   const loading = ElMessage({
     message: `正在执行 AI 协作：${workflowName}...`,
     type: 'info',
     duration: 0
   })

   try {
     const { listWorkflows, runWorkflow } = await import('@renderer/api/workflows')
     const workflows = await listWorkflows()
     const wf = workflows.find(w => w.name === workflowName)
     
     if (!wf?.id) {
       throw new Error(`未找到工作流：${workflowName}`)
     }

     await runWorkflow(wf.id, {
       scope_json: {
         project_id: project.id,
         card_id: cardId,
         self_id: cardId
       },
       params_json: {}
     })

     loading.close()
     ElMessage.success(`AI 协作「${workflowName}」执行成功`)
     
     await cardStore.fetchCards(project.id)
     if (activeCard.value?.id === cardId) {
       cardStore.setActiveCard(cardId)
     }
   } catch (err: any) {
     loading.close()
     ElMessage.error(`执行失败: ${err.message || '未知错误'}`)
     console.error('Workflow run failed:', err)
   }
 }

 async function handleBatchAnalyze() {
   const project = projectStore.currentProject
   if (!project?.id) return

   try {
     await ElMessageBox.confirm(
       '“一键入库”将对本项目中所有“章节正文”卡片执行智能审计与同步，以构建初始知识图谱。这可能需要较长时间，是否继续？',
       '批量分析确认',
       { type: 'info', confirmButtonText: '开始分析', cancelButtonText: '取消' }
     )

     const chapterCards = cards.value.filter(c => c.card_type?.name === '章节正文')
     if (chapterCards.length === 0) {
       ElMessage.warning('未找到任何“章节正文”卡片')
       return
     }

     const loading = ElMessage({
       message: `正在准备批量分析 ${chapterCards.length} 个章节...`,
       type: 'info',
       duration: 0
     })

     const { listWorkflows, runWorkflow } = await import('@renderer/api/workflows')
     const workflows = await listWorkflows()
     const wf = workflows.find(w => w.name === '智能章节审计与同步')
     
     if (!wf?.id) {
       loading.close()
       throw new Error('未找到“智能章节审计与同步”工作流')
     }

     let successCount = 0
     let failCount = 0

     for (let i = 0; i < chapterCards.length; i++) {
       const card = chapterCards[i]
       ;(loading as any).message = `正在分析第 ${i + 1}/${chapterCards.length} 章: ${card.title}...`
       
       try {
         await runWorkflow(wf.id, {
           scope_json: {
             project_id: project.id,
             card_id: card.id,
             self_id: card.id
           },
           params_json: {}
         })
         successCount++
       } catch (err) {
         console.error(`Failed to analyze card ${card.id}:`, err)
         failCount++
       }
     }

     loading.close()
     ElMessage.success(`批量分析完成！成功: ${successCount}, 失败: ${failCount}`)
     await cardStore.fetchCards(project.id)
   } catch (e) {
     if (e !== 'cancel') {
       ElMessage.error('批量分析过程中发生错误')
       console.error('Batch analyze failed:', e)
     }
   }
 }

 async function handleHistoryRestored(content: string) {
   if (activeCard.value) {
     cardStore.updateCardContentLocally(activeCard.value.id, content)
     ElMessage.success('已恢复历史版本内容')
   }
 }

 function handleEditCard(cardId: number) {
   cardStore.setActiveCard(cardId);
   activeTab.value = 'editor';
 }

 onMounted(async () => {
   if (props.initialProject?.id) {
     projectStore.setCurrentProject(props.initialProject)
     await cardStore.fetchCardTypes()
     await cardStore.fetchCards(props.initialProject.id)
   }
 })

</script>

<style scoped>
.editor-layout {
  display: flex;
  height: 100%;
  width: 100%;
  position: relative;
  background-color: var(--el-fill-color-lighter);
}

.sidebar {
  display: flex;
  flex-direction: column;
  background-color: var(--el-fill-color-lighter);
  transition: width 0.2s;
  flex-shrink: 0;
  overflow: hidden;
}

.resizer {
  width: 5px;
  background: transparent;
  cursor: col-resize;
  z-index: 10;
  user-select: none;
  position: relative;
  transition: background-color 0.2s;
}
.resizer:hover {
  background: var(--el-color-primary-light-7);
}

.main-content {
  padding: 16px 8px;
  display: flex;
  flex-direction: column;
  background-color: transparent;
}

.main-tabs {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  background-color: var(--el-bg-color);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  border-radius: 8px;
  overflow: hidden;
  border: none;
}

:deep(.el-tabs__content) {
  flex-grow: 1;
  overflow-y: auto;
}
:deep(.el-tab-pane) {
  height: 100%;
}

.assistant-sidebar { 
  border-left: none; 
  background: transparent; 
  flex-shrink: 0; 
  padding: 16px 8px 16px 0;
}
.right-resizer { cursor: col-resize; width: 5px; background: transparent; }
.right-resizer:hover { background: var(--el-color-primary-light-7); }

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