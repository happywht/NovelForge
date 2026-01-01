<template>
  <div class="ctx-panel">
    <div class="panel-header">
      <div class="header-left">
        <el-icon class="header-icon"><Connection /></el-icon>
        <h3 class="panel-title">上下文感知</h3>
      </div>
      <div class="header-right">
        <el-radio-group v-model="viewMode" size="small" class="view-toggle">
          <el-radio-button value="list"><el-icon><Memo /></el-icon></el-radio-button>
          <el-radio-button value="graph"><el-icon><Share /></el-icon></el-radio-button>
        </el-radio-group>
        <el-button size="small" type="primary" :loading="assembling" @click="assemble">
          <el-icon><Refresh /></el-icon> 刷新装配
        </el-button>
      </div>
    </div>
    
    <div v-if="viewMode === 'list'" class="controls">
      <el-form label-position="top" size="small">
        <el-form-item label="当前参与实体">
          <el-select v-model="localParticipants" multiple filterable allow-create default-first-option placeholder="输入或选择参与者" @change="onParticipantsChange" class="participant-select">
            <el-option-group v-for="g in participantGroups" :key="g.label" :label="g.label">
              <el-option v-for="p in g.values" :key="p" :label="p" :value="p" />
            </el-option-group>
          </el-select>
        </el-form-item>
      </el-form>
    </div>

    <div class="panel-content custom-scrollbar" :class="{ 'is-graph': viewMode === 'graph' }">
      <template v-if="viewMode === 'graph'">
        <KGVisualization v-if="projectId" :project-id="projectId" />
        <el-empty v-else description="未选择项目" />
      </template>
      <div v-else-if="assembled" class="assembled-container">
        <!-- 写作指南部分 -->
        <div v-if="assembled.writing_guide" class="section writing-guide-section">
          <div class="section-header">
            <el-icon><EditPen /></el-icon>
            <span class="section-title">写作指南</span>
          </div>
          <div class="guide-content">{{ assembled.writing_guide }}</div>
        </div>

        <!-- 结构化事实部分 -->
        <div v-if="assembled.facts_structured" class="section facts-section">
          <div class="section-header">
            <el-icon><Memo /></el-icon>
            <span class="section-title">关键事实</span>
          </div>
          
          <div v-if="Array.isArray(assembled.facts_structured.fact_summaries) && assembled.facts_structured.fact_summaries.length > 0" class="sub-section">
            <ul class="fact-list">
              <li v-for="(f, i) in assembled.facts_structured.fact_summaries" :key="i" class="fact-item">
                <el-icon class="bullet"><CircleCheck /></el-icon>
                <span>{{ f }}</span>
              </li>
            </ul>
          </div>

          <div v-if="Array.isArray(assembled.facts_structured.relation_summaries) && assembled.facts_structured.relation_summaries.length > 0" class="sub-section">
            <div class="sub-title">实体关系</div>
            <div v-for="(r, idx) in assembled.facts_structured.relation_summaries" :key="idx" class="relation-card">
              <div class="relation-main">
                <span class="entity-name">{{ r.a }}</span>
                <el-tag size="small" effect="plain" class="relation-kind">{{ r.kind }}</el-tag>
                <span class="entity-name">{{ r.b }}</span>
                <el-tag v-if="r.stance" size="small" :type="getStanceType(r.stance)" class="stance-tag">{{ r.stance }}</el-tag>
              </div>
              
              <div v-if="r.description" class="relation-desc">{{ r.description }}</div>
              
              <div v-if="r.a_to_b_addressing || r.b_to_a_addressing" class="addressing-box">
                <div v-if="r.a_to_b_addressing" class="addr-item">
                  <span class="addr-label">{{ r.a }} 称呼 {{ r.b }}：</span>
                  <span class="addr-val">{{ r.a_to_b_addressing }}</span>
                </div>
                <div v-if="r.b_to_a_addressing" class="addr-item">
                  <span class="addr-label">{{ r.b }} 称呼 {{ r.a }}：</span>
                  <span class="addr-val">{{ r.b_to_a_addressing }}</span>
                </div>
              </div>

              <div v-if="r.recent_dialogues?.length" class="dialogue-section">
                <div class="mini-label">对话样例</div>
                <div v-for="(d, i) in r.recent_dialogues.slice(0, 2)" :key="i" class="dialogue-item">
                  "{{ d }}"
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 原始子图部分 -->
        <div class="section raw-section">
          <div class="section-header" @click="showRaw = !showRaw">
            <el-icon><Cpu /></el-icon>
            <span class="section-title">原始事实子图</span>
            <el-icon class="toggle-icon" :class="{ 'is-active': showRaw }"><ArrowRight /></el-icon>
          </div>
          <el-collapse-transition>
            <div v-show="showRaw" class="raw-content">
              <pre class="code-block">{{ assembled.facts_subgraph || '暂无数据' }}</pre>
            </div>
          </el-collapse-transition>
        </div>
      </div>
      
      <div v-else-if="!assembling" class="empty-state">
        <el-empty description="尚未装配上下文" :image-size="100">
          <el-button type="primary" @click="assemble">立即装配</el-button>
        </el-empty>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { assembleContext, type AssembleContextResponse } from '@renderer/api/ai'
