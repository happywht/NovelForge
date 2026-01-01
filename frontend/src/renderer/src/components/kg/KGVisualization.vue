<template>
  <div class="kg-wrapper">
    <div class="kg-container" ref="containerRef"></div>
    <div class="kg-toolbar">
      <el-button-group>
        <el-button size="small" @click="handleZoomIn"><el-icon><ZoomIn /></el-icon></el-button>
        <el-button size="small" @click="handleZoomOut"><el-icon><ZoomOut /></el-icon></el-button>
        <el-button size="small" @click="handleAutoFit"><el-icon><FullScreen /></el-icon></el-button>
        <el-button size="small" @click="fetchData"><el-icon><Refresh /></el-icon></el-button>
      </el-button-group>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { Graph } from '@antv/g6'
import { getProjectGraph } from '@renderer/api/kg'
import { ZoomIn, ZoomOut, FullScreen, Refresh } from '@element-plus/icons-vue'

const props = defineProps<{
  projectId: number | null
}>()

const containerRef = ref<HTMLElement | null>(null)
let graph: any = null

const initGraph = () => {
  console.log('Initializing G6 graph, container:', containerRef.value)
  if (!containerRef.value) return

  graph = new Graph({
    container: containerRef.value,
    width: containerRef.value.clientWidth || 800,
    height: containerRef.value.clientHeight || 600,
    autoFit: 'view',
    behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element'],
    layout: {
      type: 'force',
      preventOverlap: true,
      linkDistance: 150,
      nodeStrength: -50,
      edgeStrength: 0.1,
    },
    node: {
      style: {
        size: 40,
        fill: '#C6E5FF',
        stroke: '#5B8FF9',
        lineWidth: 2,
        label: true,
        labelText: (d: any) => d.label || d.id,
        labelPlacement: 'bottom',
        labelFontSize: 12,
      },
    },
    edge: {
      style: {
        stroke: '#e2e2e2',
        lineWidth: 1,
        endArrow: true,
        label: true,
        labelText: (d: any) => d.label || '',
        labelFontSize: 10,
      },
    },
  })

  graph.on('node:dblclick', (evt: any) => {
    const { target } = evt;
    console.log('Double clicked node:', target.id)
    // TODO: Emit event to jump to card if name matches
  })
}

const fetchData = async () => {
  console.log('fetchData called, projectId:', props.projectId, 'graph initialized:', !!graph)
  if (!props.projectId || !graph) return
  try {
    const data = await getProjectGraph(props.projectId)
    console.log('Fetched KG data:', data)
    if (data && data.nodes && data.nodes.length > 0) {
      graph.setData(data)
      graph.render()
      console.log('Graph rendered')
    } else {
      console.warn('KG data is empty or invalid:', data)
    }
  } catch (e) {
    console.error('Failed to fetch KG data:', e)
  }
}

const handleZoomIn = () => graph?.zoom(1.2)
const handleZoomOut = () => graph?.zoom(0.8)
const handleAutoFit = () => graph?.fitView()

onMounted(() => {
  setTimeout(() => {
    initGraph()
    fetchData()
  }, 100)
  
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  if (graph) {
    graph.destroy()
  }
  window.removeEventListener('resize', handleResize)
})

const handleResize = () => {
  if (graph && containerRef.value) {
    graph.changeSize(containerRef.value.scrollWidth, containerRef.value.scrollHeight || 600)
  }
}

watch(() => props.projectId, () => {
  fetchData()
})
</script>

<style scoped>
.kg-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 500px;
  background: var(--el-bg-color-page);
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--el-border-color-lighter);
}

.kg-container {
  width: 100%;
  height: 100%;
}

.kg-toolbar {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 10;
  background: var(--el-bg-color-overlay);
  padding: 4px;
  border-radius: 4px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}
</style>
