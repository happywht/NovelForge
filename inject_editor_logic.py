import os

file_path = r'd:\家庭\副业探索\小说项目\NovelForge\frontend\src\renderer\src\views\Editor.vue'

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 1. Inject event listeners in onMounted
on_mounted_start = -1
for i, line in enumerate(lines):
    if 'onMounted(async () => {' in line:
        on_mounted_start = i
        break

if on_mounted_start != -1:
    # Find the end of onMounted
    on_mounted_end = -1
    for i in range(on_mounted_start, len(lines)):
        if '})' in lines[i] and (i == len(lines)-1 or 'onBeforeUnmount' in lines[i+1] or 'function' in lines[i+1]):
            on_mounted_end = i
            break
    
    if on_mounted_end != -1:
        lines.insert(on_mounted_end, "  window.addEventListener('nf:run-workflow', handleRunWorkflow as any)\n")

# 2. Inject cleanup in onBeforeUnmount
on_before_unmount_start = -1
for i, line in enumerate(lines):
    if 'onBeforeUnmount(() => {' in line:
        on_before_unmount_start = i
        break

if on_before_unmount_start != -1:
    # Find the end of onBeforeUnmount
    on_before_unmount_end = -1
    for i in range(on_before_unmount_start, len(lines)):
        if '})' in lines[i]:
            on_before_unmount_end = i
            break
    
    if on_before_unmount_end != -1:
        lines.insert(on_before_unmount_end, "    window.removeEventListener('nf:run-workflow', handleRunWorkflow as any)\n")

# 3. Inject functions before onExtractDynamicInfo
insertion_point = -1
for i, line in enumerate(lines):
    if 'function onExtractDynamicInfo' in line:
        insertion_point = i
        break

if insertion_point != -1:
    functions_code = """
  async function handleRunWorkflow(e: CustomEvent) {
    const { command, cardId, cardTitle } = e.detail
    const project = projectStore.currentProject
    if (!project?.id) return

    const commandToName = {
      'dsl7': '智能章节续写与审计',
      'dsl6': '智能章节审计与同步',
      'dsl8': '角色设定智能补全'
    }
    const workflowName = commandToName[command]
    
    if (command === 'batch-analyze') {
      await handleBatchAnalyze()
      return
    }

    if (!workflowName) return

    const loading = ElMessage({
      message: `正在执行 AI 协作：${workflowName}...`,
      type: 'info',
      duration: 0
    })

    try {
      const { listWorkflows, runWorkflow } = await import('@renderer/api/workflows')
      const workflows = await listWorkflows()
      const wf = workflows.find(w => w.name === workflowName)
      
      if (!wf?.id) {
        throw new Error(`未找到工作流：${workflowName}`)
      }

      await runWorkflow(wf.id, {
        scope_json: {
          project_id: project.id,
          card_id: cardId,
          self_id: cardId
        },
        params_json: {}
      })

      loading.close()
      ElMessage.success(`AI 协作「${workflowName}」执行成功`)
      
      await cardStore.fetchCards(project.id)
      if (activeCard.value?.id === cardId) {
        cardStore.setActiveCard(cardId)
      }
    } catch (err: any) {
      loading.close()
      ElMessage.error(`执行失败: ${err.message || '未知错误'}`)
      console.error('Workflow run failed:', err)
    }
  }

  async function handleBatchAnalyze() {
    const project = projectStore.currentProject
    if (!project?.id) return

    try {
      await ElMessageBox.confirm(
        '“一键入库”将对本项目中所有“章节正文”卡片执行智能审计与同步，以构建初始知识图谱。这可能需要较长时间，是否继续？',
        '批量分析确认',
        { type: 'info', confirmButtonText: '开始分析', cancelButtonText: '取消' }
      )

      const chapterCards = cards.value.filter(c => c.card_type?.name === '章节正文')
      if (chapterCards.length === 0) {
        ElMessage.warning('未找到任何“章节正文”卡片')
        return
      }

      const loading = ElMessage({
        message: `正在准备批量分析 ${chapterCards.length} 个章节...`,
        type: 'info',
        duration: 0
      })

      const { listWorkflows, runWorkflow } = await import('@renderer/api/workflows')
      const workflows = await listWorkflows()
      const wf = workflows.find(w => w.name === '智能章节审计与同步')
      
      if (!wf?.id) {
        loading.close()
        throw new Error('未找到“智能章节审计与同步”工作流')
      }

      let successCount = 0
      let failCount = 0

      for (let i = 0; i < chapterCards.length; i++) {
        const card = chapterCards[i]
        loading.message = `正在分析第 ${i + 1}/${chapterCards.length} 章: ${card.title}...`
        
        try {
          await runWorkflow(wf.id, {
            scope_json: {
              project_id: project.id,
              card_id: card.id,
              self_id: card.id
            },
            params_json: {}
          })
          successCount++
        } catch (err) {
          console.error(`Failed to analyze card ${card.id}:`, err)
          failCount++
        }
      }

      loading.close()
      ElMessage.success(`批量分析完成！成功: ${successCount}, 失败: ${failCount}`)
      await cardStore.fetchCards(project.id)
    } catch (e) {
      if (e !== 'cancel') {
        ElMessage.error('批量分析过程中发生错误')
        console.error('Batch analyze failed:', e)
      }
    }
  }

"""
    lines.insert(insertion_point, functions_code)

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Successfully injected logic into Editor.vue")
