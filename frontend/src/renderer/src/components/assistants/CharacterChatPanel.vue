<template>
  <div class="character-chat-panel">
    <!-- 头部：角色选择与会话管理 -->
    <div class="chat-header">
      <el-select
        v-model="selectedCharacterId"
        placeholder="选择角色"
        size="small"
        class="character-select"
        @change="handleCharacterChange"
      >
        <el-option
          v-for="char in characters"
          :key="char.id"
          :label="char.title"
          :value="char.id"
        />
      </el-select>
      <el-button 
        type="primary" 
        link 
        size="small" 
        :disabled="!selectedCharacterId"
        @click="startNewChat"
      >
        <el-icon><Plus /></el-icon> 新对话
      </el-button>
    </div>

    <!-- 消息列表 -->
    <div class="message-list" ref="messageListRef">
      <div v-if="!currentSession" class="empty-state">
        <el-empty description="请选择角色并开始对话" :image-size="100" />
      </div>
      <template v-else>
        <div 
          v-for="msg in messages" 
          :key="msg.id" 
          class="message-item"
          :class="{ 'is-user': msg.role === 'user', 'is-assistant': msg.role === 'assistant' }"
        >
          <div class="message-avatar">
            <el-avatar :size="24" :icon="msg.role === 'user' ? UserFilled : Avatar" />
          </div>
          <div class="message-content">
            <div class="message-bubble">{{ msg.content }}</div>
          </div>
        </div>
        <div v-if="isLoading" class="message-item is-assistant">
           <div class="message-avatar">
            <el-avatar :size="24" :icon="Avatar" />
          </div>
          <div class="message-content">
            <div class="message-bubble loading-bubble">
              <span class="dot">.</span><span class="dot">.</span><span class="dot">.</span>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- 输入框 -->
    <div class="chat-input">
      <el-input
        v-model="inputMessage"
        type="textarea"
        :rows="3"
        placeholder="与角色对话..."
        resize="none"
        :disabled="!currentSession || isLoading"
        @keydown.enter.prevent="handleSend"
      />
      <div class="input-actions">
        <el-button 
          type="primary" 
          size="small" 
          :loading="isLoading" 
          :disabled="!currentSession || !inputMessage.trim()"
          @click="handleSend"
        >
          发送
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useCardStore } from '@renderer/stores/useCardStore'
import { storeToRefs } from 'pinia'
import { UserFilled, Avatar, Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import * as ChatAPI from '@renderer/api/chat'

const props = defineProps<{
  projectId: number
}>()

const cardStore = useCardStore()
const { cards } = storeToRefs(cardStore)

const selectedCharacterId = ref<number | null>(null)
const currentSession = ref<ChatAPI.ChatSession | null>(null)
const messages = ref<ChatAPI.ChatMessage[]>([])
const inputMessage = ref('')
const isLoading = ref(false)
const messageListRef = ref<HTMLElement | null>(null)

// 筛选角色卡片
const characters = computed(() => {
  return (cards.value || []).filter(c => c.card_type?.name?.includes('角色'))
})

// 加载会话
async function loadSessions() {
  if (!selectedCharacterId.value) return
  try {
    const sessions = await ChatAPI.listSessions(props.projectId)
    // 简单的过滤逻辑：找到该角色最新的会话
    const charSessions = sessions.filter(s => s.character_card_id === selectedCharacterId.value)
    if (charSessions.length > 0) {
      currentSession.value = charSessions[0]
      await loadMessages()
    } else {
      currentSession.value = null
      messages.value = []
    }
  } catch (e) {
    console.error('Failed to load sessions', e)
  }
}

async function loadMessages() {
  if (!currentSession.value) return
  try {
    messages.value = await ChatAPI.getSessionMessages(currentSession.value.id)
    scrollToBottom()
  } catch (e) {
    console.error('Failed to load messages', e)
  }
}

async function handleCharacterChange() {
  await loadSessions()
  if (!currentSession.value && selectedCharacterId.value) {
    // 自动创建新会话（可选，或者让用户点击）
    // await startNewChat()
  }
}

async function startNewChat() {
  if (!selectedCharacterId.value) return
  try {
    isLoading.value = true
    const char = characters.value.find(c => c.id === selectedCharacterId.value)
    currentSession.value = await ChatAPI.createSession({
      project_id: props.projectId,
      character_card_id: selectedCharacterId.value,
      title: `Chat with ${char?.title}`
    })
    messages.value = []
    isLoading.value = false
  } catch (e) {
    ElMessage.error('创建会话失败')
    isLoading.value = false
  }
}

async function handleSend() {
  if (!inputMessage.value.trim() || !currentSession.value || isLoading.value) return
  
  const content = inputMessage.value.trim()
  inputMessage.value = ''
  
  // 乐观更新
  const tempMsg: ChatAPI.ChatMessage = {
    id: -1,
    session_id: currentSession.value.id,
    role: 'user',
    content: content,
    created_at: new Date().toISOString()
  }
  messages.value.push(tempMsg)
  scrollToBottom()
  
  try {
    isLoading.value = true
    const aiMsg = await ChatAPI.sendMessage(currentSession.value.id, { content })
    // 替换最后一条消息（如果需要）或者重新加载
    // 这里简单起见，重新加载或追加
    messages.value = await ChatAPI.getSessionMessages(currentSession.value.id)
    scrollToBottom()
  } catch (e) {
    ElMessage.error('发送失败')
    // 回滚
    messages.value = messages.value.filter(m => m.id !== -1)
  } finally {
    isLoading.value = false
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (messageListRef.value) {
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight
    }
  })
}

watch(() => props.projectId, () => {
  selectedCharacterId.value = null
  currentSession.value = null
  messages.value = []
})
</script>

<style scoped>
.character-chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--el-bg-color);
}

.chat-header {
  padding: 8px 12px;
  border-bottom: 1px solid var(--el-border-color-light);
  display: flex;
  gap: 8px;
  align-items: center;
}

.character-select {
  flex: 1;
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.empty-state {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  color: var(--el-text-color-secondary);
}

.message-item {
  display: flex;
  gap: 8px;
  max-width: 90%;
}

.message-item.is-user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message-item.is-assistant {
  align-self: flex-start;
}

.message-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.message-bubble {
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.5;
  word-break: break-word;
  white-space: pre-wrap;
}

.is-user .message-bubble {
  background: var(--el-color-primary-light-9);
  color: var(--el-text-color-primary);
  border-top-right-radius: 2px;
}

.is-assistant .message-bubble {
  background: var(--el-fill-color-light);
  color: var(--el-text-color-regular);
  border-top-left-radius: 2px;
}

.loading-bubble {
  display: flex;
  gap: 2px;
}

.dot {
  animation: dot-blink 1.4s infinite both;
}

.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes dot-blink {
  0% { opacity: 0.2; }
  20% { opacity: 1; }
  100% { opacity: 0.2; }
}

.chat-input {
  padding: 12px;
  border-top: 1px solid var(--el-border-color-light);
  background: var(--el-bg-color);
}

.input-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}
</style>
