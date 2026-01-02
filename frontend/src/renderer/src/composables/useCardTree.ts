import { computed, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useCardStore } from '@renderer/stores/useCardStore'
import { useEditorStore } from '@renderer/stores/useEditorStore'
import { useProjectStore } from '@renderer/stores/useProjectStore'
import { useAssistantStore } from '@renderer/stores/useAssistantStore'

export interface TreeNode {
  id: number | string
  title: string
  children?: TreeNode[]
  card_type?: { name: string }
  __isGroup?: boolean
  __groupType?: string
}

export function useCardTree() {
  const cardStore = useCardStore()
  const editorStore = useEditorStore()
  const projectStore = useProjectStore()
  const assistantStore = useAssistantStore()
  const { cardTree, cards, activeCard } = storeToRefs(cardStore)
  const { expandedKeys } = storeToRefs(editorStore)

  function buildGroupedNodes(nodes: any[]): any[] {
    return nodes.map((n) => {
      const node: TreeNode = { ...n }
      // 分组节点自身不再参与分组逻辑，直接递归其子节点
      if ((n as any).__isGroup) {
        if (Array.isArray(n.children) && n.children.length > 0) {
          node.children = buildGroupedNodes(n.children as any)
        }
        return node
      }
      if (Array.isArray(n.children) && n.children.length > 0) {
        // 统计子节点类型数量
        const byType: Record<string, any[]> = {}
        n.children.forEach((c: any) => {
          const typeName = c.card_type?.name || '未知类型'
          if (!byType[typeName]) byType[typeName] = []
          byType[typeName].push(c)
        })
        const types = Object.keys(byType)

        // 决定哪些类型需要分组
        const finalChildren: any[] = []
        types.forEach((t) => {
          const list = byType[t]
          if (list.length > 2) {
            // 创建虚拟分组节点
            finalChildren.push({
              id: `group:${n.id}:${t}`,
              title: `${t} (${list.length})`,
              __isGroup: true,
              __groupType: t,
              children: buildGroupedNodes(list)
            })
          } else {
            // 保持原样
            finalChildren.push(...buildGroupedNodes(list))
          }
        })
        node.children = finalChildren
      }
      return node
    })
  }

  const groupedTree = computed(() => buildGroupedNodes(cardTree.value))

  function updateProjectStructureContext(currentCardId?: number) {
    const project = projectStore.currentProject
    if (!project?.id) return

    assistantStore.updateProjectStructure(
      project.id,
      project.name,
      cards.value,
      cardStore.cardTypes,
      currentCardId
    )
  }

  function onNodeExpand(data: any) {
    editorStore.addExpandedKey(String(data.id))
  }

  function onNodeCollapse(data: any) {
    editorStore.removeExpandedKey(String(data.id))
  }

  return {
    groupedTree,
    expandedKeys,
    onNodeExpand,
    onNodeCollapse,
    buildGroupedNodes,
    updateProjectStructureContext
  }
}
