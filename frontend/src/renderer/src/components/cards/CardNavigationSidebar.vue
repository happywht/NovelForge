<template>
  <el-aside
    class="sidebar card-navigation-sidebar"
    :style="{ width: leftSidebarWidth + 'px' }"
    @contextmenu.prevent="onSidebarContextMenu"
  >
    <div class="sidebar-header">
      <h3 class="sidebar-title">创作卡片</h3>
    </div>

    <!-- 上半区（类型列表 + 自由卡片库） -->
    <div
      class="types-pane"
      :style="{ height: typesPaneHeight + 'px' }"
      @dragover.prevent
      @drop="onTypesPaneDrop"
    >
      <div class="pane-title">已有卡片类型</div>
      <el-scrollbar class="types-scroll">
        <ul class="types-list">
          <li
            v-for="t in cardStore.cardTypes"
            :key="t.id"
            class="type-item"
            draggable="true"
            @dragstart="onTypeDragStart(t)"
          >
            <span class="type-name">{{ t.name }}</span>
          </li>
        </ul>
      </el-scrollbar>
    </div>
    <!-- 内部分割条（垂直） -->
    <div class="inner-resizer" @mousedown="startResizingInner"></div>

    <!-- 下半区：项目卡片树 -->
    <div
      class="cards-pane"
      :style="{ height: `calc(100% - ${typesPaneHeight + innerResizerThickness}px)` }"
      @dragover.prevent
      @drop="onCardsPaneDrop"
    >
      <div class="cards-title">
        <div class="cards-title-text">当前项目：{{ projectStore.currentProject?.name }}</div>
        <div class="cards-title-actions">
          <el-button size="small" type="primary" @click="openCreateRoot">新建卡片</el-button>
          <el-button v-if="!isFreeProject" size="small" @click="openImportFreeCards"
            >导入卡片</el-button
          >
        </div>
      </div>
      <el-tree
        v-if="groupedTree.length > 0"
        ref="treeRef"
        :data="groupedTree"
        node-key="id"
        :default-expanded-keys="expandedKeys"
        :expand-on-click-node="false"
        draggable
        :allow-drop="handleAllowDrop"
        :allow-drag="handleAllowDrag"
        class="card-tree"
        @node-click="handleNodeClick"
        @node-expand="onNodeExpand"
        @node-collapse="onNodeCollapse"
        @node-drop="handleNodeDrop"
      >
        <template #default="{ node, data }">
          <el-dropdown
            class="full-row-dropdown"
            trigger="contextmenu"
            @command="(cmd: string) => handleContextCommand(cmd, data)"
          >
            <div
              class="custom-tree-node full-row"
              @dragover.prevent
              @drop="(e: any) => onExternalDropToNode(e, data)"
              @dragenter.prevent
            >
              <el-icon class="card-icon">
                <component :is="getIconByCardType(data.card_type?.name || data.__groupType)" />
              </el-icon>
              <span class="label">{{ node.label || data.title }}</span>
              <span v-if="data.children && data.children.length > 0" class="child-count">{{
                data.children.length
              }}</span>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <template v-if="!data.__isGroup">
                  <el-dropdown-item command="create-child">新建子卡片</el-dropdown-item>
                  <el-dropdown-item command="rename">重命名</el-dropdown-item>
                  <el-dropdown-item command="edit-structure">结构编辑</el-dropdown-item>
                  <el-dropdown-item command="add-as-reference">添加为引用</el-dropdown-item>
                  <el-dropdown-item command="delete" divided>删除卡片</el-dropdown-item>
                </template>
                <template v-else>
                  <el-dropdown-item command="delete-group" divided
                    >删除该分组下所有卡片</el-dropdown-item
                  >
                </template>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
      </el-tree>
      <el-empty v-else description="暂无卡片" :image-size="80"></el-empty>
    </div>

    <!-- 空白区域右键菜单（手动触发） -->
    <span
      ref="blankMenuRef"
      class="blank-menu-ref"
      :style="{
        position: 'fixed',
        left: blankMenuX + 'px',
        top: blankMenuY + 'px',
        width: '1px',
        height: '1px'
      }"
    ></span>
    <el-dropdown v-model:visible="blankMenuVisible" trigger="manual">
      <span></span>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item @click="openCreateRoot">新建卡片</el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>

    <!-- 新建卡片对话框 -->
    <el-dialog v-model="isCreateCardDialogVisible" title="新建创作卡片" width="500px">
      <el-form :model="newCardForm" label-position="top">
        <el-form-item label="卡片标题">
          <el-input v-model="newCardForm.title" placeholder="请输入卡片标题"></el-input>
        </el-form-item>
        <el-form-item label="卡片类型">
          <el-select
            v-model="newCardForm.card_type_id"
            placeholder="请选择卡片类型"
            style="width: 100%"
          >
            <el-option
              v-for="type in cardStore.cardTypes"
              :key="type.id"
              :label="type.name"
              :value="type.id"
            ></el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="父级卡片 (可选)">
          <el-tree-select
            v-model="newCardForm.parent_id"
            :data="cardStore.cardTree"
            :props="treeSelectProps"
            check-strictly
            :render-after-expand="false"
            placeholder="选择父级卡片"
            clearable
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="isCreateCardDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCreateCard">创建</el-button>
      </template>
    </el-dialog>

    <SchemaStudio
      v-model:visible="schemaStudio.visible"
      :mode="'card'"
      :target-id="schemaStudio.cardId"
      :context-title="schemaStudio.cardTitle"
      @saved="onCardSchemaSaved"
    />
  </el-aside>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { ElMessageBox, ElMessage } from 'element-plus'
