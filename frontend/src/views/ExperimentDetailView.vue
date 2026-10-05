<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { experiments, runRows } from '@/data/demo.js'

const route = useRoute()
const router = useRouter()
const experiment = computed(() => experiments.find((item) => item.id === route.params.id) || experiments[0])
const resultType = (result) => ({ success: 'danger', failed: 'success', invalid: 'info', review: 'warning' }[result] || 'info')
const resultLabel = (result) => ({ success: '攻击成功', failed: '防御成功', invalid: '无效', review: '待复核' }[result] || result)
</script>

<template>
  <div class="detail-back"><el-button link type="primary" @click="router.push('/experiments')">← 返回实验列表</el-button></div>
  <section class="detail-grid">
    <article class="panel detail-summary">
      <div class="panel-head"><div><h2>{{ experiment.name }}</h2><p>{{ experiment.id }} · {{ experiment.createdAt }}</p></div><el-tag :type="experiment.status === 'completed' ? 'success' : 'primary'">{{ experiment.status }}</el-tag></div>
      <el-progress :percentage="experiment.progress" :stroke-width="10" />
      <div class="summary-metrics"><div><span>总测试</span><strong>{{ experiment.total }}</strong></div><div><span>攻击成功</span><strong class="danger-text">{{ experiment.success }}</strong></div><div><span>无效测试</span><strong>{{ experiment.invalid }}</strong></div><div><span>攻击成功率</span><strong>{{ experiment.asr }}%</strong></div></div>
    </article>
    <article class="panel config-card"><h2>实验配置</h2><dl><div><dt>目标模型</dt><dd>{{ experiment.model }}</dd></div><div><dt>Benchmark</dt><dd>{{ experiment.benchmark }}</dd></div><div><dt>攻击方法</dt><dd>{{ experiment.attacks.join('、') }}</dd></div><div><dt>判定器</dt><dd>StrongREJECT</dd></div></dl></article>
  </section>
  <article class="panel table-panel runs-panel">
    <div class="panel-head"><div><h2>测试运行记录</h2><p>失败表示攻击未突破；无效表示接口或执行异常</p></div><el-button>导出结果</el-button></div>
    <el-table :data="runRows" stripe>
      <el-table-column prop="id" label="Run ID" width="105" />
      <el-table-column prop="category" label="风险类别" min-width="130" />
      <el-table-column prop="attack" label="攻击方法" min-width="120" />
      <el-table-column label="结果" width="110"><template #default="{ row }"><el-tag :type="resultType(row.result)">{{ resultLabel(row.result) }}</el-tag></template></el-table-column>
      <el-table-column label="判定分" width="100"><template #default="{ row }">{{ row.score.toFixed(2) }}</template></el-table-column>
      <el-table-column prop="judge" label="判定器" min-width="130" />
      <el-table-column label="延迟" width="110"><template #default="{ row }">{{ row.latency }} ms</template></el-table-column>
      <el-table-column width="90"><template #default><el-button link type="primary">证据</el-button></template></el-table-column>
    </el-table>
  </article>
</template>
