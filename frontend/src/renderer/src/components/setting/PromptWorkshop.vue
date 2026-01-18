<template>
  <div class="prompt-workshop">
    <div class="toolbar">
      <h2>提示词工坊</h2>
      <el-button type="primary" @click="openDrawer()">新建提示词</el-button>
    </div>
    
    <el-table v-loading="loading" :data="items" style="width: 100%" height="calc(100vh - 100px)">
      <el-table-column prop="name" label="名称" width="180" />
      <el-table-column prop="description" label="描述" />
      <el-table-column label="操作" width="220">
        <template #default="{ row }">
          <el-button size="small" @click="openDrawer(row)">编辑</el-button>
          <el-popconfirm
            v-if="!row.built_in"
            title="删除该提示词？"
            @confirm="remove(row)"
          >
            <template #reference>
              <el-button size="small" type="danger" :disabled="row.built_in">删除</el-button>
            </template>
          </el-popconfirm>
          <el-button v-else size="small" type="danger" plain disabled>删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-drawer
      v-model="drawer.visible"
      :title="drawer.editing ? '编辑提示词' : '新建提示词'"
      size="50%"
      :before-close="handleDrawerClose"
    >
      <div class="drawer-content">
        <el-form label-position="top" :model="form">
          <el-form-item label="名称">
            <el-input v-model="form.name" :disabled="drawer.editing && form.built_in" />
          </el-form-item>
          <el-form-item label="描述">
            <el-input v-model="form.description" type="textarea" :rows="2" />
          </el-form-item>
          
          <el-divider content-position="left">模板编辑</el-divider>
          
          <div class="mode-switch">
             <el-radio-group v-model="editMode" size="small">
               <el-radio-button label="structured">结构化编辑</el-radio-button>
               <el-radio-button label="raw">源码编辑</el-radio-button>
             </el-radio-group>
             <el-button 
               v-if="editMode === 'structured'" 
               type="primary" 
               link 
               size="small" 
               @click="syncToRaw"
               style="margin-left: auto"
             >
               生成预览 ->
             </el-button>
          </div>

          <div v-if="editMode === 'structured'" class="structured-editor">
            <el-form-item label="角色 (Role)">
              <el-input v-model="structured.role" placeholder="例如：你是一个经验丰富的小说编辑..." />
            </el-form-item>
            <el-form-item label="技能 (Skills)">
              <el-input v-model="structured.skills" type="textarea" :rows="2" placeholder="例如：擅长分析剧情节奏、人物弧光..." />
            </el-form-item>
            <el-form-item label="目标 (Goals)">
              <el-input v-model="structured.goals" type="textarea" :rows="3" placeholder="每行一个目标" />
            </el-form-item>
            <el-form-item label="引用知识库 (Knowledge)">
               <div class="kb-selector">
                 <div class="row">
                    <span class="label">引用方式：</span>
                    <el-radio-group v-model="knowledgeMode" size="small">
                      <el-radio-button label="id">按ID</el-radio-button>
                      <el-radio-button label="name">按名称</el-radio-button>
                    </el-radio-group>
                 </div>
                 <el-select 
                   v-model="selectedKnowledgeIds" 
                   multiple 
                   filterable
                   placeholder="选择知识库条目" 
                   style="width: 100%"
                 >
                   <el-option 
                     v-for="k in knowledgeItems" 
                     :key="k.id" 
                     :label="k.name" 
                     :value="k.id" 
                   />
                 </el-select>
               </div>
            </el-form-item>
            <el-form-item label="输出格式 (Output Format)">
              <el-input v-model="structured.outputFormat" type="textarea" :rows="2" placeholder="例如：请以 Markdown 列表形式输出..." />
            </el-form-item>
          </div>

          <div v-else class="raw-editor">
            <el-form-item label="模板内容">
              <el-input 
                v-model="form.template" 
                type="textarea" 
                :rows="15" 
                font-family="monospace"
              />
              <div class="template-hint">
                使用 <code>${variable}</code> 的形式来定义占位符。
              </div>
            </el-form-item>
          </div>
        </el-form>
      </div>
      <template #footer>
        <div class="drawer-footer">
          <el-button @click="handleDrawerClose">取消</el-button>
          <el-button type="success" plain @click="openTestDialog">测试运行</el-button>
          <el-button type="primary" @click="save">保存</el-button>
        </div>
      </template>
    </el-drawer>

    <PromptTestDialog 
      v-model:visible="testDialogVisible"
      :template="currentTemplateForTest"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listPrompts,
  createPrompt,
  updatePrompt,
  deletePrompt,
  listKnowledge,
  type Prompt,
  type Knowledge
} from '@renderer/api/setting'
import PromptTestDialog from './PromptTestDialog.vue'