import {
  CollectionTag,
  MagicStick,
  ChatLineRound,
  List,
  Connection,
  Tickets,
  Notebook,
  Document,
  User,
  OfficeBuilding
} from '@element-plus/icons-vue'
import { useCardStore } from '@renderer/stores/useCardStore'
import { useProjectStore } from '@renderer/stores/useProjectStore'
import { useEditorStore } from '@renderer/stores/useEditorStore'
import { useAssistantStore } from '@renderer/stores/useAssistantStore'
import { useCardTree } from '@renderer/composables/useCardTree'
import { useCardDragDrop } from '@renderer/composables/useCardDragDrop'
import SchemaStudio from '@renderer/components/shared/SchemaStudio.vue'

const props = defineProps<{
  leftSidebarWidth: number
}>()

const emit = defineEmits(['open-import-free-cards', 'active-tab-change'])

const cardStore = useCardStore()
const projectStore = useProjectStore()
const editorStore = useEditorStore()
const assistantStore = useAssistantStore()
const { cards, activeCard } = storeToRefs(cardStore)
const { expandedKeys, groupedTree, onNodeExpand, onNodeCollapse, updateProjectStructureContext } =
  useCardTree()

const isFreeProject = computed(() => (projectStore.currentProject?.name || '') === '__free__')

// 内部垂直分割：类型/卡片高度
const typesPaneHeight = ref(180)
const innerResizerThickness = 6

const treeSelectProps = {
  value: 'id',
  label: 'title',
  children: 'children'
} as const

const isCreateCardDialogVisible = ref(false)
const newCardForm = reactive({
  title: '',
  card_type_id: null as number | null,
  parent_id: '' as any
})

const blankMenuVisible = ref(false)
const blankMenuX = ref(0)
const blankMenuY = ref(0)
const blankMenuRef = ref<HTMLElement | null>(null)

const schemaStudio = ref({ visible: false, cardId: 0, cardTitle: '' })

const {
  onTypeDragStart,
  onCardsPaneDrop,
  onTypesPaneDrop,
  handleAllowDrag,
  handleAllowDrop,
  handleNodeDrop,
  onExternalDropToNode
} = useCardDragDrop(newCardForm, handleCreateCard)

function startResizingInner(event: MouseEvent) {
  const startY = event.clientY
  const startH = typesPaneHeight.value
  const onMove = (e: MouseEvent) => {
    const dy = e.clientY - startY
    const next = Math.max(120, Math.min(startH + dy, 400))
    typesPaneHeight.value = next
  }
  const onUp = () => {
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup', onUp)
  }
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
}

