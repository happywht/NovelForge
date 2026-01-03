import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { listWorkflows, runWorkflow as apiRunWorkflow } from '@renderer/api/workflows'
import { BASE_URL } from '@renderer/api/request'
import { useCardStore } from '../stores/useCardStore'
import { useProjectStore } from '../stores/useProjectStore'

export function useWorkflowRunner() {
    const cardStore = useCardStore()
    const projectStore = useProjectStore()
    const isRunning = ref(false)
    const currentWorkflowName = ref('')

    async function runWorkflowByName(workflowName: string, scope: any, params: any = {}) {
        isRunning.value = true
        currentWorkflowName.value = workflowName

        const loading = ElMessage({
            message: `正在启动 AI 协作：${workflowName}...`,
            type: 'info',
            duration: 0
        })

        try {
            const workflows = await listWorkflows()
            const target = workflows.find((w) => w.name === workflowName)
            if (!target) {
                loading.close()
                ElMessage.error(`未找到工作流: ${workflowName}`)
                return
            }

            const axiosResp: any = await apiRunWorkflow(target.id, {
                scope_json: scope,
                params_json: params
            })

            loading.close()
            ElMessage.success(`${workflowName} 已启动`)

            // 处理 SSE 事件订阅（逻辑从 store 迁移过来或保持同步）
            const runId = axiosResp.data?.id
            if (runId) {
                subscribeToWorkflow(runId)
            }

            return axiosResp.data
        } catch (err: any) {
            loading.close()
            ElMessage.error(`启动失败: ${err.message}`)
            throw err
        } finally {
            isRunning.value = false
        }
    }

    function subscribeToWorkflow(runId: number) {
        const es = new EventSource(`${BASE_URL}/api/workflows/runs/${runId}/events`)

        es.addEventListener('run_completed', async (evt: MessageEvent) => {
            const data = JSON.parse(evt.data || '{}')
            console.log(`[WorkflowRunner] Run completed: ${runId}`, data)

            // 触发受影响卡片的精准刷新
            if (data.affected_card_ids && Array.isArray(data.affected_card_ids)) {
                for (const cid of data.affected_card_ids) {
                    await refreshCardLocally(cid)
                }
            } else {
                // 回退到全量刷新
                if (projectStore.currentProject?.id) {
                    await cardStore.fetchCards(projectStore.currentProject.id)
                }
            }
            es.close()
        })

        es.onerror = () => {
            console.warn(`[WorkflowRunner] SSE error for run ${runId}, falling back to polling if needed`)
            es.close()
            // 这里可以添加轮询兜底逻辑
        }
    }

    async function refreshCardLocally(cardId: number) {
        try {
            const resp = await fetch(`${BASE_URL}/api/cards/${cardId}`)
            if (resp.ok) {
                const updated = await resp.json()
                const index = cardStore.cards.findIndex((c) => c.id === cardId)
                if (index >= 0) {
                    cardStore.cards[index] = {
                        ...cardStore.cards[index],
                        ...updated,
                        content: updated.content ?? cardStore.cards[index].content
                    }
                }
            }
        } catch (e) {
            console.error(`[WorkflowRunner] Failed to refresh card ${cardId}`, e)
        }
    }

    return {
        isRunning,
        currentWorkflowName,
        runWorkflowByName
    }
}
