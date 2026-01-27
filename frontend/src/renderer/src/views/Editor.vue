<template>
  <div class="editor-layout" :class="{ 'fullscreen': isFullscreen }">
    <!-- Fullscreen Toolbar -->
    <div v-if="isFullscreen" class="fullscreen-toolbar">
      <div class="toolbar-left">
        <el-button
          :icon="leftSidebarCollapsed ? 'Expand' : 'Fold'"
          circle
          size="small"
          @click="leftSidebarCollapsed = !leftSidebarCollapsed"
        >
          <el-icon>
            <component :is="leftSidebarCollapsed ? 'Expand' : 'Fold'" />
          </el-icon>
        </el-button>
        <span class="toolbar-title">{{ projectStore.currentProject?.name || '编辑器' }}</span>
      </div>
      <div class="toolbar-right">
        <el-button
          :icon="rightSidebarCollapsed ? 'Expand' : 'Fold'"
          circle
          size="small"
          @click="rightSidebarCollapsed = !rightSidebarCollapsed"
        >
          <el-icon>
            <component :is="rightSidebarCollapsed ? 'Expand' : 'Fold'" />
          </el-icon>
        </el-button>
        <el-button
          type="primary"
          circle
          size="small"
          @click="toggleFullscreen"
        >
          <el-icon><CloseBold /></el-icon>
        </el-button>
      </div>
    </div>

    <!-- 左侧卡片导航树 -->
    <CardNavigationSidebar
      v-show="!leftSidebarCollapsed"
      :left-sidebar-width="leftSidebarWidth"
      :class="{ 'sidebar-transition': true }"
      @open-import-free-cards="importVisible = true"
      @active-tab-change="(tab: string) => (activeTab = tab)"
    />

    <!-- 左侧折叠按钮 -->
    <div v-if="!isFullscreen" class="sidebar-toggle left-toggle" @click="leftSidebarCollapsed = !leftSidebarCollapsed">
      <el-icon>
        <component :is="leftSidebarCollapsed ? 'DArrowRight' : 'DArrowLeft'" />
      </el-icon>
    </div>

    <!-- 拖拽条 -->
    <div
      v-show="!leftSidebarCollapsed"
      class="resizer left-resizer"
      @mousedown="startResizing('left')"
    ></div>

    <!-- 中栏主内容区 -->
    <el-main class="main-content">
      <!-- 非全屏模式下的工具栏 -->
      <div v-if="!isFullscreen" class="content-header">
        <div class="header-actions">
          <el-button
            :icon="FullScreen"
            circle
            size="small"
            @click="toggleFullscreen"
            title="全屏模式 (F11)"
          >
            <el-icon><FullScreen /></el-icon>
          </el-button>
        </div>
      </div>

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
    <div
      v-show="!rightSidebarCollapsed"
      class="resizer right-resizer"
      @mousedown="startResizing('right')"
    ></div>
    <AssistantSidebar
      v-show="!rightSidebarCollapsed"
      ref="assistantSidebarRef"
      :width="rightSidebarWidth"
      :active-card="activeCard"
      :prefetched-context="prefetchedContext"
      :class="{ 'sidebar-transition': true }"
      @jump-to-card="handleJumpToCard"
      @history-restored="handleHistoryRestored"
    />

    <!-- 右侧折叠按钮 -->
    <div v-if="!isFullscreen" class="sidebar-toggle right-toggle" @click="rightSidebarCollapsed = !rightSidebarCollapsed">
      <el-icon>
        <component :is="rightSidebarCollapsed ? 'DArrowLeft' : 'DArrowRight'" />
      </el-icon>
    </div>

    <!-- 导入卡片对话框 -->
    <CardImportDialog v-model:visible="importVisible" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, defineAsyncComponent, computed, watch, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
import { ElMessage } from 'element-plus'
import { FullScreen, CloseBold, Fold, Expand, DArrowLeft, DArrowRight } from '@element-plus/icons-vue'
import type { components } from '@renderer/types/generated'
import { useSidebarResizer } from '@renderer/composables/useSidebarResizer'
import { useFullscreen } from '@renderer/composables/useFullscreen'
import { useCardStore } from '@renderer/stores/useCardStore'
import { useProjectStore } from '@renderer/stores/useProjectStore'
import CardNavigationSidebar from '@renderer/components/cards/CardNavigationSidebar.vue'
import AssistantSidebar from '@renderer/components/assistants/AssistantSidebar.vue'
import CardImportDialog from '@renderer/components/cards/CardImportDialog.vue'

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
const leftSidebarCollapsed = ref(false)
const rightSidebarCollapsed = ref(false)

// Composables
const { leftSidebarWidth, rightSidebarWidth, startResizing } = useSidebarResizer()

// Set optimized default widths (20% : 50% : 30% for 1400px screen)
leftSidebarWidth.value = 280  // 20%
rightSidebarWidth.value = 420  // 30%

const { isFullscreen, toggleFullscreen } = useFullscreen()

// Keyboard shortcuts
const handleKeydown = (e: KeyboardEvent) => {
  // Ctrl+B: toggle left sidebar
  if (e.ctrlKey && e.key === 'b') {
    e.preventDefault()
    leftSidebarCollapsed.value = !leftSidebarCollapsed.value
  }
  // Ctrl+/: toggle right sidebar
  if (e.ctrlKey && e.key === '/') {
    e.preventDefault()
    rightSidebarCollapsed.value = !rightSidebarCollapsed.value
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})

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

watch(cards, async () => {
  if (isChapterContent.value && activeCard.value) {
    await assembleChapterContext()
  }
})

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
  transition: all 0.3s ease;
}

.editor-layout.fullscreen {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 9999;
  background-color: var(--el-bg-color);
}

/* Fullscreen Toolbar */
.fullscreen-toolbar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 48px;
  background: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color-lighter);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  z-index: 100;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.toolbar-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.fullscreen .main-content {
  margin-top: 48px;
}

/* Sidebar Transitions */
.sidebar-transition {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

/* Sidebar Toggle Buttons */
.sidebar-toggle {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 24px;
  height: 48px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 0 8px 8px 0;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 20;
  transition: all 0.2s ease;
}

.sidebar-toggle:hover {
  background: var(--el-fill-color-light);
  border-color: var(--el-color-primary-light-7);
}

.sidebar-toggle.left-toggle {
  left: 0;
}

.sidebar-toggle.right-toggle {
  right: 0;
  border-radius: 8px 0 0 8px;
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
  flex: 1;
  min-width: 0;
}

.content-header {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 8px;
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
