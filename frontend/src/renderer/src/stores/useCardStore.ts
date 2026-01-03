import { defineStore, storeToRefs } from 'pinia'
import { ref, computed, watch } from 'vue'
import {
  getCardTypes,
  getCardsForProject,
  createCard,
  updateCard,
  deleteCard,
  getContentModels,
  type CardRead,
  type CardTypeRead,
  type CardCreate,
  type CardUpdate
} from '@renderer/api/cards'
import { useProjectStore } from './useProjectStore'
import { ElMessage } from 'element-plus'
import { BASE_URL } from '@renderer/api/request'

// 为了避免直接在 CardRead 上添加 children 属性，这里定义本地扩展类型
export interface CardContent {
  title?: string
  content?: string
  chapter_number?: number
  volume_number?: number
  entity_list?: string[]
  [key: string]: any
}

type CardNode = Omit<CardRead, 'content'> & {
  content: CardContent
  children: CardNode[]
}
const buildCardTree = (cards: CardRead[]): CardNode[] => {
  if (!cards || cards.length === 0) return [];

  const nodeMap = new Map<number, CardNode>();
  const tree: CardNode[] = [];

  // First pass: Create all nodes and map them
  for (const card of cards) {
    nodeMap.set(card.id, { ...card, children: [] });
  }

  // Second pass: Build the tree structure
  for (const card of cards) {
    const node = nodeMap.get(card.id)!;
    if (card.parent_id && nodeMap.has(card.parent_id)) {
      nodeMap.get(card.parent_id)!.children.push(node);
    } else {
      tree.push(node);
    }
  }

  // Third pass: Sort nodes recursively
  const sortNodes = (nodes: CardNode[]) => {
    if (nodes.length > 1) {
      nodes.sort((a, b) => (a.display_order || 0) - (b.display_order || 0));
    }
    for (const n of nodes) {
      if (n.children.length > 0) {
        sortNodes(n.children);
      }
    }
  };

  sortNodes(tree);
  return tree;
};

