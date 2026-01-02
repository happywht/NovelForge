<template>
  <!-- 动态信息预览对话框 -->
  <el-dialog
    v-model="internalPreviewVisible"
    title="动态信息预览"
    width="70%"
    @close="$emit('update:previewVisible', false)"
  >
    <div v-if="previewData">
      <div v-for="role in previewData.info_list" :key="role.name" class="role-block">
        <h4>{{ role.name }}</h4>
        <div v-for="(items, catKey) in role.dynamic_info" :key="String(catKey)" class="cat-block">
          <div class="cat-title">{{ formatCategory(catKey) }}</div>
          <el-table :data="items as any[]" size="small" border>
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="info" label="信息" min-width="360" />
            <el-table-column label="操作" width="90">
              <template #default="scope">
                <el-button
                  type="danger"
                  text
                  size="small"
                  @click="$emit('remove-item', role.name, String(catKey), scope.$index)"
                >
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </div>
    <template #footer>
      <el-button @click="internalPreviewVisible = false">取消</el-button>
      <el-button type="primary" @click="$emit('confirm-dynamic')">确定更新</el-button>
    </template>
  </el-dialog>

  <!-- 关系入图预览对话框 -->
  <el-dialog
    v-model="internalRelationsVisible"
    title="关系入图预览"
    width="70%"
    @close="$emit('update:relationsVisible', false)"
  >
    <div v-if="relationsPreview">
      <div v-if="relationsPreview.relations?.length" style="margin-top: 16px">
        <h4>关系项</h4>
        <el-table :data="relationsPreview.relations" size="small" border>
          <el-table-column prop="a" label="A" width="160" />
          <el-table-column prop="kind" label="关系" width="120" />
          <el-table-column prop="b" label="B" width="160" />
          <el-table-column label="证据">
            <template #default="{ row }">
              <div v-if="row.a_to_b_addressing || row.b_to_a_addressing">
                <div v-if="row.a_to_b_addressing">A称呼B: {{ row.a_to_b_addressing }}</div>
                <div v-if="row.b_to_a_addressing">B称呼A: {{ row.b_to_a_addressing }}</div>
              </div>
              <div v-if="row.recent_dialogues?.length">
                <div>对话样例：</div>
                <ul style="margin: 4px 0 0 16px; padding: 0">
                  <li v-for="(d, i) in row.recent_dialogues" :key="i" style="list-style: disc">
                    {{ d }}
                  </li>
                </ul>
              </div>
              <div v-if="row.recent_event_summaries?.length">
                <div>
                  近期事件：{{
                    row.recent_event_summaries[row.recent_event_summaries.length - 1].summary
                  }}
                  <span
                    v-if="
                      row.recent_event_summaries[row.recent_event_summaries.length - 1]
                        .volume_number != null ||
                      row.recent_event_summaries[row.recent_event_summaries.length - 1]
                        .chapter_number != null
                    "
                    class="event-meta"
                  >
                    （卷{{
                      row.recent_event_summaries[row.recent_event_summaries.length - 1]
                        .volume_number ?? '-'
                    }}·章{{
                      row.recent_event_summaries[row.recent_event_summaries.length - 1]
                        .chapter_number ?? '-'
                    }}）
                  </span>
                </div>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>
    <template #footer>
      <el-button @click="internalRelationsVisible = false">取消</el-button>
      <el-button type="primary" @click="$emit('confirm-relations')">确认入图</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  previewVisible: boolean
  previewData: any
  relationsVisible: boolean
  relationsPreview: any
}>()

const emit = defineEmits<{
  (e: 'update:previewVisible', val: boolean): void
  (e: 'update:relationsVisible', val: boolean): void
  (e: 'confirm-dynamic'): void
  (e: 'confirm-relations'): void
  (e: 'remove-item', roleName: string, catKey: string, index: number): void
}>()

const internalPreviewVisible = ref(props.previewVisible)
const internalRelationsVisible = ref(props.relationsVisible)

watch(
  () => props.previewVisible,
  (val) => {
    internalPreviewVisible.value = val
  }
)

watch(
  () => internalPreviewVisible.value,
  (val) => {
    emit('update:previewVisible', val)
  }
)

watch(
  () => props.relationsVisible,
  (val) => {
    internalRelationsVisible.value = val
  }
)

watch(
  () => internalRelationsVisible.value,
  (val) => {
    emit('update:relationsVisible', val)
  }
)

function formatCategory(catKey: any) {
  return String(catKey)
}
</script>

<style scoped>
.role-block {
  margin-bottom: 24px;
  padding: 16px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}

.cat-block {
  margin-top: 12px;
}

.cat-title {
  font-weight: bold;
  margin-bottom: 8px;
  color: var(--el-text-color-primary);
}

.event-meta {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
