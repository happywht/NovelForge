<template>
  <el-form-item :label="label" :prop="prop">
    <template #label v-if="$slots.label">
      <slot name="label"></slot>
    </template>
    <el-switch
      :model-value="modelValue"
      :disabled="readonly"
      @update:modelValue="$emit('update:modelValue', $event)"
    />
    <div v-if="schema.description" class="field-desc">{{ schema.description }}</div>
  </el-form-item>
</template>

<script setup lang="ts">
import type { JSONSchema } from '@renderer/api/schema'

defineProps<{
  label: string
  prop: string
  schema: JSONSchema
  modelValue: boolean
  readonly?: boolean
}>()

defineEmits(['update:modelValue'])
</script>

<style scoped>
.field-desc {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
  line-height: 1.4;
}
</style>
