<template>
  <el-form-item :label="label" :prop="prop">
    <template v-if="$slots.label" #label>
      <slot name="label"></slot>
    </template>
    <el-select
      :model-value="modelValue"
      :placeholder="placeholder"
      :disabled="readonly"
      clearable
      style="width: 100%"
      @update:model-value="emit('update:modelValue', $event)"
    >
      <el-option
        v-for="item in schema.enum"
        :key="String(item)"
        :label="String(item)"
        :value="item"
      />
    </el-select>
  </el-form-item>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { JSONSchema } from '@renderer/api/schema'

const props = defineProps<{
  modelValue: string | number | undefined
  label: string
  prop: string
  schema: JSONSchema
  readonly?: boolean
}>()

const emit = defineEmits(['update:modelValue'])

const placeholder = computed(() => {
  return props.schema.description || `请选择 ${props.label}`
})
</script>
