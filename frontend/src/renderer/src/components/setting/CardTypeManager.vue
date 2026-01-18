<template>
  <div class="card-type-manager">
    <!-- 工具条：搜索 + 新增 -->
    <div class="toolbar">
      <el-input v-model="query" placeholder="搜索类型（名称/描述）" clearable class="search" />
      <el-button type="primary" @click="openEditor()">新增类型</el-button>
    </div>

    <!-- 列表 -->
    <el-table v-loading="loading" :data="filteredTypes" height="60vh" size="small" :border="false">
      <el-table-column prop="name" label="名称" width="220" />
      <el-table-column prop="description" label="描述" min-width="260" show-overflow-tooltip>
        <template #default="{ row }">
          <span>{{
            row.description && String(row.description).trim() ? row.description : '—'
          }}</span>
        </template>
      </el-table-column>
      <el-table-column label="AI" width="90">
        <template #default="{ row }">
          <el-tag size="small" :type="row.is_ai_enabled ? 'success' : 'info'">{{
            row.is_ai_enabled ? '启用' : '关闭'
          }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="260" align="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEditor(row)">编辑</el-button>
          <el-button size="small" type="primary" plain @click="openSchemaStudio(row)"
            >编辑结构</el-button
          >
          <template v-if="!isBuiltInCardType(row)">
            <el-popconfirm
              title="删除该类型？（若有引用将影响创建操作）"
              @confirm="removeType(row)"
            >
              <template #reference>
                <el-button size="small" type="danger" plain>删除</el-button>
              </template>
            </el-popconfirm>
          </template>
          <el-button v-else size="small" type="danger" plain disabled>删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 编辑抽屉：基础信息 + 结构编辑入口 -->
    <el-drawer
      v-model="drawer.visible"
      :title="drawer.editing ? '编辑卡片类型' : '新增卡片类型'"
      size="60%"
    >
      <div class="editor-grid">
        <el-form label-position="top" :model="form">
          <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
          <el-form-item label="描述"
            ><el-input v-model="form.description" type="textarea" :rows="2"
          /></el-form-item>
          <el-form-item label="是否启用AI"><el-switch v-model="form.is_ai_enabled" /></el-form-item>
          <el-form-item label="是否单例"><el-switch v-model="form.is_singleton" /></el-form-item>
          <el-form-item label="默认上下文模板"
            ><el-input v-model="form.default_ai_context_template" type="textarea" :rows="4"
          /></el-form-item>

          <template v-if="form.is_ai_enabled">
            <div class="ai-section-title">AI 参数</div>
            <el-form-item label="模型（LLM 配置）">
              <el-select
                v-model="aiParams.llm_config_id"
                filterable
                placeholder="选择模型"
                style="width: 100%"
              >
                <el-option
                  v-for="c in llmConfigs"
                  :key="c.id"
                  :label="c.display_name || c.provider + ':' + c.model_name"
                  :value="c.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="提示词">
              <el-select
                v-model="aiParams.prompt_name"
                filterable
                placeholder="选择提示词"
                style="width: 100%"
              >
                <el-option v-for="p in prompts" :key="p.name" :label="p.name" :value="p.name" />
              </el-select>
            </el-form-item>
            <div class="ai-grid">
              <el-form-item label="温度">
                <el-input-number
                  v-model="aiParams.temperature"
                  :min="0"
                  :max="2"
                  :step="0.1"
                  controls-position="right"
                  style="width: 100%"
                />
              </el-form-item>
              <el-form-item label="最大 tokens">
                <el-input-number
                  v-model="aiParams.max_tokens"
                  :min="1"
                  :step="128"
                  controls-position="right"
                  style="width: 100%"
                />
              </el-form-item>
              <el-form-item label="超时 (秒)">
                <el-input-number
                  v-model="aiParams.timeout"
                  :min="1"
                  :max="600"
                  :step="5"
                  controls-position="right"
                  style="width: 100%"
                />
              </el-form-item>
            </div>
          </template>

          <el-form-item label="UI 布局（可选）">
            <el-input
              v-model="uiLayoutText"
              type="textarea"
              :rows="6"
              placeholder='{ "sections": [ ... ] }'
            />
          </el-form-item>
        </el-form>
        <div class="mt-2">
          <el-button type="primary" plain @click="openSchemaEditor">编辑结构（Schema）</el-button>
        </div>
      </div>
      <template #footer>
        <el-button @click="drawer.visible = false">取消</el-button>
        <el-button type="primary" @click="saveType">保存</el-button>
        <el-button v-if="drawer.id" type="success" plain @click="openTriggerBinder"
          >触发器</el-button
        >
      </template>
    </el-drawer>

    <SchemaStudio
      v-model:visible="studio.visible"
      :mode="'type'"
      :target-id="studio.typeId"
      :context-title="studio.typeName"
      @saved="onStudioSaved"
    />

    <!-- TriggerBinder 抽屉 -->
    <el-drawer v-model="triggerDrawer.visible" :title="`触发器 · ${form.name || ''}`" size="40%">
      <div class="trigger-panel">
        <div class="toolbar">
          <el-button type="primary" size="small" @click="addTrigger">新增触发器</el-button>
        </div>
        <el-table :data="filteredTriggers" size="small" height="50vh">
          <el-table-column prop="trigger_on" label="触发时机" width="140" />
          <el-table-column prop="is_active" label="状态" width="100">
            <template #default="{ row }">
              <el-switch v-model="row.is_active" @change="(v) => updateTrigger(row)" />
            </template>
          </el-table-column>
          <el-table-column label="操作" align="right" width="160">
            <template #default="{ row }">
              <el-select
                v-model="row.trigger_on"
                size="small"
                style="width: 140px"
                @change="() => updateTrigger(row)"
              >
                <el-option label="OnSave" value="onsave" />
                <el-option label="OnGenerateFinish" value="ongenfinish" />
                <el-option label="Manual" value="manual" />
              </el-select>
              <el-button text type="danger" @click="removeTrigger(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-drawer>
    <!-- 模板选择对话框 -->
    <el-dialog
      v-model="templateDialogVisible"
      title="选择卡片模板"
      width="600px"
      append-to-body
    >
      <div class="template-list">
        <div 
          class="template-item" 
          :class="{ active: selectedTemplateIndex === -1 }"
          @click="selectedTemplateIndex = -1"
        >
          <div class="template-name">空白模板 (Empty)</div>
          <div class="template-desc">从零开始创建一个全新的卡片类型。</div>
        </div>
        <div 
          v-for="(preset, index) in presets" 
          :key="index"
          class="template-item"
          :class="{ active: selectedTemplateIndex === index }"
          @click="selectedTemplateIndex = index"
        >
          <div class="template-name">{{ preset.name }}</div>
          <div class="template-desc">{{ preset.description }}</div>
        </div>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="templateDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="confirmTemplate">确定</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { components } from '@renderer/types/generated'
import { useCardStore } from '@renderer/stores/useCardStore'
import { schemaService } from '@renderer/api/schema'
import {
  listCardTypes,
  createCardType,
  updateCardType,
  deleteCardType,
  listLLMConfigs,
  listPrompts,
  type CardTypeRead as CTR,
  type CardTypeCreate as CTC,
  type CardTypeUpdate as CTU
} from '@renderer/api/setting'
import SchemaStudio from '../shared/SchemaStudio.vue'
import {
  listWorkflowTriggers,
  createWorkflowTrigger,
  updateWorkflowTrigger,
  deleteWorkflowTrigger,
  type WorkflowTriggerRead,
  type WorkflowTriggerCreate
} from '@renderer/api/workflows'
import { CARD_PRESETS } from '@renderer/constants/card_presets'

// 后端 CardType 类型
type CardTypeRead = CTR
type CardTypeCreate = CTC
type CardTypeUpdate = CTU

function isBuiltInCardType(row: any): boolean {
  return !!row?.built_in
}

const cardStore = useCardStore()

const loading = ref(false)
const types = ref<CardTypeRead[]>([])
const query = ref('')

async function fetchTypes() {
  loading.value = true
  try {
    types.value = await listCardTypes()
  } finally {
    loading.value = false
  }
}

const filteredTypes = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return types.value
  return types.value.filter(
    (t) =>
      (t.name || '').toLowerCase().includes(q) || (t.description || '').toLowerCase().includes(q)
  )
})

