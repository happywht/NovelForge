<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useProjectStore } from '@renderer/stores/useProjectStore'
import { useCardStore } from '@renderer/stores/useCardStore'
import { reverseImport, reversePreview } from '@renderer/api/projects'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
}>()

const projectStore = useProjectStore()
const cardStore = useCardStore()

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

const importForm = ref({
  text: '',
  regex_pattern: '(第[一二三四五六七八九十百千万零\\d]+[章节回].*)',
  autoAnalyze: true,
  generateOutlines: true
})

const fileName = ref('')
const isImporting = ref(false)
const isPreviewing = ref(false)
const previewChapters = ref<any[]>([])

async function handleFileChange(file: any) {
  if (!file) return
  fileName.value = file.name
  const reader = new FileReader()
  reader.onload = (e) => {
    importForm.value.text = e.target?.result as string
    handlePreview() // 自动预览
  }
  reader.readAsText(file.raw)
}

async function handlePreview() {
  if (!importForm.value.text) return
  
  const projectId = projectStore.currentProject?.id
  if (!projectId) return

  isPreviewing.value = true
  try {
    const res = await reversePreview(projectId, {
      text: importForm.value.text,
      regex_pattern: importForm.value.regex_pattern
    })
    previewChapters.value = res.data.chapters
  } catch (err: any) {
    ElMessage.error(`预览失败: ${err.message}`)
  } finally {
    isPreviewing.value = false
  }
}

// 监听正则变化自动刷新预览
watch(() => importForm.value.regex_pattern, () => {
  if (importForm.value.text) {
    handlePreview()
  }
})

async function startImport() {
  if (!importForm.value.text) {
    ElMessage.warning('请先上传小说文本')
    return
  }

  const projectId = projectStore.currentProject?.id
  if (!projectId) return

  isImporting.value = true
  try {
    const res = await reverseImport(projectId, {
      text: importForm.value.text,
      regex_pattern: importForm.value.regex_pattern
    })
    
    ElMessage.success(res.message || '导入成功')
    await cardStore.fetchCards(projectId)
    
    if (importForm.value.autoAnalyze) {
      await runBatchAnalyze(res.data.created_card_ids)
    }
    
    dialogVisible.value = false
  } catch (err: any) {
    ElMessage.error(`导入失败: ${err.message}`)
  } finally {
    isImporting.value = false
  }
}

async function runBatchAnalyze(cardIds: number[]) {
  if (!cardIds || cardIds.length === 0) return

  const projectId = projectStore.currentProject?.id
  if (!projectId) return

  const loading = ElMessage({
    message: `正在准备对 ${cardIds.length} 个新章节进行 AI 深度分析...`,
    type: 'info',
    duration: 0
  })

  try {
    const { listWorkflows, runWorkflow } = await import('@renderer/api/workflows')
    const workflows = await listWorkflows()
    const wf = workflows.find((w) => w.name === '智能章节审计与同步')

    if (!wf?.id) {
      loading.close()
      ElMessage.warning('未找到分析工作流，跳过自动分析')
      return
    }

    let successCount = 0
    let failCount = 0

    const allCards = cardStore.cards

    for (let i = 0; i < cardIds.length; i++) {
      const cardId = cardIds[i]
      const card = allCards.find(c => c.id === cardId)
      const title = card?.title || `第 ${i+1} 章`
      
      ;(loading as any).message = `正在分析第 ${i + 1}/${cardIds.length} 章: ${title}...`

      try {
        await runWorkflow(wf.id, {
          scope_json: {
            project_id: projectId,
            card_id: cardId,
            self_id: cardId,
            chapter_number: i + 1
          },
          params_json: {}
        })
        successCount++
      } catch (err) {
        console.error(`Failed to analyze card ${cardId}:`, err)
        failCount++
      }
    }

    loading.close()
    ElMessageBox.alert(
      `反向工程完成！\n成功导入并分析了 ${successCount} 个章节。\n系统已为您自动生成了章节大纲、角色卡和初步设定。`,
      '分析完成',
      { confirmButtonText: '太棒了' }
    )
  } catch (e) {
    loading.close()
    ElMessage.error('自动分析过程中发生错误')
    console.error('Batch analyze failed:', e)
  }
}
</script>

<template>
  <el-dialog v-model="dialogVisible" title="反向工程 (AI 智能拆解与分析)" width="800px">
    <div class="dialog-content">
      <div class="left-panel">
        <el-form :model="importForm" label-position="top">
          <el-form-item label="上传小说正文 (TXT)">
            <el-upload
              class="upload-demo"
              drag
              action="#"
              :auto-upload="false"
              :on-change="handleFileChange"
              :limit="1"
            >
              <el-icon class="el-icon--upload"><upload-filled /></el-icon>
              <div class="el-upload__text">
                将文件拖到此处，或 <em>点击上传</em>
              </div>
            </el-upload>
          </el-form-item>
          
          <el-form-item label="章节切分正则">
            <el-input v-model="importForm.regex_pattern" placeholder="请输入正则表达式"></el-input>
          </el-form-item>

          <el-form-item>
            <el-checkbox v-model="importForm.autoAnalyze">导入后立即启动 AI 深度分析</el-checkbox>
            <div class="sub-options" v-if="importForm.autoAnalyze">
              <el-checkbox v-model="importForm.generateOutlines" disabled>包含章节大纲生成 (已集成)</el-checkbox>
              <div class="help-text">分析过程中将自动提取角色、关系并生成章节梗概。</div>
            </div>
          </el-form-item>
        </el-form>
      </div>

      <div class="right-panel">
        <div class="preview-header">
          <span>章节预览 (共 {{ previewChapters.length }} 章)</span>
          <el-button link type="primary" @click="handlePreview" :loading="isPreviewing">刷新预览</el-button>
        </div>
        <div class="preview-list" v-loading="isPreviewing">
          <el-table :data="previewChapters" height="400px" size="small">
            <el-table-column label="章节标题" prop="title" show-overflow-tooltip></el-table-column>
            <el-table-column label="字数" width="100">
              <template #default="{ row }">
                {{ row.content?.length || 0 }} 字
              </template>
            </el-table-column>
          </el-table>
          <div v-if="previewChapters.length === 0 && !isPreviewing" class="empty-preview">
            暂无预览内容，请上传文件
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="isImporting" @click="startImport" :disabled="previewChapters.length === 0">
        {{ isImporting ? '正在导入并分析...' : '开始导入' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script lang="ts">
import { UploadFilled } from '@element-plus/icons-vue'
export default {
  components: {
    UploadFilled
  }
}
</script>

<style scoped>
.dialog-content {
  display: flex;
  gap: 20px;
}
.left-panel {
  flex: 1;
}
.right-panel {
  flex: 1;
  border-left: 1px solid #dcdfe6;
  padding-left: 20px;
}
.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  font-weight: bold;
}
.preview-list {
  border: 1px solid #ebeef5;
  border-radius: 4px;
}
.empty-preview {
  height: 400px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
}
.sub-options {
  margin-left: 24px;
  margin-top: 5px;
}
.help-text {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
.upload-demo {
  width: 100%;
}
</style>
