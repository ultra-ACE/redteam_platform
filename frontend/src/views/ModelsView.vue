<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { Connection, Delete, EditPen } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { models } from '@/data/demo.js'

const dialogVisible = ref(false)
const dialogMode = ref('create')
const editingId = ref(null)
const activeType = ref('all')
const currentPage = ref(1)
const pageSize = ref(10)
const form = reactive({
  type: 'online',
  endpointUrl: '',
  apiKey: '',
  model: '',
})

const filteredModels = computed(() => {
  if (activeType.value === 'all') return models
  return models.filter((item) => item.type === activeType.value)
})
const pagedModels = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredModels.value.slice(start, start + pageSize.value)
})
const onlineCount = computed(() => models.filter((item) => item.type === 'online').length)
const localCount = computed(() => models.filter((item) => item.type === 'local').length)
watch(activeType, () => { currentPage.value = 1 })
const resetModelForm = (type = form.type) => {
  Object.assign(form, {
    type,
    endpointUrl: '',
    apiKey: '',
    model: '',
  })
}
const openCreateDialog = () => {
  dialogMode.value = 'create'
  editingId.value = null
  resetModelForm('online')
  dialogVisible.value = true
}
const changeModelType = (type) => resetModelForm(type)
const testConnection = (row) => { ElMessage.success(`${row.model} 连接测试成功（演示）`) }
const openEditDialog = (row) => {
  dialogMode.value = 'edit'
  editingId.value = row.id
  Object.assign(form, {
    type: row.type,
    endpointUrl: row.endpoint || '',
    apiKey: '',
    model: row.model || '',
  })
  dialogVisible.value = true
}
const saveModel = () => {
  if (form.type === 'online' && (!form.endpointUrl || !form.model || (dialogMode.value === 'create' && !form.apiKey))) {
    ElMessage.warning('请填写接口地址、API Key 和模型名称')
    return
  }
  if (form.type === 'local' && (!form.model || !form.endpointUrl)) {
    ElMessage.warning('请填写模型名称和接口地址')
    return
  }
  if (dialogMode.value === 'edit') {
    const row = models.find((item) => item.id === editingId.value)
    if (row) {
      Object.assign(row, {
        type: form.type,
        model: form.model,
        endpoint: form.endpointUrl,
        status: 'offline',
        latency: 0,
      })
    }
    ElMessage.success('模型信息已更新，请重新测试连接')
  } else {
    models.push({
      id: Date.now(),
      name: form.model,
      type: form.type,
      provider: form.type === 'online' ? 'Custom API' : 'Local Service',
      protocol: 'OpenAI Compatible',
      endpoint: form.endpointUrl,
      model: form.model,
      status: 'offline',
      latency: 0,
    })
    ElMessage.success(`${form.type === 'online' ? '在线' : '本地'}模型已创建，请测试连接`)
  }
  dialogVisible.value = false
}
const deleteModel = (row) => {
  ElMessageBox.confirm(`确认删除模型“${row.model}”吗？`, '删除模型', {
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(() => {
    const index = models.findIndex((item) => item.id === row.id)
    if (index >= 0) models.splice(index, 1)
    const lastPage = Math.max(1, Math.ceil(filteredModels.value.length / pageSize.value))
    if (currentPage.value > lastPage) currentPage.value = lastPage
    ElMessage.success('模型已删除')
  }).catch(() => {})
}
</script>

<template>
  <section class="model-summary">
    <div><span>全部模型</span><strong>{{ models.length }}</strong></div>
    <div><span>在线 API 模型</span><strong>{{ onlineCount }}</strong></div>
    <div><span>本地部署模型</span><strong>{{ localCount }}</strong></div>
    <div><span>连接正常</span><strong>{{ models.filter((item) => item.status === 'online').length }}</strong></div>
  </section>

  <div class="toolbar model-toolbar">
    <el-segmented v-model="activeType" :options="[
      { label: `全部 (${models.length})`, value: 'all' },
      { label: `在线模型 (${onlineCount})`, value: 'online' },
      { label: `本地模型 (${localCount})`, value: 'local' },
    ]" />
    <div class="model-actions">
      <el-button type="primary" @click="openCreateDialog">新建模型</el-button>
    </div>
  </div>

  <article class="panel table-panel">
    <el-table :data="pagedModels" stripe>
      <el-table-column prop="model" label="模型名称" width="190" align="center" show-overflow-tooltip />
      <el-table-column prop="endpoint" label="接口地址" min-width="280" align="center" show-overflow-tooltip />
      <el-table-column label="模型类型" width="130" align="center">
        <template #default="{ row }">
          <el-tag :type="row.type === 'online' ? 'primary' : 'warning'" effect="light">
            {{ row.type === 'online' ? '在线 API' : '本地部署' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="连接状态" width="120" align="center"><template #default="{ row }"><el-tag :type="row.status === 'online' ? 'success' : 'info'">{{ row.status === 'online' ? '正常' : '未连接' }}</el-tag></template></el-table-column>
      <el-table-column label="响应延迟" width="120" align="center"><template #default="{ row }">{{ row.latency ? `${row.latency} ms` : '-' }}</template></el-table-column>
      <el-table-column label="操作" min-width="320" align="center">
        <template #default="{ row }">
          <div class="action-group">
            <el-button class="action-button" size="small" plain :icon="Connection" @click="testConnection(row)">测试连接</el-button>
            <el-button class="action-button" size="small" plain :icon="EditPen" @click="openEditDialog(row)">编辑</el-button>
            <el-button class="action-button" size="small" plain type="danger" :icon="Delete" @click="deleteModel(row)">删除</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>
    <div class="pagination-wrap">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="filteredModels.length"
        layout="total, prev, pager, next, jumper"
        background
      />
    </div>
  </article>

  <el-dialog v-model="dialogVisible" width="700px" class="model-dialog" :close-on-click-modal="false">
    <template #header>
      <div class="dialog-heading">
        <strong>{{ dialogMode === 'create' ? '添加模型' : '编辑模型' }}</strong>
        <span>OpenAI 兼容协议</span>
      </div>
    </template>

    <el-form :model="form" label-position="top" class="provider-form">
      <div class="model-type-switch">
        <el-segmented v-model="form.type" :options="[
          { label: '在线模型', value: 'online' },
          { label: '本地模型', value: 'local' },
        ]" @change="changeModelType" />
      </div>

      <template v-if="form.type === 'online'">
        <el-form-item label="接口地址">
          <el-input v-model="form.endpointUrl" size="large" placeholder="例如 https://api.example.com/v1/chat/completions" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="form.apiKey" size="large" type="password" show-password :placeholder="dialogMode === 'edit' ? '留空表示不修改 API Key' : '输入你的 API Key'" autocomplete="new-password" />
        </el-form-item>
        <el-form-item label="模型名称">
          <el-input v-model="form.model" size="large" placeholder="输入接口要求的模型名称，例如 deepseek-chat" />
        </el-form-item>
        <p class="form-note">接口地址需填写完整请求路径，并兼容 OpenAI Chat Completions 请求格式。</p>
      </template>

      <template v-else>
        <el-form-item label="模型名称">
          <el-input v-model="form.model" size="large" placeholder="例如 qwen2.5:7b" />
        </el-form-item>
        <el-form-item label="接口地址">
          <el-input v-model="form.endpointUrl" size="large" placeholder="例如 http://127.0.0.1:11434/v1/chat/completions" />
        </el-form-item>
        <p class="form-note">请先启动本地推理服务，并确认其提供 OpenAI 兼容接口。</p>
      </template>
    </el-form>
    <template #footer><el-button size="large" @click="dialogVisible = false">取消</el-button><el-button type="primary" size="large" @click="saveModel">{{ dialogMode === 'create' ? '创建' : '保存修改' }}</el-button></template>
  </el-dialog>
</template>

<style scoped>
.model-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 10px;
}

.model-summary div {
  padding: 14px 16px;
  background: #fff;
  border-radius: 5px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, .1);
}

