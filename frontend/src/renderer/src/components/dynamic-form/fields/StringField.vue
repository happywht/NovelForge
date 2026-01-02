<template>
  <el-form-item :label="label" :prop="prop">
    <template v-if="$slots.label" #label>
      <slot name="label"></slot>
    </template>
    <el-input
      v-if="!isLongText"
      :model-value="modelValue"
      :placeholder="placeholder"
      :disabled="readonly"
      clearable
      @update:model-value="emit('update:modelValue', $event)"
    />
    <el-input
      v-else
      type="textarea"
      :model-value="modelValue"
      :placeholder="placeholder"
      :autosize="{ minRows: 3, maxRows: 10 }"
      :disabled="readonly"
      clearable
      @update:model-value="emit('update:modelValue', $event)"
    />
  </el-form-item>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { JSONSchema } from '@renderer/api/schema'

const props = defineProps<{
  modelValue: string | undefined
  label: string
  prop: string
  schema: JSONSchema
  readonly?: boolean
}>()

const emit = defineEmits(['update:modelValue'])

// 一个简单的启发式方法：如果描述或标题表明它是一个长文本字段，则使用文本区域。
const isLongText = computed(() => {
  if (props.schema.minLength !== undefined && props.schema.minLength > 50) {
    return true
  }
  const description = props.schema.description?.toLowerCase() || ''
  const title = props.schema.title?.toLowerCase() || ''
  if (props.prop === 'overview' || props.prop === 'content') return true
  return (
    description.includes('思考') ||
    description.includes('过程') ||
    description.includes('描述') ||
    description.includes('概述') ||
    title.includes('thinking')
  )
})

const placeholder = computed(() => {
  return props.schema.description || `请输入 ${props.label}`
})
</script>
