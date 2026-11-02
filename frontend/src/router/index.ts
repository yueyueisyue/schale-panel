import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  // 开屏动画直接长在登录页背景上，不再单设 Boot 页
  { path: '/', redirect: '/login' },
  { path: '/login', name: 'login', component: () => import('@/pages/Login.vue'), meta: { bare: true } },
  { path: '/checkin', name: 'checkin', component: () => import('@/pages/Checkin.vue'), meta: { bare: true } },
  { path: '/home', name: 'home', component: () => import('@/pages/Home.vue') },
  { path: '/cafe', name: 'cafe', component: () => import('@/pages/Cafe.vue') },
  { path: '/shop', name: 'shop', component: () => import('@/pages/Shop.vue') },
  { path: '/members', name: 'members', component: () => import('@/pages/Members.vue') },
  { path: '/member/:key', name: 'member', component: () => import('@/pages/MemberDetail.vue') },
  { path: '/social', name: 'social', component: () => import('@/pages/Social.vue') },
  { path: '/daily', name: 'daily', component: () => import('@/pages/Daily.vue') },
  { path: '/tasks', name: 'tasks', component: () => import('@/pages/Tasks.vue') },
  { path: '/squad', name: 'squad', component: () => import('@/pages/Squad.vue') },
  { path: '/spine', name: 'spine', component: () => import('@/pages/SpineTest.vue'), meta: { bare: true } },
  { path: '/:pathMatch(.*)*', redirect: '/login' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 极简门禁：没有 token → 回登录
// ?preview=1 时放行（仅开发期截图验货用）
router.beforeEach((to) => {
  if (to.meta.bare) return true
  if (new URLSearchParams(location.search).has('preview')) return true
  const token = localStorage.getItem('schale_token')
  if (!token) return { name: 'login' }
  return true
})

export default router