const drawer = ref({ visible: false, editing: false, id: 0 })
const form = ref<any>({
  name: '',
  description: '',
  is_ai_enabled: true,
  is_singleton: false,
  default_ai_context_template: ''
})
const uiLayoutText = ref('')
// AI 参数与可选项
const aiParams = ref<{
  llm_config_id?: number
  prompt_name?: string
  temperature?: number
  max_tokens?: number
  timeout?: number
}>({})
const defaultAIParams = { temperature: 0.7, max_tokens: 1024, timeout: 60 }
const llmConfigs = ref<any[]>([])
const prompts = ref<any[]>([])

// 模板选择相关
const templateDialogVisible = ref(false)
const presets = CARD_PRESETS
const selectedTemplateIndex = ref(-1)

function openEditor(row?: CardTypeRead) {
  if (!row) {
    // 新增模式：先打开模板选择
    selectedTemplateIndex.value = -1
    templateDialogVisible.value = true
    return
  }
  
  // 编辑模式：直接打开编辑器
  initEditor(row)
}

function confirmTemplate() {
  templateDialogVisible.value = false
  const preset = selectedTemplateIndex.value >= 0 ? presets[selectedTemplateIndex.value] : null
  
  const newType = {
    name: preset ? preset.name.split(' ')[0] : '',
    description: preset?.description || '',
    is_ai_enabled: false,
    is_singleton: false,
    default_ai_context_template: '',
    json_schema: preset?.json_schema ? JSON.parse(preset.json_schema) : undefined,
    ui_layout: preset?.ui_layout ? JSON.parse(preset.ui_layout) : undefined
  }
  
  initEditor(undefined, newType)
}

