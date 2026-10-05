<script setup>
import { ref } from 'vue'
import { UploadFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { benchmarks } from '@/data/demo.js'

const importDialogVisible = ref(false)
const detailDialogVisible = ref(false)
const selectedDataset = ref(null)
const uploadFiles = ref([])

const openImportDialog = () => {
  uploadFiles.value = []
  importDialogVisible.value = true
}

const importDataset = () => {
  if (!uploadFiles.value.length) {
    ElMessage.warning('请先选择数据集文件')
    return
  }
  ElMessage.success(`数据集 ${uploadFiles.value[0].name} 已导入（演示）`)
  importDialogVisible.value = false
}

const openDatasetDetail = (dataset) => {
  selectedDataset.value = dataset
  detailDialogVisible.value = true
}
</script>

<template>
  <div class="toolbar"><div><strong>测试数据集</strong><span>风险集与正常集独立统计，确保结果可解释</span></div><el-button type="primary" @click="openImportDialog">导入数据集</el-button></div>
  <div class="benchmark-grid">
    <article v-for="item in benchmarks" :key="item.id" class="panel benchmark-card">
      <div class="benchmark-title"><div class="dataset-icon">DS</div><div><h2>{{ item.name }}</h2><p>{{ item.version }}</p></div><el-tag type="success">已就绪</el-tag></div>
      <div class="benchmark-stats"><div><strong>{{ item.cases }}</strong><span>测试用例</span></div><div><strong>{{ item.categories }}</strong><span>风险类别</span></div><div><strong>{{ item.type }}</strong><span>数据类型</span></div></div>
      <div class="card-actions"><el-button type="primary" plain @click="openDatasetDetail(item)">详情</el-button></div>
    </article>
  </div>

  <el-dialog v-model="detailDialogVisible" title="数据集详情" width="560px">
    <el-descriptions v-if="selectedDataset" :column="2" border>
      <el-descriptions-item label="数据集名称" :span="2">{{ selectedDataset.name }}</el-descriptions-item>
      <el-descriptions-item label="用例数">{{ selectedDataset.cases }}</el-descriptions-item>
      <el-descriptions-item label="风险类型">{{ selectedDataset.categories }} 类</el-descriptions-item>
      <el-descriptions-item label="数据集类型" :span="2">{{ selectedDataset.type }}</el-descriptions-item>
    </el-descriptions>
    <template #footer><el-button type="primary" @click="detailDialogVisible = false">关闭</el-button></template>
  </el-dialog>

  <el-dialog v-model="importDialogVisible" title="导入数据集" width="560px" :close-on-click-modal="false">
    <el-upload
      v-model:file-list="uploadFiles"
      class="dataset-upload"
      drag
      action="#"
      accept=".json,.jsonl,.csv"
      :auto-upload="false"
      :limit="1"
    >
      <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
      <div class="el-upload__text">将文件拖到此处，或<em>点击选择文件</em></div>
      <template #tip><div class="el-upload__tip">支持 JSON、JSONL、CSV 格式，单次上传一个文件</div></template>
    </el-upload>
    <template #footer>
      <el-button @click="importDialogVisible = false">取消</el-button>
      <el-button type="primary" @click="importDataset">确认导入</el-button>
    </template>
  </el-dialog>
</template>
