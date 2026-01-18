<template>
  <el-dialog
    :model-value="visible"
    title="提示词测试"
    width="60%"
    append-to-body
    @update:model-value="(val) => emit('update:visible', val)"
  >
    <div class="test-container">
      <div class="config-row">
        <span class="label">测试模型:</span>
        <el-select v-model="selectedConfigId" placeholder="选择模型" style="width: 200px">
          <el-option
            v-for="c in llmConfigs"
            :key="c.id"
            :label="c.display_name || c.model_name"
            :value="c.id"
          />
        </el-select>
      </div>

      <div class="input-section">
        <div class="label">
          完整提示词预览 
          <el-tag size="small" type="info">只读</el-tag>
        </div>
        <el-input
          :model-value="finalPrompt"
          type="textarea"
          :rows="6"
          readonly
          resize="none"
          class="preview-input"
        />
      </div>

      <div class="input-section">
        <div class="label">用户输入 (User Message)</div>
        <el-input
          v-model="userInput"
          type="textarea"
          :rows="3"
          placeholder="模拟用户的输入内容..."
        />
      </div>

      <div class="output-section">
        <div class="label">
          模型响应
          <el-button
            type="primary"
            size="small"
            :loading="generating"
            :disabled="!selectedConfigId"
            @click="handleRun"
          >
            运行测试
          </el-button>
        </div>
        <div class="response-box" v-loading="generating">
          <pre v-if="response">{{ response }}</pre>
          <div v-else class="placeholder">等待运行...</div>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { listLLMConfigs, type LLMConfigRead } from '@renderer/api/setting'
import { ElMessage } from 'element-plus'
// We need an API to run ad-hoc chat. 
// Currently we don't have a direct "test prompt" API, but we can use the `chat` endpoint or similar.
// However, `chat` endpoint is complex. 
// Let's assume we can use a new simple endpoint or reuse `testLLMConnection` but that's for connection.
// Actually, we should probably add a simple "completion" API or use the existing `ai_tools` via some endpoint.
// For now, let's use a new API function `runPromptTest` which we will implement in `setting.ts` and backend.

import { runPromptTest } from '@renderer/api/setting'

const props = defineProps<{
  visible: boolean
  template: string
}>()

const emit = defineEmits<{
  'update:visible': [val: boolean]
}>()

const llmConfigs = ref<LLMConfigRead[]>([])
const selectedConfigId = ref<number>()
const userInput = ref('')
const response = ref('')
const generating = ref(false)

// Replace placeholders if any (simple replacement for display)
// In a real scenario, we might want to let user fill variables.
// For now, we just show the template as system prompt.
const finalPrompt = computed(() => {
  return props.template
})

onMounted(async () => {
  try {
    llmConfigs.value = await listLLMConfigs()
    if (llmConfigs.value.length > 0) {
      selectedConfigId.value = llmConfigs.value[0].id
    }
  } catch (e) {
    console.error(e)
  }
})

async function handleRun() {
  if (!selectedConfigId.value) return
  generating.value = true
  response.value = ''
  try {
    const res = await runPromptTest({
      llm_config_id: selectedConfigId.value,
      system_prompt: props.template,
      user_prompt: userInput.value
    })
    response.value = res
  } catch (e: any) {
    response.value = `Error: ${e.message || e}`
  } finally {
    generating.value = false
  }
}
</script>

<style scoped>
.test-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.config-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.label {
  font-weight: 500;
  margin-bottom: 4px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.response-box {
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 12px;
  min-height: 150px;
  max-height: 300px;
  overflow-y: auto;
  background-color: #f5f7fa;
}
.response-box pre {
  margin: 0;
  white-space: pre-wrap;
  font-family: inherit;
}
.placeholder {
  color: #909399;
  text-align: center;
  margin-top: 40px;
}
</style>