function initEditor(row?: CardTypeRead, templateData?: any) {
  drawer.value = { visible: true, editing: !!row, id: row?.id || 0 }
  
  if (row) {
    form.value = { ...row }
    uiLayoutText.value = row.ui_layout ? JSON.stringify(row.ui_layout, null, 2) : ''
    aiParams.value = (row as any)?.ai_params
      ? { ...defaultAIParams, ...(row as any).ai_params }
      : { ...defaultAIParams }
  } else {
    form.value = {
      name: '',
      description: '',
      is_ai_enabled: true,
      is_singleton: false,
      default_ai_context_template: '',
      ...templateData
    }
    // 如果有模板数据，需要特殊处理 json_schema，因为 form 不直接绑定它，而是通过 saveType 提交
    // 但这里我们需要把 ui_layout 展示出来
    uiLayoutText.value = templateData?.ui_layout ? JSON.stringify(templateData.ui_layout, null, 2) : ''
    aiParams.value = { ...defaultAIParams }
    
    // 注意：json_schema 在这里没有直接绑定到 form 上展示（因为没有 Schema 编辑器），
    // 而是需要保存时提交。
    // 为了支持模板的 Schema，我们需要暂存它，或者在保存时如果 form.id 为空且使用了模板，则带上 Schema。
    // 更好的方式是：如果使用了模板，我们应该把 Schema 存到 form 的临时字段里，saveType 时取用。
    if (templateData?.json_schema) {
      (form.value as any)._pending_schema = templateData.json_schema
    }
  }

  // 首次打开加载可选项
  if (llmConfigs.value.length === 0) {
    listLLMConfigs()
      .then((v) => {
        llmConfigs.value = v
        if (!aiParams.value.llm_config_id && v?.length) aiParams.value.llm_config_id = v[0].id
      })
      .catch(() => {})
  } else if (!aiParams.value.llm_config_id && llmConfigs.value?.length) {
    aiParams.value.llm_config_id = llmConfigs.value[0].id
  }
  if (prompts.value.length === 0) {
    listPrompts()
      .then((v: any) => (prompts.value = v))
      .catch(() => {})
  }
}

function openSchemaEditor() {
  openSchemaStudio(
    form.value?.id ? ({ id: form.value.id, name: form.value.name } as any) : undefined
  )
}

const studio = ref<{ visible: boolean; typeId: number; typeName: string }>({
  visible: false,
  typeId: 0,
  typeName: ''
})
function openSchemaStudio(row?: CardTypeRead) {
  const id = row?.id || drawer.value.id
  const name = row?.name || form.value?.name || ''
  if (!id) {
    ElMessage.warning('请先保存类型的基础信息')
    return
  }
  studio.value = { visible: true, typeId: id as number, typeName: name }
}

// ---- TriggerBinder ----
const triggerDrawer = ref<{ visible: boolean } & { triggers: WorkflowTriggerRead[] }>({
  visible: false,
  triggers: []
})
const filteredTriggers = computed(() =>
  triggerDrawer.value.triggers.filter((t) => t.card_type_name === form.value.name)
)

