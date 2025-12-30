<template>
  <div class="history-panel">
    <div class="panel-header">
      <div class="header-left">
        <el-icon class="header-icon"><Clock /></el-icon>
        <h3 class="panel-title">生成历史</h3>
      </div>
      <el-button size="small" :loading="loading" @click="fetchHistory">
        <el-icon><Refresh /></el-icon> 刷新
      </el-button>
    </div>

    <div class="panel-content custom-scrollbar">
      <div v-if="historyList.length > 0" class="history-list">
        <div v-for="item in historyList" :key="item.id" class="history-item">
          <div class="item-header">
            <span class="item-time">{{ formatTime(item.created_at) }}</span>
            <el-tag size="small" effect="plain" class="prompt-tag">{{ item.prompt_name }}</el-tag>
          </div>
          <div class="item-preview" @click="viewDetail(item)">
            {{ item.content.substring(0, 150) }}{{ item.content.length > 150 ? '...' : '' }}
          </div>
          <div class="item-actions">
            <el-button size="small" link type="primary" @click="viewDetail(item)">查看详情</el-button>
            <el-button size="small" link type="warning" @click="confirmRestore(item)">恢复此版本</el-button>
          </div>
        </div>
      </div>
      <el-empty v-else description="暂无生成历史" :image-size="80" />
    </div>

    <!-- 详情对话框 -->
    <el-dialog v-model="detailVisible" title="历史版本详情" width="700px" append-to-body destroy-on-close>
      <div class="detail-info">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="生成时间">{{ formatTime(selectedItem?.created_at || '') }}</el-descriptions-item>
          <el-descriptions-item label="提示词">{{ selectedItem?.prompt_name }}</el-descriptions-item>
          <el-descriptions-item label="LLM ID">{{ selectedItem?.llm_config_id }}</el-descriptions-item>
          <el-descriptions-item label="模式">{{ selectedItem?.meta_data?.stream ? '流式' : '非流式' }}</el-descriptions-item>
        </el-descriptions>
      </div>
      <div class="detail-content">
        <div class="content-label">生成内容：</div>
        <div class="content-box custom-scrollbar">
          <pre class="content-text">{{ selectedItem?.content }}</pre>
        </div>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button type="warning" @click="confirmRestore(selectedItem)">恢复此版本</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { getCardGenerationHistory, restoreCardGeneration, type GenerationHistory } from '@renderer/api/cards'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Clock, Refresh } from '@element-plus/icons-vue'
import dayjs from 'dayjs'

const props = defineProps<{ cardId?: number }>()
const emit = defineEmits<{ (e: 'restored', content: any): void }>()

const loading = ref(false)
const historyList = ref<GenerationHistory[]>([])
const detailVisible = ref(false)
const selectedItem = ref<GenerationHistory | null>(null)

async function fetchHistory() {
  if (!props.cardId) {
    historyList.value = []
    return
  }
  try {
    loading.value = true
    const list = await getCardGenerationHistory(props.cardId)
    // 按时间倒序排列
    historyList.value = (list || []).sort((a, b) => 
      new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    )
  } catch (e) {
    console.error('Fetch history error:', e)
    ElMessage.error('获取历史记录失败')
  } finally {
    loading.value = false
  }
}

function formatTime(time: string) {
  if (!time) return ''
  return dayjs(time).format('YYYY-MM-DD HH:mm:ss')
}

function viewDetail(item: GenerationHistory) {
  selectedItem.value = item
  detailVisible.value = true
}

async function confirmRestore(item: GenerationHistory | null) {
  if (!item || !props.cardId) return
  try {
    await ElMessageBox.confirm('确定要恢复到此版本吗？当前卡片内容将被覆盖。', '恢复确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    const res = await restoreCardGeneration(props.cardId, item.id)
    if (res.success) {
      ElMessage.success('已恢复到历史版本')
      emit('restored', res.content)
      detailVisible.value = false
    }
  } catch (e) {
    if (e !== 'cancel') {
      console.error('Restore error:', e)
      ElMessage.error('恢复失败')
    }
  }
}

watch(() => props.cardId, () => {
  fetchHistory()
}, { immediate: true })

onMounted(() => {
  fetchHistory()
})
</script>

<style scoped>
.history-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--el-bg-color);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--el-fill-color-lighter);
  border-bottom: 1px solid var(--el-border-color-light);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-icon {
  color: var(--el-color-primary);
  font-size: 18px;
}

.panel-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}

.panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.history-item {
  padding: 12px;
  background: var(--el-bg-color-overlay);
  border-radius: 8px;
  border: 1px solid var(--el-border-color-lighter);
  transition: all 0.2s;
}

.history-item:hover {
  border-color: var(--el-color-primary-light-5);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.item-time {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-family: monospace;
}

.prompt-tag {
  font-size: 11px;
}

.item-preview {
  font-size: 13px;
  line-height: 1.5;
  color: var(--el-text-color-regular);
  cursor: pointer;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin-bottom: 8px;
  white-space: pre-wrap;
}

.item-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  border-top: 1px dashed var(--el-border-color-lighter);
  padding-top: 8px;
}

.detail-info {
  margin-bottom: 16px;
}

.content-label {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--el-text-color-primary);
}

.content-box {
  max-height: 400px;
  overflow-y: auto;
  padding: 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 4px;
  border: 1px solid var(--el-border-color-lighter);
}

.content-text {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--el-text-color-regular);
  white-space: pre-wrap;
  word-break: break-all;
  font-family: inherit;
}

.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: var(--el-border-color-lighter);
  border-radius: 3px;
}

.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: var(--el-border-color);
}
</style>
