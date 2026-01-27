<template>
  <el-tooltip :content="isFullscreen ? '退出全屏 (F11)' : '全屏模式 (F11)'" placement="bottom">
    <el-button
      :icon="isFullscreen ? FullScreen : FullScreen"
      :type="isFullscreen ? 'primary' : 'default'"
      circle
      @click="$emit('toggle')"
    >
      <el-icon>
        <component :is="isFullscreen ? 'CloseBold' : 'FullScreen'" />
      </el-icon>
    </el-button>
  </el-tooltip>
</template>

<script setup lang="ts">
import { FullScreen } from '@element-plus/icons-vue'

defineProps<{
  isFullscreen: boolean
}>()

defineEmits<{
  toggle: []
}>()
</script>

<style scoped>
.el-button {
  transition: all 0.3s ease;
}
</style>
