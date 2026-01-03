import { ElMessage } from 'element-plus'
import { useProjectStore } from '../stores/useProjectStore'
import { useCardStore } from '../stores/useCardStore'

export function useCardPackage() {
    const projectStore = useProjectStore()
    const cardStore = useCardStore()

    async function handleExportPackage(data: any) {
        if (!data?.id) return
        try {
            const { exportCardPackage } = await import('@renderer/api/package')
            const res = await exportCardPackage(data.id)
            const blob = new Blob([JSON.stringify(res, null, 2)], { type: 'application/json' })
            const url = URL.createObjectURL(blob)
            const link = document.createElement('a')
            link.href = url
            link.download = `${data.title || 'package'}.nfpkg.json`
            document.body.appendChild(link)
            link.click()
            document.body.removeChild(link)
            URL.revokeObjectURL(url)
            ElMessage.success('导出成功')
        } catch (err: any) {
            ElMessage.error(`导出失败: ${err.message}`)
        }
    }

    async function handleImportPackage() {
        const input = document.createElement('input')
        input.type = 'file'
        input.accept = '.json'
        input.onchange = async (e: any) => {
            const file = e.target.files[0]
            if (!file) return

            const reader = new FileReader()
            reader.onload = async (ev) => {
                try {
                    const json = JSON.parse(ev.target?.result as string)
                    const { importCardPackage } = await import('@renderer/api/package')
                    const projectId = projectStore.currentProject?.id
                    if (!projectId) return

                    await importCardPackage(projectId, {
                        package_data: json,
                        target_parent_id: null
                    })
                    ElMessage.success('导入成功')
                    cardStore.fetchCards(projectId)
                } catch (err: any) {
                    ElMessage.error(`导入失败: ${err.message}`)
                }
            }
            reader.readAsText(file)
        }
        input.click()
    }

    return {
        handleExportPackage,
        handleImportPackage
    }
}
