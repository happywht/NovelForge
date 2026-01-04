<template>
  <div v-if="store.isLoading" class="global-loading-bar">
    <div class="progress-track">
      <div 
        class="progress-fill" 
        :style="{ width: store.progress + '%' }"
      ></div>
    </div>
    <div class="loading-message" v-if="store.loadingMessage">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>{{ store.loadingMessage }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useGlobalStatusStore } from '@renderer/stores/useGlobalStatusStore'
import { Loading } from '@element-plus/icons-vue'

const store = useGlobalStatusStore()
</script>

<style scoped>
.global-loading-bar {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  z-index: 9999;
  pointer-events: none; /* 允许点击穿透 */
}

.progress-track {
  width: 100%;
  height: 3px;
  background: transparent;
}

.progress-fill {
  height: 100%;
  background: var(--el-color-primary);
  transition: width 0.3s ease;
  box-shadow: 0 0 8px var(--el-color-primary-light-5);
}

.loading-message {
  position: absolute;
  top: 12px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--el-bg-color-overlay);
  padding: 6px 16px;
  border-radius: 20px;
  box-shadow: var(--el-box-shadow-light);
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--el-text-color-regular);
  border: 1px solid var(--el-border-color-lighter);
  pointer-events: auto; /* 消息框可交互 */
}
</style>
