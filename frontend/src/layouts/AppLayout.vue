<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { DataAnalysis, Cpu, Collection, SetUp, Document } from '@element-plus/icons-vue'

const route = useRoute()
const pageTitles = {
  dashboard: ['安全概览', '汇总模型风险、任务进度与近期实验'],
  models: ['模型管理', '维护目标模型及接口连接状态'],
  benchmarks: ['数据集管理', '管理风险行为集与正常请求集'],
  experiments: ['实验中心', '创建并跟踪红队安全评测任务'],
  'experiment-detail': ['实验详情', '查看执行进度、指标与判定证据'],
}
const currentTitle = computed(() => pageTitles[route.name] || ['RedEval', '大模型红队安全评测平台'])
</script>

<template>
  <div class="app-shell">
    <header class="top-nav">
      <div class="brand">
        <div class="brand-mark">R</div>
        <div><strong>RedEval</strong><span>大模型红队安全评测平台</span></div>
      </div>
      <div class="header-right">
        <span class="system-status"><span class="status-dot"></span> 演示环境运行中</span>
        <div class="avatar">R</div>
      </div>
    </header>

    <div class="workspace">
      <aside class="sidebar">
        <el-menu router :default-active="route.path">
          <el-menu-item index="/dashboard"><el-icon><DataAnalysis /></el-icon><span>安全概览</span></el-menu-item>
          <el-menu-item index="/models"><el-icon><Cpu /></el-icon><span>模型管理</span></el-menu-item>
          <el-menu-item index="/benchmarks"><el-icon><Collection /></el-icon><span>数据集管理</span></el-menu-item>
          <el-menu-item index="/experiments"><el-icon><SetUp /></el-icon><span>实验中心</span></el-menu-item>
          <el-menu-item disabled><el-icon><Document /></el-icon><span>报告中心</span><em>即将开放</em></el-menu-item>
        </el-menu>
        <div class="sidebar-foot"><span>RedEval MVP</span><small>Version 0.1.0</small></div>
      </aside>

      <main class="main-content">
        <div class="page-heading"><div><h1>{{ currentTitle[0] }}</h1><p>{{ currentTitle[1] }}</p></div><el-tag type="info" effect="plain">Mock Data</el-tag></div>
        <router-view />
      </main>
    </div>
  </div>
</template>
