<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { init, use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { useRouter } from 'vue-router'
import { benchmarks, categoryRisk, experiments, models } from '@/data/demo.js'

const router = useRouter()
use([BarChart, GridComponent, TooltipComponent, CanvasRenderer])
const chartRef = ref(null)
let chart
const completed = computed(() => experiments.filter((item) => item.status === 'completed').length)
const averageAsr = computed(() => (experiments.reduce((sum, item) => sum + item.asr, 0) / experiments.length).toFixed(1))
const statusType = (status) => ({ completed: 'success', running: 'primary', failed: 'danger' }[status] || 'info')
const statusLabel = (status) => ({ completed: '已完成', running: '运行中', failed: '失败' }[status] || status)

const metrics = computed(() => [
  { label: '目标模型', value: models.length, desc: `${models.filter((item) => item.status === 'online').length} 个连接正常`, tone: 'blue' },
  { label: 'Benchmark', value: benchmarks.length, desc: `${benchmarks.reduce((sum, item) => sum + item.cases, 0)} 条测试用例`, tone: 'violet' },
  { label: '评测实验', value: experiments.length, desc: `${completed.value} 个已完成`, tone: 'green' },
  { label: '平均 ASR', value: `${averageAsr.value}%`, desc: '越低表示防护越稳健', tone: 'orange' },
])

const renderChart = () => {
  if (!chartRef.value) return
  chart = init(chartRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 18, right: 24, top: 10, bottom: 8, containLabel: true },
    xAxis: { type: 'value', max: 30, splitLine: { lineStyle: { color: '#eef2f7' } } },
    yAxis: { type: 'category', data: categoryRisk.map((item) => item.name), axisTick: { show: false }, axisLine: { show: false } },
    series: [{ type: 'bar', data: categoryRisk.map((item) => item.value), barWidth: 16, itemStyle: { color: '#0a66c2', borderRadius: [0, 5, 5, 0] } }],
  })
}
const resizeChart = () => chart?.resize()
onMounted(() => { nextTick(renderChart); window.addEventListener('resize', resizeChart) })
onBeforeUnmount(() => { window.removeEventListener('resize', resizeChart); chart?.dispose() })
</script>

<template>
  <section class="metrics-grid">
    <article v-for="item in metrics" :key="item.label" class="metric-card" :class="`metric-${item.tone}`">
      <span>{{ item.label }}</span><strong>{{ item.value }}</strong><small>{{ item.desc }}</small>
    </article>
  </section>

  <section class="dashboard-grid">
    <div class="stack">
      <article class="panel">
        <div class="panel-head"><div><h2>风险类别暴露率</h2><p>当前实验中各类风险的攻击成功率</p></div><el-button text type="primary" @click="router.push('/experiments')">查看实验</el-button></div>
        <div ref="chartRef" class="chart"></div>
      </article>
      <article class="panel">
        <div class="panel-head"><div><h2>近期实验</h2><p>最近创建的模型安全评测任务</p></div></div>
        <el-table :data="experiments.slice(0, 3)" stripe>
          <el-table-column prop="name" label="实验名称" min-width="180" />
          <el-table-column prop="model" label="目标模型" min-width="130" />
          <el-table-column label="状态" width="110"><template #default="{ row }"><el-tag :type="statusType(row.status)" effect="light">{{ statusLabel(row.status) }}</el-tag></template></el-table-column>
          <el-table-column label="ASR" width="90"><template #default="{ row }"><strong>{{ row.asr }}%</strong></template></el-table-column>
          <el-table-column width="88"><template #default="{ row }"><el-button link type="primary" @click="router.push(`/experiments/${row.id}`)">详情</el-button></template></el-table-column>
        </el-table>
      </article>
    </div>

    <article class="panel activity-panel">
      <div class="panel-head"><div><h2>系统状态</h2><p>评测资源与执行队列</p></div></div>
      <div class="health-row"><span>API 服务</span><el-tag type="success" effect="light">正常</el-tag></div>
      <div class="health-row"><span>后台 Worker</span><el-tag type="success" effect="light">空闲</el-tag></div>
      <div class="health-row"><span>等待任务</span><strong>0</strong></div>
      <div class="health-row"><span>运行任务</span><strong>1</strong></div>
      <div class="divider"></div>
      <h3>攻击方法</h3>
      <div class="attack-list"><span>Direct</span><span>Role-play</span><span>Transformation</span><span class="muted">PAIR · 规划中</span></div>
      <el-button class="full-button" type="primary" @click="router.push('/experiments')">创建新实验</el-button>
    </article>
  </section>
</template>