function openCreateRoot() {
  newCardForm.title = ''
  newCardForm.card_type_id = null
  newCardForm.parent_id = '' as any
  isCreateCardDialogVisible.value = true
}

function openCreateChild(parentId: number) {
  newCardForm.title = ''
  newCardForm.card_type_id = null
  newCardForm.parent_id = parentId
  isCreateCardDialogVisible.value = true
}

async function handleCreateCard() {
  if (!newCardForm.title.trim()) {
    ElMessage.warning('请输入卡片标题')
    return
  }
  if (!newCardForm.card_type_id) {
    ElMessage.warning('请选择卡片类型')
    return
  }

  const payload = {
    title: newCardForm.title.trim(),
    card_type_id: newCardForm.card_type_id,
    parent_id: newCardForm.parent_id || null,
    project_id: projectStore.currentProject?.id
  }

  const newCard = await cardStore.addCard(payload as any)
  if (newCard && projectStore.currentProject?.id) {
    const cardType = cardStore.cardTypes.find((ct) => ct.id === newCardForm.card_type_id)
    assistantStore.recordOperation(projectStore.currentProject.id, {
      type: 'create',
      cardId: (newCard as any).id,
      cardTitle: newCard.title,
      cardType: cardType?.name || 'Unknown'
    })
  }

  isCreateCardDialogVisible.value = false
  Object.assign(newCardForm, { title: '', card_type_id: null, parent_id: '' as any })
}

function openImportFreeCards() {
  emit('open-import-free-cards')
}

function handleNodeClick(data: any) {
  if (data.__isGroup) return
  cardStore.setActiveCard(data.id)
  emit('active-tab-change', 'editor')

  try {
    const pid = projectStore.currentProject?.id as number
    const pname = projectStore.currentProject?.name || ''
    const full = (cards.value || []).find((c: any) => c.id === data.id)
    const title = (full?.title || data.title || '') as string
    const content = full?.content || (data as any).content || {}
    if (pid && data?.id) {
      assistantStore.addAutoRef({
        projectId: pid,
        projectName: pname,
        cardId: data.id,
        cardTitle: title,
        content
      })
    }
  } catch {}
}

function onSidebarContextMenu(e: MouseEvent) {
  if ((e.target as HTMLElement).closest('.el-tree-node')) return
  blankMenuX.value = e.clientX
  blankMenuY.value = e.clientY
  blankMenuVisible.value = true
}

function handleContextCommand(command: string, data: any) {
  if (command === 'create-child') {
    openCreateChild(data.id)
  } else if (command === 'delete') {
    deleteNode(data.id, data.title)
  } else if (command === 'delete-group') {
    deleteGroupNodes(data)
  } else if (command === 'edit-structure') {
    if (!data?.id || data.__isGroup) return
    schemaStudio.value = { visible: true, cardId: data.id, cardTitle: data.title || '' }
  } else if (command === 'rename') {
    if (!data?.id || data.__isGroup) return
    renameCard(data.id, data.title || '')
  } else if (command === 'add-as-reference') {
    addAsReference(data)
  }
}

async function deleteNode(cardId: number, title: string) {
  try {
    await ElMessageBox.confirm(`确认删除卡片「${title}」？此操作不可恢复`, '删除确认', {
      type: 'warning'
    })
    await cardStore.removeCard(cardId)
    ElMessage.success('已删除')
    updateProjectStructureContext(activeCard.value?.id)
  } catch {}
}

async function deleteGroupNodes(groupData: any) {
  try {
    const title = groupData?.title || groupData?.__groupType || '该分组'
    await ElMessageBox.confirm(`确认删除${title}下的所有卡片？此操作不可恢复`, '删除确认', {
      type: 'warning'
    })
    const directChildren: any[] = Array.isArray(groupData?.children) ? groupData.children : []
    const toDeleteOrdered: number[] = []

    function collectDescendantIds(parentId: number) {
      const childIds = (cards.value || [])
        .filter((c: any) => c.parent_id === parentId)
        .map((c: any) => c.id)
      for (const cid of childIds) collectDescendantIds(cid)
      toDeleteOrdered.push(parentId)
    }

    for (const child of directChildren) {
      collectDescendantIds(child.id)
    }

    const seen = new Set<number>()
    for (const id of toDeleteOrdered) {
      if (seen.has(id)) continue
      seen.add(id)
      await cardStore.removeCard(id)
    }
    updateProjectStructureContext(activeCard.value?.id)
  } catch {}
}