.model-summary span,
.model-summary strong {
  display: block;
}

.model-summary span {
  color: #64748b;
  font-size: 13px;
}

.model-summary strong {
  margin-top: 8px;
  color: #0f172a;
  font-size: 24px;
}

.model-toolbar {
  gap: 16px;
}

.model-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.action-button {
  min-width: 78px;
  margin: 0 !important;
}

.action-group {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  white-space: nowrap;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  padding: 16px 4px 2px;
}

.dialog-heading {
  display: flex;
  align-items: center;
  gap: 12px;
}

.dialog-heading strong {
  color: #111;
  font-size: 20px;
}

.dialog-heading span {
  padding: 5px 10px;
  color: #0a66c2;
  background: #eaf3fc;
  border: 1px solid #cfe3f7;
  border-radius: 14px;
  font-size: 13px;
}

.form-note {
  margin: 2px 0 0;
  color: #64748b;
  font-size: 13px;
}

.model-type-switch {
  display: flex;
  margin-bottom: 18px;
}

.model-type-switch :deep(.el-segmented) {
  width: 100%;
}

.model-type-switch :deep(.el-segmented__item) {
  min-height: 38px;
}

.model-type-switch :deep(.el-segmented__item-selected) {
  color: #0a66c2;
}

:deep(.model-dialog) {
  border-radius: 14px;
}

:deep(.model-dialog .el-dialog__header) {
  margin-right: 0;
  padding: 20px 24px;
  border-bottom: 1px solid #e5e7eb;
}

:deep(.model-dialog .el-dialog__body) {
  padding: 18px 24px 14px;
}

:deep(.model-dialog .el-dialog__footer) {
  padding: 16px 24px;
  border-top: 1px solid #e5e7eb;
}

:deep(.provider-form .el-form-item) {
  margin-bottom: 15px;
}

:deep(.provider-form .el-form-item__label) {
  width: 100%;
  margin-bottom: 7px;
  color: #4b5563;
  font-weight: 600;
}
</style>
