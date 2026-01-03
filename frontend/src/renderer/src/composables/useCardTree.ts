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
    if (!nodes || nodes.length === 0) return [];

    const result: any[] = [];
    for (const n of nodes) {
      const node: TreeNode = { ...n };

      if ((n as any).__isGroup) {
        if (Array.isArray(n.children) && n.children.length > 0) {
          node.children = buildGroupedNodes(n.children);
        }
        result.push(node);
        continue;
      }

      if (Array.isArray(n.children) && n.children.length > 0) {
        const byType = new Map<string, any[]>();
        for (const c of n.children) {
          const typeName = c.card_type?.name || '未知类型';
          let list = byType.get(typeName);
          if (!list) {
            list = [];
            byType.set(typeName, list);
          }
          list.push(c);
        }

        const finalChildren: any[] = [];
        for (const [t, list] of byType.entries()) {
          if (list.length > 3) { // 稍微提高分组阈值以减少节点数
            finalChildren.push({
              id: `group:${n.id}:${t}`,
              title: `${t} (${list.length})`,
              __isGroup: true,
              __groupType: t,
              children: buildGroupedNodes(list)
            });
          } else {
            // 直接展开，但仍需递归处理其子节点
            for (const item of list) {
              const processed = { ...item };
              if (item.children && item.children.length > 0) {
                processed.children = buildGroupedNodes(item.children);
              }
              finalChildren.push(processed);
            }
          }
        }
        node.children = finalChildren;
      }
      result.push(node);
    }
    return result;
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