async function renameCard(cardId: number, oldTitle: string) {
  try {
    const { value } = await ElMessageBox.prompt('重命名会立即生效，请输入新名称：', '重命名', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputValue: oldTitle,
      inputPlaceholder: '请输入卡片标题',
      inputValidator: (v: string) => v.trim().length > 0 || '标题不能为空'
    })
    const newTitle = String(value).trim()
    if (newTitle === oldTitle) return
    const card = cards.value.find((c) => (c as any).id === cardId)
    const updatePayload: any = { title: newTitle }
    if (card && card.content) {
      updatePayload.content = { ...(card.content as any), title: newTitle }
    }
    await cardStore.modifyCard(cardId, updatePayload)
    ElMessage.success('已重命名')
    updateProjectStructureContext(activeCard.value?.id)
  } catch {}
}

function addAsReference(data: any) {
  try {
    const pid = projectStore.currentProject?.id as number
    const pname = projectStore.currentProject?.name || ''
    const full = (cards.value || []).find((c: any) => c.id === data.id)
    const title = (full?.title || data.title || '') as string
    const content = full?.content || (data as any).content || {}
    assistantStore.addInjectedRefDirect(
      { projectId: pid, projectName: pname, cardId: data.id, cardTitle: title, content },
      'manual'
    )
    ElMessage.success('已添加为引用')
  } catch {}
}

function onCardSchemaSaved() {
  cardStore.fetchCards(projectStore.currentProject!.id)
}

function getIconByCardType(typeName?: string) {
  switch (typeName) {
    case '作品标签':
      return CollectionTag
    case '金手指':
      return MagicStick
    case '一句话梗概':
      return ChatLineRound
    case '故事大纲':
      return List
    case '世界观设定':
      return Connection
    case '核心蓝图':
      return Tickets
    case '分卷大纲':
      return Notebook
    case '章节大纲':
      return Document
    case '角色卡':
      return User
    case '场景卡':
      return OfficeBuilding
    default:
      return Document
  }
}
</script>

<style scoped>
.card-navigation-sidebar {
  display: flex;
  flex-direction: column;
  background-color: #f8f9fa;
  border-right: 1px solid #e0e0e0;
  overflow: hidden;
}

.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid #e0e0e0;
}

.sidebar-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.types-pane {
  padding: 12px;
  overflow: hidden;
}

.pane-title {
  font-size: 12px;
  font-weight: 600;
  color: #909399;
  margin-bottom: 8px;
  text-transform: uppercase;
}

.types-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.type-item {
  padding: 8px 12px;
  margin-bottom: 4px;
  background-color: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  cursor: grab;
  transition: all 0.2s;
}

.type-item:hover {
  border-color: #409eff;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.type-name {
  font-size: 13px;
  color: #606266;
}

.inner-resizer {
  height: 6px;
  background-color: #f0f2f5;
  cursor: row-resize;
  transition: background-color 0.2s;
}

.inner-resizer:hover {
  background-color: #e0e0e0;
}

.cards-pane {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 12px;
  overflow: hidden;
}

.cards-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.cards-title-text {
  font-size: 12px;
  font-weight: 600;
  color: #909399;
}

.card-tree {
  flex: 1;
  background: transparent;
}

.custom-tree-node {
  display: flex;
  align-items: center;
  width: 100%;
  padding: 4px 0;
}

.card-icon {
  margin-right: 8px;
  color: #409eff;
}

.label {
  font-size: 14px;
  color: #303133;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.child-count {
  font-size: 11px;
  color: #909399;
  background-color: #f0f2f5;
  padding: 0 6px;
  border-radius: 10px;
  margin-left: 8px;
}

.full-row-dropdown {
  width: 100%;
}

.blank-menu-ref {
  visibility: hidden;
}
</style>
