import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from '@/layouts/AppLayout.vue'

const routes = [
  {
    path: '/',
    component: AppLayout,
    redirect: '/dashboard',
    children: [
      { path: 'dashboard', name: 'dashboard', component: () => import('@/views/DashboardView.vue') },
      { path: 'models', name: 'models', component: () => import('@/views/ModelsView.vue') },
      { path: 'benchmarks', name: 'benchmarks', component: () => import('@/views/BenchmarksView.vue') },
      { path: 'experiments', name: 'experiments', component: () => import('@/views/ExperimentsView.vue') },
      { path: 'experiments/:id', name: 'experiment-detail', component: () => import('@/views/ExperimentDetailView.vue') },
    ],
  },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
