import { storeToRefs } from 'pinia'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useCardStore } from '@renderer/stores/useCardStore'
import { useProjectStore } from '@renderer/stores/useProjectStore'
import { useAssistantStore } from '@renderer/stores/useAssistantStore'
import { useCardTree } from './useCardTree'
import { copyCard, batchReorderCards } from '@renderer/api/cards'
import { getCardSchema, createCardType } from '@renderer/api/setting'

export function useCardDragDrop(newCardForm: any, handleCreateCard: () => void) {
    const cardStore = useCardStore()
    const projectStore = useProjectStore()
    const assistantStore = useAssistantStore()
    const { cards, activeCard } = storeToRefs(cardStore)
    const { updateProjectStructureContext } = useCardTree()

    // 拖拽：从类型到卡片区域创建新实例
    function onTypeDragStart(t: any) {
        try { (event as DragEvent).dataTransfer?.setData('application/x-card-type-id', String(t.id)) } catch { }
    }

    async function onCardsPaneDrop(e: DragEvent) {
        try {
            const typeId = e.dataTransfer?.getData('application/x-card-type-id')
            if (typeId) {
                newCardForm.title = (cardStore.cardTypes.find(ct => ct.id === Number(typeId))?.name || '新卡片')
                newCardForm.card_type_id = Number(typeId)
                newCardForm.parent_id = '' as any
                handleCreateCard()
                return
            }
            const freeCardId = e.dataTransfer?.getData('application/x-free-card-id')
            if (freeCardId) {
                await copyCard(Number(freeCardId), { target_project_id: projectStore.currentProject!.id, parent_id: null as any })
                await cardStore.fetchCards(projectStore.currentProject!.id)
                ElMessage.success('已复制自由卡片到根目录')
                return
            }
        } catch { }
    }

    async function onTypesPaneDrop(e: DragEvent) {
        try {
            const cardIdStr = e.dataTransfer?.getData('application/x-card-id')
            const cardId = cardIdStr ? Number(cardIdStr) : NaN
            if (!cardId || Number.isNaN(cardId)) return

            const resp = await getCardSchema(cardId)
            const effective = resp?.effective_schema || resp?.json_schema
            if (!effective) { ElMessage.warning('该卡片暂无可用结构，无法生成类型'); return }

            const old = cards.value.find(c => (c as any).id === cardId)
            const defaultName = (old?.title || '新类型') as string
            const { value } = await ElMessageBox.prompt('从该实例创建卡片类型，请输入类型名称：', '创建卡片类型', {
                inputValue: defaultName,
                confirmButtonText: '创建',
                cancelButtonText: '取消',
                inputValidator: (v: string) => v.trim().length > 0 || '名称不能为空'
            })
            const finalName = String(value).trim()
            await createCardType({ name: finalName, description: `${finalName}的默认卡片类型`, json_schema: effective } as any)
            ElMessage.success('已从实例创建卡片类型')
            await cardStore.fetchCardTypes()
        } catch (err) { }
    }

    function handleAllowDrag(draggingNode: any): boolean {
        return !draggingNode.data.__isGroup
    }

    function handleAllowDrop(draggingNode: any, dropNode: any, type: 'prev' | 'inner' | 'next'): boolean {
        if (dropNode.data.__isGroup) {
            return type === 'inner'
        }
        return true
    }

    async function handleNodeDrop(draggingNode: any, dropNode: any, dropType: 'before' | 'after' | 'inner', ev: DragEvent) {
        try {
            const draggedCard = draggingNode.data
            const targetCard = dropNode.data

            if (targetCard.__isGroup && dropType === 'inner') {
                const rootCards = cards.value.filter(c => c.parent_id === null)
                const maxOrder = rootCards.length > 0 ? Math.max(...rootCards.map(c => c.display_order || 0)) : -1

                await cardStore.modifyCard(draggedCard.id, { parent_id: null, display_order: maxOrder + 1 }, { skipHooks: true })
                ElMessage.success(`已将「${draggedCard.title}」移到根级`)
                await cardStore.fetchCards(projectStore.currentProject!.id)

                assistantStore.recordOperation(projectStore.currentProject!.id, {
                    type: 'move',
                    cardId: draggedCard.id,
                    cardTitle: draggedCard.title,
                    cardType: draggedCard.card_type?.name || 'Unknown',
                    detail: '从子卡片移到根级'
                })

                updateProjectStructureContext(activeCard.value?.id)
                return
            }

            if (dropType === 'inner') {
                const children = cards.value.filter(c => c.parent_id === targetCard.id)
                const maxOrder = children.length > 0 ? Math.max(...children.map(c => c.display_order || 0)) : -1

                await cardStore.modifyCard(draggedCard.id, { parent_id: targetCard.id, display_order: maxOrder + 1 }, { skipHooks: true })
                ElMessage.success(`已将「${draggedCard.title}」设为「${targetCard.title}」的子卡片`)
                await cardStore.fetchCards(projectStore.currentProject!.id)

                assistantStore.recordOperation(projectStore.currentProject!.id, {
                    type: 'move',
                    cardId: draggedCard.id,
                    cardTitle: draggedCard.title,
                    cardType: draggedCard.card_type?.name || 'Unknown',
                    detail: `设为「${targetCard.title}」(${targetCard.card_type?.name || 'Unknown'} #${targetCard.id})的子卡片`
                })

                updateProjectStructureContext(activeCard.value?.id)
                return
            }

            const newParentId = targetCard.parent_id || null
            const siblings = cards.value
                .filter(c => (c.parent_id || null) === newParentId && c.id !== draggedCard.id)
                .sort((a, b) => (a.display_order || 0) - (b.display_order || 0))

            const targetIndex = siblings.findIndex(c => c.id === targetCard.id)
            let newSiblings = [...siblings]
            if (dropType === 'before') {
                newSiblings.splice(targetIndex, 0, draggedCard)
            } else {
                newSiblings.splice(targetIndex + 1, 0, draggedCard)
            }

            const updates: any[] = []
            newSiblings.forEach((card, index) => {
                if (card.id === draggedCard.id) {
                    updates.push({ card_id: card.id, display_order: index, parent_id: newParentId })
                } else if (card.display_order !== index) {
                    updates.push({ card_id: card.id, display_order: index, parent_id: card.parent_id || null })
                }
            })

            if (updates.length > 0) {
                await batchReorderCards({ updates })
            }

            ElMessage.success(`已调整「${draggedCard.title}」的位置`)
            await cardStore.fetchCards(projectStore.currentProject!.id)

            updateProjectStructureContext(activeCard.value?.id)
        } catch (err: any) {
            ElMessage.error(err?.message || '拖拽失败')
            await cardStore.fetchCards(projectStore.currentProject!.id)
            updateProjectStructureContext(activeCard.value?.id)
        }
    }

    async function onExternalDropToNode(e: DragEvent, nodeData: any) {
        const raw = e.dataTransfer?.getData('application/x-card-type-id') || ''
        const typeId = Number(raw)
        if (Number.isFinite(typeId) && typeId > 0) {
            if (nodeData?.__isGroup) return
            const newCard = await cardStore.addCard({ title: '新建卡片', card_type_id: typeId, parent_id: nodeData?.id } as any)
            if (newCard && projectStore.currentProject?.id) {
                const cardType = cardStore.cardTypes.find(ct => ct.id === typeId)
                assistantStore.recordOperation(projectStore.currentProject.id, {
                    type: 'create',
                    cardId: (newCard as any).id,
                    cardTitle: newCard.title,
                    cardType: cardType?.name || 'Unknown'
                })
            }
            return
        }

        try {
            const freeCardId = e.dataTransfer?.getData('application/x-free-card-id')
            if (freeCardId) {
                if (nodeData?.__isGroup) return
                await copyCard(Number(freeCardId), { target_project_id: projectStore.currentProject!.id, parent_id: Number(nodeData?.id) })
                await cardStore.fetchCards(projectStore.currentProject!.id)
                ElMessage.success('已复制自由卡片到该节点下')
            }
        } catch (err) { }
    }

    return {
        onTypeDragStart,
        onCardsPaneDrop,
        onTypesPaneDrop,
        handleAllowDrag,
        handleAllowDrop,
        handleNodeDrop,
        onExternalDropToNode
    }
}
