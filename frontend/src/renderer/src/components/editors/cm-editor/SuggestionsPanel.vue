<template>
  <div class="suggestions-panel">
    <div class="panel-header">
      <span class="title">AI 建议 ({{ suggestions.length }})</span>
      <el-button v-if="suggestions.length > 0" type="primary" link @click="clearAll">全部忽略</el-button>
    </div>

    <div v-if="suggestions.length === 0" class="empty-state">
      <el-empty description="暂无新建议" :image-size="60" />
    </div>

    <div v-else class="suggestions-list">
      <el-card 
        v-for="item in suggestions" 
        :key="item.id" 
        class="suggestion-card" 
        shadow="hover"
      >
        <template #header>
          <div class="card-header">
            <div class="header-left">
              <el-tag :type="item.type === 'dynamic_info' ? 'success' : 'warning'" size="small">
                {{ item.type === 'dynamic_info' ? '属性' : '关系' }}
              </el-tag>
              <span class="suggestion-title">{{ item.title }}</span>
            </div>
            <span class="time">{{ formatTime(item.timestamp) }}</span>
          </div>
        </template>

        <div class="suggestion-content">
          <p class="description">{{ item.description }}</p>
          
          <!-- 动态信息预览 -->
          <div v-if="item.type === 'dynamic_info'" class="details">
            <div v-for="role in item.data.info_list" :key="role.name" class="role-item">
              <div class="role-name">{{ role.name }}</div>
              <ul class="info-list">
                <li v-for="(vals, key) in role.dynamic_info" :key="key">
                  <span class="info-key">{{ key }}:</span>
                  <span class="info-vals">{{ vals.map((v: any) => v.info).join(', ') }}</span>
                </li>
              </ul>
            </div>
          </div>

          <!-- 关系预览 -->
          <div v-if="item.type === 'relation'" class="details">
            <ul class="relation-list">
              <li v-for="(rel, idx) in item.data.relations" :key="idx">
                {{ rel.a }} <el-icon><Right /></el-icon> {{ rel.b }} ({{ rel.kind }})
              </li>
            </ul>
          </div>
        </div>

        <div class="card-actions">
          <el-button size="small" @click="removeSuggestion(item.id)">忽略</el-button>
          <el-button 
            size="small" 
            type="primary" 
            :loading="loading" 
            @click="handleApprove(item)"
          >采纳</el-button>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useSuggestionsStore, type Suggestion } from '@renderer/stores/useSuggestionsStore'
import { useProjectStore } from '@renderer/stores/useProjectStore'
import { Right } from '@element-plus/icons-vue'
import dayjs from 'dayjs'

const props = defineProps<{
  context?: {
    participants?: string[]
    volume_number?: number
    chapter_number?: number
  }
}>()

const suggestionsStore = useSuggestionsStore()
const projectStore = useProjectStore()
const { suggestions, loading } = storeToRefs(suggestionsStore)
const { approveSuggestion, removeSuggestion, clearAll } = suggestionsStore

const handleApprove = async (item: Suggestion): Promise<void> => {
  const projectId = projectStore.currentProject?.id
  if (!projectId) return
  await approveSuggestion(item, projectId, props.context)
}

const formatTime = (ts: number): string => {
  return dayjs(ts).format('HH:mm')
}
</script>

<style scoped>
.suggestions-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 12px;
  background-color: var(--el-bg-color-page);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.panel-header .title {
  font-weight: 600;
  font-size: 14px;
}

.suggestions-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.suggestion-card {
  border-radius: 8px;
}

.suggestion-card :deep(.el-card__header) {
  padding: 8px 12px;
  background-color: var(--el-fill-color-light);
}

.suggestion-card :deep(.el-card__body) {
  padding: 12px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.suggestion-title {
  font-size: 13px;
  font-weight: 500;
}

.time {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.suggestion-content {
  margin-bottom: 12px;
}

.description {
  font-size: 12px;
  color: var(--el-text-color-regular);
  margin-bottom: 8px;
}

.details {
  background-color: var(--el-fill-color-lighter);
  padding: 8px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 200px;
  overflow-y: auto;
}

.role-item {
  margin-bottom: 8px;
}

.role-name {
  font-weight: 600;
  color: var(--el-color-primary);
  margin-bottom: 4px;
}

.info-list, .relation-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.info-key {
  color: var(--el-text-color-secondary);
  margin-right: 4px;
}

.card-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
  padding-top: 8px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.empty-state {
  margin-top: 60px;
}
</style>