import { ElMessage } from 'element-plus'
import { getCardsForProject, type CardRead } from '@renderer/api/cards'
import { Connection, Refresh, EditPen, Memo, CircleCheck, Cpu, ArrowRight, Share } from '@element-plus/icons-vue'
import KGVisualization from '../kg/KGVisualization.vue'

const props = defineProps<{ projectId?: number; participants?: string[]; volumeNumber?: number | null; stageNumber?: number | null; chapterNumber?: number | null; draftTail?: string; prefetched?: AssembleContextResponse | null }>()
const emit = defineEmits<{ (e:'update:participants', v: string[]): void; (e:'update:volumeNumber', v: number | null): void; (e:'update:stageNumber', v: number | null): void; (e:'update:chapterNumber', v: number | null): void }>()

const assembling = ref(false)
const assembled = ref<AssembleContextResponse | null>(null)
const showRaw = ref(false)
const viewMode = ref<'list' | 'graph'>('list')

type Group = { label: string; values: string[] }
const participantGroups = ref<Group[]>([])
const localParticipants = ref<string[]>(props.participants || [])
const localVolumeNumber = ref<number | null>(props.volumeNumber ?? null)
const localChapterNumber = ref<number | null>(props.chapterNumber ?? null)

watch(() => props.participants, (v) => { localParticipants.value = [...(v || [])] })
watch(() => props.volumeNumber, (v) => { localVolumeNumber.value = v ?? null })
watch(() => props.chapterNumber, (v) => { localChapterNumber.value = v ?? null })
watch(() => props.prefetched, (v) => { if (v) assembled.value = v })
watch(() => props.projectId, async () => { await buildAllGroups() })

function getStanceType(stance: string) {
  if (stance.includes('友') || stance.includes('爱')) return 'success'
  if (stance.includes('敌') || stance.includes('恨')) return 'danger'
  if (stance.includes('中')) return 'info'
  return 'warning'
}

function detectTypeGroupByCard(c: CardRead): string {
  const et = (c.content as any)?.entity_type
  if (et === 'character') return '角色'
  if (et === 'scene') return '场景'
  if (et === 'organization') return '组织'
  if (et === 'item') return '物品'
  if (et === 'concept') return '概念'
  if (et === 'character') return '角色'

  const tname = (c.card_type?.name || '').trim()
  if (tname.includes('角色')) return '角色'
  if (tname.includes('场景')) return '场景'
  if (tname.includes('组织')) return '组织'
  if (tname.includes('物品')) return '物品'
  if (tname.includes('概念')) return '概念'

  return '其他'
}

async function buildAllGroups() {
  if (!props.projectId) { participantGroups.value = []; return }
  try {
    const cards: CardRead[] = await getCardsForProject(props.projectId)
    const order = ['角色','场景','组织','物品','概念','其他']
    const buckets = new Map<string, Set<string>>()
    order.forEach(t => buckets.set(t, new Set<string>()))
    for (const c of cards) {
      const t = detectTypeGroupByCard(c)
      const title = (c.title || '').trim()
      if (!title) continue
      buckets.get(t)!.add(title)
    }
    participantGroups.value = order
      .map(label => ({ label, values: Array.from(buckets.get(label) || []).sort((a,b)=>a.localeCompare(b)) }))
      .filter(g => g.values.length > 0)
  } catch {
    participantGroups.value = []
  }
}

