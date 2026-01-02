<template>
  <el-form-item :label="label" :prop="prop">
    <template v-if="$slots.label" #label>
      <slot name="label"></slot>
    </template>
    <div class="tuple-field-wrapper">
      <div v-for="(itemSchema, index) in itemSchemas" :key="index" class="tuple-item">
        <component
          :is="getFieldComponent(itemSchema)"
          :model-value="modelValue ? modelValue[index] : undefined"
          :schema="itemSchema"
          :root-schema="rootSchema"
          :readonly="readonly"
          label=""
          prop=""
          @update:model-value="updateItem(index, $event)"
        />
      </div>
    </div>
  </el-form-item>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent } from 'vue'
import type { JSONSchema } from '@renderer/api/schema'

// 避免循环依赖
const StringField = defineAsyncComponent(() => import('./StringField.vue'))
const NumberField = defineAsyncComponent(() => import('./NumberField.vue'))
const FallbackField = defineAsyncComponent(() => import('./FallbackField.vue'))

const props = defineProps<{
  modelValue: any[] | undefined
  label: string
  prop: string
  schema: JSONSchema
  rootSchema?: JSONSchema
  readonly?: boolean
}>()

const emit = defineEmits(['update:modelValue'])

// 根据 schema 确定元组每个元素的 schema
const itemSchemas = computed((): JSONSchema[] => {
  return props.schema.prefixItems || props.schema.anyOf || []
})

// 动态获取元组中每个元素应该使用的字段组件
function getFieldComponent(itemSchema: JSONSchema) {
  switch (itemSchema.type) {
    case 'string':
      return StringField
    case 'number':
    case 'integer':
      return NumberField
    default:
      return FallbackField
  }
}

function updateItem(index: number, value: any) {
  const newTuple = [...(props.modelValue || [])]
  newTuple[index] = value
  emit('update:modelValue', newTuple)
}
</script>

<style scoped>
.tuple-field-wrapper {
  display: flex;
  gap: 10px;
  width: 100%;
}

.tuple-item {
  flex-grow: 1;
}

/* 移除内联字段的 el-form-item 默认边距 */
:deep(.el-form-item) {
  margin-bottom: 0;
}
</style>