const DEFAULT_OUTPUT_FORMAT = '请严格根据提供的Json Schema返回结果'

const loading = ref(false)
const items = ref<Prompt[]>([])
const knowledgeItems = ref<Knowledge[]>([])

const drawer = ref({
  visible: false,
  editing: false,
  id: 0
})

const form = ref<Partial<Prompt>>({
  name: '',
  description: '',
  template: ''
})

const editMode = ref<'structured' | 'raw'>('structured')

// Structured data
const structured = ref({
  role: '',
  skills: '',
  goals: '',
  outputFormat: DEFAULT_OUTPUT_FORMAT
})
const selectedKnowledgeIds = ref<number[]>([])
const knowledgeMode = ref<'id' | 'name'>('id')

// Test Dialog State
const testDialogVisible = ref(false)
const currentTemplateForTest = computed(() => {
  if (editMode.value === 'structured') {
    return composeTemplate(structured.value)
  }
  return form.value.template || ''
})

function openTestDialog() {
  testDialogVisible.value = true
}

async function fetchList() {
  loading.value = true
  try {
    const [pList, kList] = await Promise.all([listPrompts(), listKnowledge()])
    items.value = pList
    knowledgeItems.value = kList
  } catch (e: any) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

function handleDrawerClose() {
  drawer.value.visible = false
}

function resetStructuredDefaults() {
  structured.value = {
    role: '',
    skills: '',
    goals: '',
    outputFormat: DEFAULT_OUTPUT_FORMAT
  }
  selectedKnowledgeIds.value = []
  knowledgeMode.value = 'name'
}

// 解析逻辑
function parseKnowledgeBlock(tpl: string) {
  const k = /-\s*knowledge:\s*([\s\S]*?)(?:\n-\s*OutputFormat\s*[:：]|$)/i.exec(tpl)
  const ids: number[] = []
  let mode: 'id' | 'name' = 'name'
  
  if (k && k[1]) {
    const block = k[1]
    const idReg = /@KB\{\s*id\s*=\s*(\d+)\s*\}/gi
    const nameReg = /@KB\{\s*name\s*=\s*([^}]+)\}/gi
    let m: RegExpExecArray | null
    
    // Check for IDs
    while ((m = idReg.exec(block))) {
      const id = Number(m[1])
      if (!Number.isNaN(id)) ids.push(id)
    }
    
    if (ids.length > 0) {
      mode = 'id'
    } else {
      // Check for Names
      const names: string[] = []
      while ((m = nameReg.exec(block))) {
        const n = (m[1] || '').trim().replace(/^['"]|['"]$/g, '')
        if (n) names.push(n)
      }
      if (names.length) {
        mode = 'name'
        for (const n of names) {
          const found = knowledgeItems.value.find((kb) => kb.name === n)
          if (found) ids.push(found.id)
        }
      }
    }
  }
  selectedKnowledgeIds.value = Array.from(new Set(ids))
  knowledgeMode.value = mode
}

function tryParseStructured(tpl?: string) {
  if (!tpl) {
    resetStructuredDefaults()
    return false
  }
  try {
    const r = /-\s*Role:\s*(.*)/i.exec(tpl)
    // 简单的正则匹配，可能不够严谨，但够用
    const s = /-\s*Skills?:\s*([\s\S]*?)(?:\n-\s*Goals?:|\n-\s*knowledge:|\n-\s*OutputFormat\s*[:：]|$)/i.exec(tpl)
    const g = /-\s*Goals?:\s*([\s\S]*?)(?:\n-\s*knowledge:|\n-\s*OutputFormat\s*[:：]|$)/i.exec(tpl)
    const o = /-\s*OutputFormat\s*[:：]\s*([\s\S]*)/i.exec(tpl)
    
    // 如果连 Role 都没匹配到，可能不是结构化模板
    if (!r && !s && !g) return false

    structured.value.role = r?.[1]?.trim() || ''
    structured.value.skills = (s?.[1] || '').trim()
    structured.value.goals = (g?.[1] || '').replace(/^\s*-\s*/gm, '').trim()
    structured.value.outputFormat = (o?.[1] || DEFAULT_OUTPUT_FORMAT).trim()
    
    parseKnowledgeBlock(tpl)
    return true
  } catch {
    return false
  }
}

function openDrawer(row?: Prompt) {
  drawer.value.visible = true
  drawer.value.editing = !!row
  drawer.value.id = row?.id || 0
  
  if (row) {
    form.value = { ...row }
    // 尝试解析
    const success = tryParseStructured(row.template)
    if (success) {
      editMode.value = 'structured'
    } else {
      editMode.value = 'raw'
      resetStructuredDefaults()
    }
  } else {
    form.value = { name: '', description: '', template: '' }
    editMode.value = 'structured'
    resetStructuredDefaults()
  }
}

function syncToRaw() {
  form.value.template = composeTemplate(structured.value)
  editMode.value = 'raw'
}

function composeTemplate(s: {
  role: string
  skills: string
  goals: string
  outputFormat?: string
}) {
  const lines: string[] = []
  if (s.role?.trim()) lines.push(`- Role: ${s.role.trim()}`)
  if (s.skills?.trim()) lines.push(`- Skills: ${s.skills.trim()}`)
  if (s.goals?.trim()) {
    lines.push('- Goals:')
    const gl = s.goals
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter(Boolean)
    for (const g of gl) lines.push(`    - ${g}`)
  }
  // 知识库占位符引用
  if (selectedKnowledgeIds.value.length) {
    lines.push('\n- knowledge:')
    for (const kid of selectedKnowledgeIds.value) {
      const item = knowledgeItems.value.find((k) => k.id === kid)
      if (!item) continue
      if (knowledgeMode.value === 'id') {
        lines.push(`    - @KB{ id=${kid} }  # ${item.name}`)
      } else {
        lines.push(`    - @KB{ name=${item.name} }`)
      }
    }
  }
  if (s.outputFormat?.trim()) lines.push(`\n- OutputFormat: ${s.outputFormat.trim()}`)
  return lines.join('\n')
}

async function save() {
  // 如果在结构化模式，先同步
  if (editMode.value === 'structured') {
    form.value.template = composeTemplate(structured.value)
  }
  
  try {
    if (!form.value.name || !form.value.template) {
      ElMessage.warning('名称和模板内容不能为空')
      return
    }
    
    if (drawer.value.editing) {
      await updatePrompt(drawer.value.id, form.value)
      ElMessage.success('已更新')
    } else {
      await createPrompt(form.value)
      ElMessage.success('已创建')
    }
    drawer.value.visible = false
    fetchList()
  } catch (e: any) {
    ElMessage.error('保存失败')
  }
}

async function remove(row: Prompt) {
  try {
    await deletePrompt(row.id)
    ElMessage.success('已删除')
    fetchList()
  } catch (e: any) {
    ElMessage.error(e?.message || '删除失败')
  }
}

onMounted(() => {
  fetchList()
})
</script>

<style scoped>
.prompt-workshop {
  padding: 20px;
  height: 100%;
  display: flex;
  flex-direction: column;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.drawer-content {
  padding: 0 20px;
}
.mode-switch {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
}
.kb-selector {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.label {
  color: var(--el-text-color-regular);
}
.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
.template-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 5px;
}
</style>
