<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { storeToRefs } from 'pinia'
import { useCardStore } from '@renderer/stores/useCardStore'
import { useProjectStore } from '@renderer/stores/useProjectStore'
import { getProjects } from '@renderer/api/projects'
import { getCardsForProject, copyCard } from '@renderer/api/cards'
import type { components } from '@renderer/types/generated'

type CardRead = components['schemas']['CardRead']

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
}>()

const cardStore = useCardStore()
const projectStore = useProjectStore()
const { cardTree } = storeToRefs(cardStore)

const importDialog = ref<{ search: string; parentId: number | null; sourcePid: number | null; projects: Array<{id:number; name:string}> }>({ search: '', parentId: null, sourcePid: null, projects: [] })
const importSourceCards = ref<CardRead[]>([])
const selectedImportIds = ref<number[]>([])
const importFilter = ref<{ types: number[] }>({ types: [] })

const treeSelectProps = {
  value: 'id',
  label: 'title',
  children: 'children'
} as const

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
    emit('update:visible', false)
  } catch { ElMessage.error('导入失败') }
}

async function init() {
  try {
    const list = await getProjects()
    const currentId = projectStore.currentProject?.id
    importDialog.value.projects = (list || []).filter(p => p.id !== currentId).map(p => ({ id: p.id!, name: p.name! }))
    importDialog.value.sourcePid = importDialog.value.projects[0]?.id ?? null
    selectedImportIds.value = []
    await onImportSourceChange(importDialog.value.sourcePid as any)
  } catch { ElMessage.error('加载来源项目失败') }
}

// 当外部 visible 变为 true 时初始化
watch(() => props.visible, (newVal) => {
  if (newVal) {
    init()
  }
})

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})
</script>

<template>
  <el-dialog v-model="dialogVisible" title="导入卡片" width="900px" class="nf-import-dialog">
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
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :disabled="!selectedImportIds.length" @click="confirmImportCards">导入所选</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.nf-import-dialog :deep(.el-dialog__body) {
  padding-top: 10px;
}
</style>
