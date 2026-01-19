<template>
  <div class="knowledge-manager">
    <div class="header">
      <h4>知识库</h4>
      <div class="actions">
        <el-button size="small" @click="handleImportClick">导入</el-button>
        <el-button size="small" @click="handleExportAll">导出全部</el-button>
        <el-button type="primary" size="small" @click="openEditor()">新建知识</el-button>
      </div>
    </div>
    
    <!-- 隐藏的文件输入框 -->
    <input
      ref="fileInput"
      type="file"
      accept=".json,.md,.txt"
      style="display: none"
      @change="onFileSelected"
    />

    <el-table v-loading="loading" :data="items" height="60vh" size="small">
      <el-table-column prop="name" label="名称" width="150" />
      <el-table-column prop="description" label="描述" min-width="150" />
      <el-table-column label="内置" width="80">
        <template #default="{ row }">
          <el-tag size="small" :type="row.built_in ? 'info' : 'success'">{{
            row.built_in ? '内置' : '自定义'
          }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" align="right">
        <template #default="{ row }">
          <el-button size="small" @click="handleExportOne(row)">导出</el-button>
          <el-button size="small" @click="openEditor(row)">编辑</el-button>
          <el-popconfirm title="删除该知识？" @confirm="remove(row)">
            <template #reference>
              <el-button size="small" type="danger" plain :disabled="row.built_in">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <!-- ... dialog ... -->
    <el-dialog
      v-model="editor.visible"
      :title="editor.editing ? '编辑知识' : '新建知识'"
      width="50%"
      append-to-body
    >
      <el-form label-position="top" :model="editor.form">
        <el-form-item label="名称"
          ><el-input v-model="editor.form.name" :disabled="editor.editing && editor.form.built_in"
        /></el-form-item>
        <el-form-item label="描述"
          ><el-input v-model="editor.form.description" type="textarea" :rows="2"
        /></el-form-item>
        <el-form-item label="内容"
          ><el-input v-model="editor.form.content" type="textarea" :rows="14"
        /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editor.visible = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  listKnowledge,
  createKnowledge,
  updateKnowledge,
  deleteKnowledge,
  type Knowledge
} from '@renderer/api/setting'

const loading = ref(false)
const items = ref<Knowledge[]>([])
const fileInput = ref<HTMLInputElement>()

const editor = ref<{ visible: boolean; editing: boolean; form: Partial<Knowledge> }>({
  visible: false,
  editing: false,
  form: {}
})

async function fetchList() {
  loading.value = true
  try {
    items.value = await listKnowledge()
  } catch (e: any) {
    ElMessage.error('加载知识库失败')
  } finally {
    loading.value = false
  }
}

function openEditor(row?: Knowledge) {
  editor.value.visible = true
  editor.value.editing = !!row
  editor.value.form = row ? { ...row } : { name: '', description: '', content: '' }
}

async function save() {
  try {
    const f = editor.value.form
    if (!f?.name || !f.content) {
      ElMessage.warning('请填写名称与内容')
      return
    }
    if (editor.value.editing && f.id) {
      const saved = await updateKnowledge(f.id, {
        name: f.name,
        description: f.description || '',
        content: f.content
      })
      ElMessage.success('已更新')
      // 局部更新
      if (saved) {
        const idx = items.value.findIndex((i) => i.id === saved.id)
        if (idx >= 0) items.value[idx] = saved
      }
    } else {
      const created = await createKnowledge({
        name: f.name,
        description: f.description || '',
        content: f.content
      })
      ElMessage.success('已创建')
      if (created) items.value.unshift(created)
    }
    editor.value.visible = false
  } catch (e: any) {
    ElMessage.error('保存失败')
  }
}

async function remove(row: Knowledge) {
  try {
    await deleteKnowledge(row.id)
    ElMessage.success('已删除')
    items.value = items.value.filter((i) => i.id !== row.id)
  } catch (e: any) {
    ElMessage.error(e?.message || '删除失败')
  }
}

// ---- Import / Export ----

function handleImportClick() {
  fileInput.value?.click()
}

async function onFileSelected(e: Event) {
  const files = (e.target as HTMLInputElement).files
  if (!files || files.length === 0) return
  
  const file = files[0]
  const reader = new FileReader()
  reader.onload = async (ev) => {
    try {
      const text = ev.target?.result as string
      if (file.name.endsWith('.json')) {
        // 尝试解析 JSON
        const data = JSON.parse(text)
        if (Array.isArray(data)) {
          // 批量导入
          let count = 0
          for (const item of data) {
            if (item.name && item.content) {
              await createKnowledge({
                name: item.name,
                description: item.description || '',
                content: item.content
              })
              count++
            }
          }
          ElMessage.success(`成功导入 ${count} 条知识`)
        } else if (data.name && data.content) {
          // 单条导入
          await createKnowledge({
            name: data.name,
            description: data.description || '',
            content: data.content
          })
          ElMessage.success('导入成功')
        }
      } else {
        // 视为纯文本/Markdown，文件名作为标题
        const name = file.name.replace(/\.(md|txt)$/i, '')
        await createKnowledge({
          name: name,
          description: 'Imported from file',
          content: text
        })
        ElMessage.success('导入成功')
      }
      fetchList()
    } catch (err) {
      ElMessage.error('导入失败：文件格式错误')
    } finally {
      // 重置 input
      if (fileInput.value) fileInput.value.value = ''
    }
  }
  reader.readAsText(file)
}

function handleExportOne(row: Knowledge) {
  const data = JSON.stringify(row, null, 2)
  downloadFile(data, `${row.name}.json`, 'application/json')
}

function handleExportAll() {
  const data = JSON.stringify(items.value, null, 2)
  downloadFile(data, 'knowledge_base_export.json', 'application/json')
}

function downloadFile(content: string, filename: string, type: string) {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

fetchList()
</script>

<style scoped>
.knowledge-manager {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
