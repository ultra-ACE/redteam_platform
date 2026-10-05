<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { benchmarks, experiments, models } from '@/data/demo.js'

const router = useRouter()
const dialogVisible = ref(false)
const form = reactive({ name: '', model: '', benchmark: '', attacks: ['Direct'], sampleSize: 20, concurrency: 2 })
const statusType = (status) => ({ completed: 'success', running: 'primary', failed: 'danger' }[status] || 'info')
const statusLabel = (status) => ({ completed: '已完成', running: '运行中', failed: '失败' }[status] || status)
const createExperiment = () => { ElMessage.success('实验已创建（演示）'); dialogVisible.value = false }
</script>

<template>
  <div class="toolbar"><div><strong>评测实验</strong><span>按统一配置执行 Benchmark × Attack × Model × Judge</span></div><el-button type="primary" @click="dialogVisible = true">创建实验</el-button></div>
  <article class="panel table-panel">
    <el-table :data="experiments" stripe>
      <el-table-column prop="name" label="实验名称" min-width="180" />
      <el-table-column prop="model" label="目标模型" min-width="130" />
      <el-table-column prop="benchmark" label="Benchmark" min-width="140" />
      <el-table-column label="攻击方法" min-width="180"><template #default="{ row }"><el-tag v-for="attack in row.attacks" :key="attack" class="inline-tag" type="info" effect="plain">{{ attack }}</el-tag></template></el-table-column>
      <el-table-column label="状态" width="110"><template #default="{ row }"><el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag></template></el-table-column>
      <el-table-column label="进度" width="170"><template #default="{ row }"><el-progress :percentage="row.progress" :stroke-width="8" /></template></el-table-column>
      <el-table-column label="ASR" width="90"><template #default="{ row }"><strong>{{ row.asr }}%</strong></template></el-table-column>
      <el-table-column width="90"><template #default="{ row }"><el-button link type="primary" @click="router.push(`/experiments/${row.id}`)">详情</el-button></template></el-table-column>
    </el-table>
  </article>

  <el-dialog v-model="dialogVisible" title="创建评测实验" width="620px">
    <el-form :model="form" label-width="110px">
      <el-form-item label="实验名称"><el-input v-model="form.name" placeholder="例如 模型安全基线测试" /></el-form-item>
      <el-form-item label="目标模型"><el-select v-model="form.model" class="full-select" placeholder="选择模型"><el-option v-for="item in models" :key="item.id" :label="item.name" :value="item.name" /></el-select></el-form-item>
      <el-form-item label="Benchmark"><el-select v-model="form.benchmark" class="full-select" placeholder="选择测试集"><el-option v-for="item in benchmarks" :key="item.id" :label="item.name" :value="item.name" /></el-select></el-form-item>
      <el-form-item label="攻击方法"><el-checkbox-group v-model="form.attacks"><el-checkbox value="Direct">Direct</el-checkbox><el-checkbox value="Role-play">Role-play</el-checkbox><el-checkbox value="Transformation">Transformation</el-checkbox><el-checkbox value="PAIR" disabled>PAIR</el-checkbox></el-checkbox-group></el-form-item>
      <el-form-item label="抽样数量"><el-input-number v-model="form.sampleSize" :min="1" :max="100" /></el-form-item>
      <el-form-item label="并发数"><el-input-number v-model="form.concurrency" :min="1" :max="5" /></el-form-item>
    </el-form>
    <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" @click="createExperiment">创建实验</el-button></template>
  </el-dialog>
</template>
