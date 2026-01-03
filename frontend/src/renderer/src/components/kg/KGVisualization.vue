<template>
  <div ref="wrapperRef" class="kg-wrapper" :class="{ 'is-fullscreen': isFullscreen }">
    <div ref="containerRef" class="kg-container"></div>
    
    <!-- 图例 -->
    <div class="kg-legend">
      <div v-for="(color, type) in typeColors" :key="type" class="legend-item">
        <span class="legend-dot" :style="{ backgroundColor: color }"></span>
        <span class="legend-label">{{ type }}</span>
      </div>
    </div>

    <div class="kg-toolbar">
      <el-button-group>
        <el-button size="small" title="放大" @click="handleZoomIn">
          <el-icon><ZoomIn /></el-icon>
        </el-button>
        <el-button size="small" title="缩小" @click="handleZoomOut">
          <el-icon><ZoomOut /></el-icon>
        </el-button>
        <el-button size="small" title="自适应" @click="handleAutoFit">
          <el-icon><Aim /></el-icon>
        </el-button>
        <el-button size="small" :title="isFullscreen ? '退出全屏' : '全屏'" @click="toggleFullscreen">
          <el-icon><FullScreen v-if="!isFullscreen" /><Close v-else /></el-icon>
        </el-button>
        <el-button size="small" title="刷新" @click="fetchData">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </el-button-group>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { Graph } from '@antv/g6'
import { getProjectGraph } from '@renderer/api/kg'
import { ZoomIn, ZoomOut, FullScreen, Refresh, Aim, Close } from '@element-plus/icons-vue'

const props = defineProps<{
  projectId: number | null
  povCharacter?: string
}>()

const loading = ref(false)

const wrapperRef = ref<HTMLElement | null>(null)
const containerRef = ref<HTMLElement | null>(null)
const isFullscreen = ref(false)
let graph: any = null

const typeColors: Record<string, string> = {
  '角色': '#67C23A', // Success Green
  '场景': '#E6A23C', // Warning Orange
  '组织': '#409EFF', // Primary Blue
  '物品': '#F56C6C', // Danger Red
  '概念': '#909399', // Info Grey
  '其他': '#DCDFE6'
}

const initGraph = () => {
  if (!containerRef.value) return

  const width = containerRef.value.clientWidth || 800
  const height = containerRef.value.clientHeight || 600

  graph = new Graph({
    container: containerRef.value,
    width,
    height,
    autoFit: 'view', // 初始适配
    behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element', 'click-select'],
    layout: {
      type: 'circular',
      radius: 180,
      ordering: 'topology',
    },
    node: {
      type: 'circle',
      style: {
        size: 40,
        fill: '#C6E5FF',
        stroke: '#5B8FF9',
        lineWidth: 2,
        label: true,
        labelPlacement: 'bottom',
        labelFontSize: 12,
        labelFill: '#2C3E50',
        labelFontWeight: 'bold',
        labelBackground: true,
        labelBackgroundFill: 'rgba(255, 255, 255, 0.85)',
        labelBackgroundRadius: 4,
        labelPadding: [2, 4],
      }
    },
    edge: {
      type: 'line',
      style: {
        stroke: '#BDC3C7',
        lineWidth: 1.5,
        endArrow: true,
        label: true,
        labelFontSize: 10,
        labelFill: '#7F8C8D',
        labelBackground: true,
        labelBackgroundFill: 'rgba(255, 255, 255, 0.9)',
        labelBackgroundRadius: 2,
        labelPadding: [1, 3]
      }
    }
  })

  graph.setZoomRange([0.05, 1.5]) // 限制最大缩放，防止文字巨大
}

const fetchData = async () => {
  if (!props.projectId || !graph) return
  loading.value = true
  try {
    // 这里的 API 以后可以扩展支持 pov_character
    const res = await getProjectGraph(props.projectId, props.povCharacter)
    const data = res
    if (data && data.nodes && data.nodes.length > 0) {
      handleResize()
      
      const processedData = {
        nodes: data.nodes.map((n: any) => {
          let type = n.type || '其他'
          const label = n.label || n.id || ''
          
          if (type === '其他') {
            if (label.includes('宗') || label.includes('公司') || label.includes('局')) type = '组织'
            else if (label.includes('服务器') || label.includes('秘境') || label.includes('界')) type = '场景'
            else if (label.length <= 4) type = '角色'
          }

          return {
            id: String(n.id),
            type: 'circle',
            style: {
              size: type === '角色' ? 45 : 35,
              fill: typeColors[type] || typeColors['其他'],
              stroke: '#ffffff',
              lineWidth: 2,
              labelText: label,
            }
          }
        }),
        edges: (data.edges || []).map((e: any) => ({
          source: String(e.source),
          target: String(e.target),
          type: 'line',
          style: {
            labelText: e.label || '',
          }
        }))
      }
      
      graph.setData(processedData)
      graph.render()
      
      // 适配视图，并严格限制缩放
      setTimeout(() => {
        if (!graph) return
        graph.fitView({ padding: 80 })
        // 强制检查缩放，如果过大则缩小
        if (graph.getZoom() > 0.8) {
          graph.zoomTo(0.8)
        }
      }, 500)
    }
  } catch (e) {
    console.error('Failed to fetch KG data:', e)
  }
}

const handleZoomIn = () => {
  if (!graph) return
  graph.zoom(1.2)
}

const handleZoomOut = () => {
  if (!graph) return
  graph.zoom(0.8)
}

const handleAutoFit = () => {
  if (!graph) return
  graph.fitView({ padding: 80 })
  if (graph.getZoom() > 0.8) {
    graph.zoomTo(0.8)
  }
}

const toggleFullscreen = () => {
  isFullscreen.value = !isFullscreen.value
  setTimeout(() => {
    handleResize()
    handleAutoFit()
  }, 300)
}

const handleResize = () => {
  if (graph && containerRef.value) {
    const width = containerRef.value.clientWidth
    const height = containerRef.value.clientHeight
    if (width > 0 && height > 0) {
      graph.setSize(width, height)
    }
  }
}

onMounted(() => {
  nextTick(() => {
    initGraph()
    fetchData()
  })

  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  if (graph) {
    graph.destroy()
  }
  window.removeEventListener('resize', handleResize)
})

watch(
  () => props.projectId,
  () => {
    fetchData()
  }
)

watch(
  () => props.povCharacter,
  () => {
    fetchData()
  }
)
</script>

<style scoped>
.kg-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 500px;
  background: #ffffff;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid var(--el-border-color-lighter);
}

.kg-wrapper.is-fullscreen {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  z-index: 3000;
  border-radius: 0;
  background: #ffffff;
}

.kg-container {
  width: 100%;
  height: 100%;
}

.kg-toolbar {
  position: absolute;
  top: 20px;
  right: 20px;
  z-index: 10;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(8px);
  padding: 4px;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  border: 1px solid var(--el-border-color-lighter);
}

.kg-legend {
  position: absolute;
  bottom: 20px;
  left: 20px;
  z-index: 10;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(8px);
  padding: 12px 16px;
  border-radius: 10px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  border: 1px solid var(--el-border-color-lighter);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 10px;
}

.legend-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.legend-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
</style>
