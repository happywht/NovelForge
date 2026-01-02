<template>
  <el-card shadow="never" class="array-field-card">
    <template #header>
      <div class="card-header">
        <slot name="label">
          <span>{{ label }}</span>
        </slot>
      </div>
    </template>

    <div v-if="!modelValue || modelValue.length === 0" class="empty-state">
      <p>暂无项目</p>
    </div>

    <div v-for="(item, index) in modelValue" :key="index" class="array-item">
      <div class="array-item-content">
        <!-- 对于简单类型，直接使用对应的字段组件 -->
        <component
          v-if="isSimpleTypeForIndex(index)"
          :is="getSimpleFieldComponentForIndex(index)"
          :label="`项目 ${index + 1}`"
          :prop="String(index)"
          :schema="getItemSchemaForIndex(index)"
          :model-value="item"
          :root-schema="rootSchema"
          :readonly="readonly"
          @update:modelValue="updateItem(index, $event)"
        />
        <!-- 对于复杂类型，使用ModelDrivenForm -->
        <ModelDrivenForm
          v-else
          :schema="getItemSchemaForIndex(index)"
          :model-value="item"
          :display-name-map="displayNameMap"
          :root-schema="rootSchema"
          :readonly-fields="readonly ? Object.keys(item || {}) : []"
          @update:modelValue="updateItem(index, $event)"
        />
      </div>
      <div class="array-item-actions" v-if="!readonly">
        <el-button
          type="danger"
          :icon="Delete"
          circle
          plain
          size="small"
          @click="removeItem(index)"
        />
      </div>
    </div>
    <el-button v-if="!readonly" type="primary" :icon="Plus" plain @click="addItem" class="add-button">
      添加 {{ (displayNameMap && displayNameMap[itemSchema.title || '']) || itemSchema.title || '新项目' }}
    </el-button>
  </el-card>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent } from 'vue'
import { type JSONSchema } from '@renderer/api/schema'
import { Delete, Plus } from '@element-plus/icons-vue'
import { resolveActualSchema, createDefaultValue, matchSchemaForValue } from '@renderer/services/schemaFieldParser'

const ModelDrivenForm = defineAsyncComponent(() => import('../ModelDrivenForm.vue'))
const StringField = defineAsyncComponent(() => import('./StringField.vue'))
const NumberField = defineAsyncComponent(() => import('./NumberField.vue'))
const BooleanField = defineAsyncComponent(() => import('./BooleanField.vue'))

const props = defineProps<{
  modelValue: any[] | undefined
  label: string
  schema: JSONSchema
  displayNameMap?: Record<string, string>
  readonly?: boolean
  contextData?: Record<string, any>
  ownerId?: number | null
  rootSchema?: JSONSchema
}>()

const emit = defineEmits(['update:modelValue'])

const itemSchema = computed((): JSONSchema => {
  if (props.schema.items) {
    return resolveActualSchema(props.schema.items, props.schema, props.rootSchema)
  }
  return { type: 'string', title: '项目' }
})

function getItemSchemaForIndex(index: number): JSONSchema {
  const base = itemSchema.value
  const value = (props.modelValue || [])[index]
  if ((base as any).anyOf) {
    return matchSchemaForValue((base as any).anyOf, value, props.rootSchema) as JSONSchema
  }
  return base
}

function isSimpleTypeForIndex(index: number) {
  const actualSchema = getItemSchemaForIndex(index)
  return actualSchema.type === 'string' || actualSchema.type === 'number' || actualSchema.type === 'integer' || actualSchema.type === 'boolean'
}

function getSimpleFieldComponentForIndex(index: number) {
  const actualSchema = getItemSchemaForIndex(index)
  switch (actualSchema.type) {
    case 'string':
      return StringField
    case 'number':
    case 'integer':
      return NumberField
    case 'boolean':
      return BooleanField
    default:
      return StringField
  }
}

function updateItem(index: number, newItem: any) {
  const newArray = [...(props.modelValue || [])]
  newArray[index] = newItem
  emit('update:modelValue', newArray)
}

function removeItem(index: number) {
  const newArray = [...(props.modelValue || [])]
  newArray.splice(index, 1)
  emit('update:modelValue', newArray)
}

function addItem() {
  const newArray = [...(props.modelValue || [])]
  const base = itemSchema.value
  
  const defaultValue = createDefaultValue(base, props.rootSchema)

  newArray.push(defaultValue)
  emit('update:modelValue', newArray)
}
</script>

<style scoped>
.array-field-card {
  margin-top: 10px;
  margin-bottom: 20px;
  background-color: var(--el-fill-color-lighter);
}
.empty-state {
  text-align: center;
  color: var(--el-text-color-secondary);
  padding: 20px 0;
}
.array-item {
  display: flex;
  align-items: flex-start;
  margin-bottom: 15px;
  padding: 15px;
  border: 1px dashed var(--el-border-color);
  border-radius: 4px;
}
.array-item-content {
  flex-grow: 1;
  padding-right: 15px;
}
.array-item-actions {
  flex-shrink: 0;
}
.add-button {
  margin-top: 10px;
  width: 100%;
}
</style>