function onParticipantsChange() {
  emit('update:participants', [...localParticipants.value])
}

onMounted(async () => { 
  await buildAllGroups()
  if (props.prefetched) assembled.value = props.prefetched 
})

async function assemble() {
  try {
    assembling.value = true
    const res = await assembleContext({
      project_id: props.projectId,
      volume_number: localVolumeNumber.value ?? undefined,
      chapter_number: localChapterNumber.value ?? undefined,
      participants: localParticipants.value,
      current_draft_tail: props.draftTail || ''
    })
    assembled.value = res
    ElMessage.success('上下文装配完成')
  } catch (e:any) {
    ElMessage.error('装配失败')
  } finally {
    assembling.value = false
  }
}
</script>

<style scoped>
.ctx-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--el-bg-color);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--el-fill-color-lighter);
  border-bottom: 1px solid var(--el-border-color-light);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.view-toggle {
  margin-right: 4px;
}

.header-icon {
  color: var(--el-color-primary);
  font-size: 18px;
}

.panel-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}

.controls {
  padding: 12px 16px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.participant-select {
  width: 100%;
}

.panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
}

.panel-content.is-graph {
  padding: 0;
  overflow: hidden;
}

.section {
  margin-bottom: 20px;
  background: var(--el-bg-color-overlay);
  border-radius: 8px;
  border: 1px solid var(--el-border-color-lighter);
  overflow: hidden;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--el-fill-color-light);
  border-bottom: 1px solid var(--el-border-color-lighter);
  cursor: default;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.guide-content {
  padding: 12px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--el-text-color-regular);
  white-space: pre-wrap;
}

.fact-list {
  list-style: none;
  padding: 8px 12px;
  margin: 0;
}

.fact-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 13px;
  line-height: 1.5;
}

.bullet {
  margin-top: 3px;
  color: var(--el-color-success);
  font-size: 14px;
}

.sub-section {
  padding: 8px 0;
}

.sub-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
  padding: 4px 12px;
  margin-top: 8px;
}

.relation-card {
  margin: 8px 12px;
  padding: 10px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
  border: 1px solid var(--el-border-color-lighter);
}

.relation-main {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 6px;
}

.entity-name {
  font-weight: 600;
  font-size: 13px;
}

.relation-kind {
  font-size: 11px;
}

.relation-desc {
  font-size: 12px;
  color: var(--el-text-color-regular);
  margin-bottom: 8px;
}

.addressing-box {
  background: var(--el-bg-color);
  padding: 6px 8px;
  border-radius: 4px;
  font-size: 11px;
  margin-bottom: 8px;
}

.addr-item {
  margin-bottom: 2px;
}

.addr-label {
  color: var(--el-text-color-secondary);
}

.dialogue-section {
  border-top: 1px dashed var(--el-border-color-lighter);
  padding-top: 6px;
}

.mini-label {
  font-size: 11px;
  color: var(--el-text-color-placeholder);
  margin-bottom: 4px;
}

.dialogue-item {
  font-size: 12px;
  font-style: italic;
  color: var(--el-text-color-regular);
  margin-bottom: 4px;
  padding-left: 8px;
  border-left: 2px solid var(--el-border-color-lighter);
}

.raw-section .section-header {
  cursor: pointer;
}

.raw-section .section-header:hover {
  background: var(--el-fill-color);
}

.toggle-icon {
  margin-left: auto;
  transition: transform 0.3s;
}

.toggle-icon.is-active {
  transform: rotate(90deg);
}

.raw-content {
  padding: 12px;
}

.code-block {
  margin: 0;
  padding: 8px;
  background: #1e1e1e;
  color: #d4d4d4;
  border-radius: 4px;
  font-family: monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
}

.empty-state {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: var(--el-border-color-lighter);
  border-radius: 3px;
}

.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: var(--el-border-color);
}
</style>