export const useCardStore = defineStore('card', () => {
  const projectStore = useProjectStore()
  const { currentProject } = storeToRefs(projectStore)

  // --- State ---
  const cards = ref<CardRead[]>([])
  const cardTypes = ref<CardTypeRead[]>([])
  const availableModels = ref<string[]>([])
  const activeCardId = ref<number | null>(null)
  const isLoading = ref(false)

  // --- Getters ---
  const cardTree = computed(() => buildCardTree(cards.value) as unknown as CardRead[])
  const activeCard = computed(() => {
    if (activeCardId.value === null) return null
    return cards.value.find((c) => c.id === activeCardId.value) || null
  })

  // --- Watchers ---
  watch(
    currentProject,
    (newProject) => {
      if (newProject?.id) {
        fetchCards(newProject.id)
      } else {
        // If there's no project, clear the cards
        cards.value = []
      }
    },
    { immediate: true }
  )

  // --- 内部工具：根据卡片类型名称拿到ID ---
  function getCardTypeIdByName(name: string): number | null {
    const ct = cardTypes.value.find((t) => t.name === name)
    return ct ? ct.id : null
  }

  // --- 内部工具：正则解析“第N卷”的标题 ---
  function parseVolumeIndexFromTitle(title: string): number | null {
    const m = title.match(/^第(\d+)卷$/)
    if (!m) return null
    return parseInt(m[1], 10)
  }

  // --- Actions ---

  async function fetchInitialData() {
    await Promise.all([fetchCardTypes(), fetchAvailableModels()])
  }

  // Card Actions
  async function fetchCards(projectId: number) {
    if (!projectId) {
      cards.value = []
      return
    }
    isLoading.value = true
    try {
      const fetchedCards = await getCardsForProject(projectId)
      console.log(
        `[CardStore] Fetched ${fetchedCards.length} cards for project ${projectId}:`,
        fetchedCards
      )
      cards.value = fetchedCards
    } catch (error) {
      ElMessage.error('Failed to fetch cards.')
      console.error(error)
    } finally {
      isLoading.value = false
    }
  }

  // 新增：addCard 支持 options.silent，静默模式下不全量刷新、不弹 Toast，直接本地插入并返回新卡
  async function addCard(cardData: CardCreate, options?: { silent?: boolean }) {
    if (!currentProject.value?.id) return
    try {
      const newCard = await createCard(currentProject.value.id, cardData)

      // 增量更新本地状态
      cards.value = [...cards.value, newCard as unknown as CardRead]

      if (!options?.silent) {
        ElMessage.success(`Card "${newCard.title}" created.`)
      }
      return newCard
    } catch (error) {
      if (!options?.silent) ElMessage.error('Failed to create card.')
      console.error(error)
      return
    }
  }

  // 增加可选参数：skipHooks 用于内部更新时跳过“保存后钩子”
  async function modifyCard(
    cardId: number,
    cardData: { content: Record<string, any> | null } | CardUpdate,
    options?: { skipHooks?: boolean }
  ) {
    try {
      console.log('[CardStore] 准备更新卡片:', cardId, cardData)
      // 使用原始响应以读取头部 X-Workflows-Started
      const axiosResp: any = await (
        await import('@renderer/api/cards')
      ).updateCardRaw(cardId, cardData as CardUpdate)
      const updatedCard: CardRead = axiosResp.data
      console.log('[CardStore] 更新卡片成功，检查工作流回执响应头:', axiosResp.headers)

      // 本地同步更新：如果是结构性变更，则全量刷新以保证树的正确性
      if ('parent_id' in cardData || 'display_order' in cardData) {
        if (currentProject.value?.id) await fetchCards(currentProject.value.id)
      } else {
        // 否则仅更新本地对象
        const index = cards.value.findIndex((c) => c.id === cardId)
        if (index !== -1) {
          const existingCard = cards.value[index]
          // 合并更新后的数据，确保 content 也被正确更新
          cards.value[index] = {
            ...existingCard,
            ...updatedCard,
            content: updatedCard.content ?? existingCard.content
          }
        }
      }
      ElMessage.success(`Card "${updatedCard.title}" updated.`)
    } catch (error) {
      ElMessage.error('Failed to update card.')
      console.error(error)
    }
  }

  async function removeCard(cardId: number) {
    try {
      await deleteCard(cardId)
      // 后端已做递归删除，这里仅刷新
      if (currentProject.value?.id) await fetchCards(currentProject.value.id)
      ElMessage.success('Card deleted successfully.')
    } catch (error) {
      ElMessage.error('Failed to delete card.')
      console.error(error)
    }
  }

  // CardType Actions
  async function fetchCardTypes() {
    try {
      cardTypes.value = await getCardTypes()
    } catch (error) {
      ElMessage.error('Failed to fetch card types.')
      console.error(error)
    }
  }

  // Available Models Actions
  async function fetchAvailableModels() {
    try {
      availableModels.value = await getContentModels()
    } catch (error) {
      ElMessage.error('Failed to fetch available content models.')
      console.error(error)
    }
  }

  // Utility
  function setActiveCard(cardId: number | null) {
    activeCardId.value = cardId
  }

  function updateCardContentLocally(cardId: number, content: any) {
    const index = cards.value.findIndex((c) => c.id === cardId)
    if (index !== -1) {
      cards.value[index] = { ...cards.value[index], content }
    }
  }

  return {
    // State
    cards,
    cardTypes,
    availableModels,
    activeCardId,
    isLoading,
    // Getters
    cardTree,
    activeCard,
    // Actions
    fetchInitialData,
    fetchCards,
    addCard,
    modifyCard,
    removeCard,
    fetchCardTypes,
    fetchAvailableModels,
    setActiveCard,
    updateCardContentLocally
  }
})