async function loadTriggers() {
  try {
    triggerDrawer.value.triggers = await listWorkflowTriggers()
  } catch {}
}
function openTriggerBinder() {
  if (!form.value?.name) {
    ElMessage.warning('请先保存类型名称')
    return
  }
  triggerDrawer.value.visible = true
  loadTriggers()
}
async function addTrigger() {
  try {
    if (!drawer.value.id) {
      ElMessage.warning('请先保存类型')
      return
    }
    const payload: WorkflowTriggerCreate = {
      workflow_id: 1,
      trigger_on: 'onsave',
      card_type_name: form.value.name,
      is_active: true
    }
    await createWorkflowTrigger(payload)
    ElMessage.success('已创建触发器，请记得在工作流工作室配置流程')
    await loadTriggers()
  } catch (e: any) {
    ElMessage.error('创建失败：' + (e?.message || e))
  }
}
async function updateTrigger(row: WorkflowTriggerRead) {
  try {
    await updateWorkflowTrigger(row.id, { trigger_on: row.trigger_on, is_active: row.is_active })
    ElMessage.success('已更新')
    await loadTriggers()
  } catch (e: any) {
    ElMessage.error('更新失败：' + (e?.message || e))
  }
}
async function removeTrigger(row: WorkflowTriggerRead) {
  try {
    await deleteWorkflowTrigger(row.id)
    ElMessage.success('已删除')
    await loadTriggers()
  } catch (e: any) {
    ElMessage.error('删除失败：' + (e?.message || e))
  }
}

async function saveType(): Promise<void> {
  let ui_layout: any = undefined
  try {
    ui_layout = uiLayoutText.value ? JSON.parse(uiLayoutText.value) : undefined
  } catch {
    ElMessage.error('UI 布局不是有效的 JSON')
    return
  }
  
  const payload: Partial<CardTypeCreate & CardTypeUpdate> = { ...form.value, ui_layout } as any
  ;(payload as any).ai_params = form.value.is_ai_enabled ? aiParams.value : null
  
  // 如果有暂存的 schema (来自模板)，则带上
  if ((form.value as any)._pending_schema) {
    (payload as any).json_schema = (form.value as any)._pending_schema
  }

  try {
    if (drawer.value.editing) {
      const id = drawer.value.id
      await updateCardType(id, payload)
      ElMessage.success('已更新卡片类型')
    } else {
      await createCardType(payload)
      ElMessage.success('已创建卡片类型')
    }
    drawer.value.visible = false
    await fetchTypes()
    await cardStore.fetchCardTypes()
    await schemaService.refreshSchemas()
  } catch (e: any) {
    ElMessage.error('保存失败：' + (e?.message || e))
  }
}

async function removeType(row: CardTypeRead) {
  try {
    await deleteCardType(row.id as number)
    ElMessage.success('已删除')
    await fetchTypes()
  } catch (e: any) {
    ElMessage.error('删除失败：' + (e?.message || e))
  }
}

function onStudioSaved() {
  fetchTypes()
  cardStore.fetchCardTypes()
  schemaService.refreshSchemas()
}

onMounted(() => {
  fetchTypes()
  const handler = () => fetchTypes()
  ;(window as any).__cardTypesUpdatedHandler = handler
  window.addEventListener('card-types-updated', handler as any)
})
onBeforeUnmount(() => {
  const handler = (window as any).__cardTypesUpdatedHandler
  if (handler) window.removeEventListener('card-types-updated', handler as any)
})

// 启用AI时若参数为空，为其填充默认值
watch(
  () => form.value.is_ai_enabled,
  (v) => {
    if (v) {
      aiParams.value = { ...defaultAIParams, ...(aiParams.value || {}) }
    }
  }
)
</script>

<style scoped>
.card-type-manager {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
}
.toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
}
.search {
  width: 320px;
  max-width: 60vw;
}
.editor-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
  height: calc(100% - 48px);
}
.mt-2 {
  margin-top: 8px;
  display: flex;
  gap: 8px;
  align-items: center;
}
.hint {
  color: var(--el-text-color-secondary);
}
.ai-section-title {
  font-weight: 600;
  color: var(--el-text-color-regular);
  margin-top: 4px;
}
.ai-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

/* 模板选择样式 */
.template-list {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  max-height: 400px;
  overflow-y: auto;
  padding: 4px;
}
.template-item {
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  padding: 12px;
  cursor: pointer;
  transition: all 0.2s;
}
.template-item:hover {
  border-color: var(--el-color-primary);
  background-color: var(--el-color-primary-light-9);
}
.template-item.active {
  border-color: var(--el-color-primary);
  background-color: var(--el-color-primary-light-8);
  box-shadow: 0 0 0 1px var(--el-color-primary);
}
.template-name {
  font-weight: bold;
  margin-bottom: 4px;
  color: var(--el-text-color-primary);
}
.template-desc {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.4;
}
</style>
