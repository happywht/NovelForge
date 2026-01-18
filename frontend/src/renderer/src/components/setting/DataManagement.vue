<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { backupDatabase, restoreDatabase } from '@renderer/api/setting'

const loading = ref(false)

async function handleBackup() {
  console.log('Backup clicked', backupDatabase)
  try {
    loading.value = true
    const blob = await backupDatabase()
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `aiauthor_backup_${new Date().toISOString().slice(0, 10)}.db`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success('备份下载成功')
  } catch (error) {
    console.error(error)
    ElMessage.error('备份失败')
  } finally {
    loading.value = false
  }
}

async function handleRestore(file: any) {
  console.log('Restore clicked', file)
  try {
    await ElMessageBox.confirm(
      '恢复数据库将覆盖当前所有数据，且不可撤销。建议先备份当前数据。确定要继续吗？',
      '危险操作警告',
      {
        confirmButtonText: '确定恢复',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    loading.value = true
    await restoreDatabase(file.raw)
    ElMessage.success('恢复成功，请重启应用')
  } catch (error) {
    if (error !== 'cancel') {
      console.error(error)
      ElMessage.error('恢复失败')
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="data-management">
    <h3>数据管理</h3>
    
    <el-card class="box-card">
      <template #header>
        <div class="card-header">
          <span>数据库备份与恢复</span>
        </div>
      </template>
      <div class="action-row">
        <div class="action-item">
          <h4>备份数据</h4>
          <p>下载当前数据库文件 (aiauthor.db) 到本地。</p>
          <el-button type="primary" @click="handleBackup" :loading="loading">
            下载备份
          </el-button>
        </div>
        
        <el-divider direction="vertical" style="height: 100px" />
        
        <div class="action-item">
          <h4>恢复数据</h4>
          <p>上传数据库文件覆盖当前数据 (慎用)。</p>
          <el-upload
            action=""
            :auto-upload="false"
            :show-file-list="false"
            accept=".db"
            :on-change="handleRestore"
          >
            <el-button type="danger" :loading="loading">
              上传并恢复
            </el-button>
          </el-upload>
        </div>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.data-management {
  padding: 20px;
}
.action-row {
  display: flex;
  justify-content: space-around;
  align-items: center;
}
.action-item {
  text-align: center;
  flex: 1;
}
.action-item p {
  color: #909399;
  font-size: 13px;
  margin-bottom: 16px;
}
</style>
