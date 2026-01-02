<template>
  <div class="editor-layout">
    <!-- 左侧卡片导航树 -->
    <CardNavigationSidebar
      :left-sidebar-width="leftSidebarWidth"
      @open-import-free-cards="importVisible = true"
      @active-tab-change="(tab: string) => (activeTab = tab)"
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
    <AssistantSidebar
      ref="assistantSidebarRef"
      :width="rightSidebarWidth"
      :active-card="activeCard"
      :prefetched-context="prefetchedContext"
      @jump-to-card="handleJumpToCard"
      @history-restored="handleHistoryRestored"
    />

    <!-- 导入卡片对话框 -->
    <CardImportDialog v-model:visible="importVisible" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, defineAsyncComponent, computed, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { ElMessageBox, ElMessage } from 'element-plus'
import type { components } from '@renderer/types/generated'
import { useSidebarResizer } from '@renderer/composables/useSidebarResizer'
import { useCardStore } from '@renderer/stores/useCardStore'
import { useProjectStore } from '@renderer/stores/useProjectStore'
import CardNavigationSidebar from '@renderer/components/cards/CardNavigationSidebar.vue'
import AssistantSidebar from '@renderer/components/assistants/AssistantSidebar.vue'
import CardImportDialog from '@renderer/components/cards/CardImportDialog.vue'

// Mock components that will be created later
const CardEditorHost = defineAsyncComponent(
  () => import('@renderer/components/cards/CardEditorHost.vue')
)
const CardMarket = defineAsyncComponent(() => import('@renderer/components/cards/CardMarket.vue'))

type Project = components['schemas']['ProjectRead']

// Props
const props = defineProps<{
  initialProject: Project
}>()

// Store
const cardStore = useCardStore()
const { activeCard, cards } = storeToRefs(cardStore)
const projectStore = useProjectStore()

// Local State
const activeTab = ref('market')
const prefetchedContext = ref<any>(null)
const importVisible = ref(false)
const assistantSidebarRef = ref<any>(null)

// Composables
const { leftSidebarWidth, rightSidebarWidth, startResizing } = useSidebarResizer()

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
    return list
      .map((x: any) => (typeof x === 'string' ? x : x?.name || ''))
      .filter(Boolean)
      .slice(0, 6)
  }
  return []
})

// 自动装配章节上下文
watch(
  isChapterContent,
  async (val) => {
    if (val && activeCard.value) {
      await assembleChapterContext()
    }
  },
  { immediate: true }
)

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

async function handleJumpToCard(payload: { projectId: number; cardId: number }) {
  cardStore.setActiveCard(payload.cardId)
  activeTab.value = 'editor'
}

async function handleHistoryRestored(content: string) {
  if (activeCard.value) {
    cardStore.updateCardContentLocally(activeCard.value.id, content)
    ElMessage.success('已恢复历史版本内容')
  }
}

function handleEditCard(cardId: number) {
  cardStore.setActiveCard(cardId)
  activeTab.value = 'editor'
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

.right-resizer {
  cursor: col-resize;
  width: 5px;
  background: transparent;
}
.right-resizer:hover {
  background: var(--el-color-primary-light-7);
}
</style>
