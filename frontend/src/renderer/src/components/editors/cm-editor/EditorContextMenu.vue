<template>
  <Teleport to="body">
    <div v-if="visible" class="context-menu-popup" :style="{ left: x + 'px', top: y + 'px' }">
      <div v-if="!expanded" class="context-menu-compact">
        <el-button type="primary" size="small" @click="$emit('expand')"> 快速编辑 </el-button>
      </div>
      <div v-else class="context-menu-expanded">
        <el-input
          v-model="internalRequirement"
          :autosize="{ minRows: 2, maxRows: 4 }"
          type="textarea"
          placeholder="描述你的要求，如：让语气更加强硬、增加环境描写..."
          size="small"
          style="margin-bottom: 8px"
        />
        <div class="context-menu-actions">
          <el-button
            type="primary"
            size="small"
            :loading="aiLoading"
            @click="$emit('polish', internalRequirement)"
          >
            <el-icon><Document /></el-icon> 润色
          </el-button>
          <el-button
            type="primary"
            size="small"
            :loading="aiLoading"
            @click="$emit('expand-text', internalRequirement)"
          >
            <el-icon><MagicStick /></el-icon> 扩写
          </el-button>
          <el-button size="small" @click="$emit('close')"> 取消 </el-button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Document, MagicStick } from '@element-plus/icons-vue'

const props = defineProps<{
  visible: boolean
  expanded: boolean
  x: number
  y: number
  requirement: string
  aiLoading: boolean
}>()

const emit = defineEmits<{
  (e: 'update:requirement', val: string): void
  (e: 'polish', requirement: string): void
  (e: 'expand-text', requirement: string): void
  (e: 'expand'): void
  (e: 'close'): void
}>()

const internalRequirement = ref(props.requirement)

watch(
  () => props.requirement,
  (val) => {
    internalRequirement.value = val
  }
)

watch(
  () => internalRequirement.value,
  (val) => {
    emit('update:requirement', val)
  }
)
</script>

<style scoped>
.context-menu-popup {
  position: fixed;
  z-index: 3000;
  background: var(--el-bg-color-overlay);
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  box-shadow: var(--el-box-shadow-light);
  padding: 12px;
  min-width: 240px;
  display: flex;
  flex-direction: column;
}

.context-menu-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
