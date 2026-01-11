<template>
  <div id="app" class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-link" @click="goHome">
          <div class="logo-dot"></div>
          <div class="brand-text">
            <div class="brand-title">LoRA Dataset</div>
            <div class="brand-sub">视觉管家</div>
          </div>
        </div>
        <el-button
          class="theme-toggle"
          :icon="theme === 'dark' ? Sunny : Moon"
          circle
          size="small"
          @click="toggleTheme"
          :title="themeLabel"
        />
      </div>

      <div class="nav-actions">
        <el-button type="primary" icon="Plus" round @click="goUpload">新建上传</el-button>
        <el-button text icon="Refresh" @click="loadTasks">刷新项目</el-button>
      </div>

      <div class="section-title">项目</div>
      <div class="task-list">
        <el-skeleton v-if="loadingTasks" :rows="4" animated />
        <div v-else>
          <div
            v-for="task in tasks"
            :key="task.id"
            class="task-item"
            :class="{ active: task.id === selectedTaskId }"
            @click="openTask(task.id)"
          >
            <div class="task-name">{{ task.name }}</div>
            <div class="task-meta">
              <el-tag size="small" :type="statusTag(task.status)">{{ statusLabel(task.status) }}</el-tag>
              <span class="meta-text">{{ task.progress }}%</span>
            </div>
          </div>
          <div v-if="!tasks.length" class="empty-hint">暂无项目，点击上方"新建上传"</div>
        </div>
      </div>

    </aside>

    <main class="main-panel">
      <header class="topbar">
        <div class="title-stack">
          <div class="page-title">{{ currentTitle }}</div>
          <div class="page-sub">高级去重 | 美观界面 | 实时任务与裁切预览</div>
        </div>
        <div class="top-actions">
          <el-button text icon="Message">反馈</el-button>
          <el-button text icon="User">账户</el-button>
          <el-button text icon="Setting" @click="settingsVisible = true">设置</el-button>
        </div>
      </header>

      <section class="content-card">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" :key="$route.fullPath" />
          </transition>
        </router-view>
      </section>
    </main>
    <SettingsDialog 
      v-model:visible="settingsVisible" 
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { getTasks } from './services/api'
import type { Task } from './types/task'
import { Moon, Sunny } from '@element-plus/icons-vue'
import SettingsDialog from './components/SettingsDialog.vue'

const router = useRouter()
const route = useRoute()

const tasks = ref<Task[]>([])
const loadingTasks = ref(false)
const selectedTaskId = ref<number | null>(null)
const refreshTimer = ref<number | null>(null)
const theme = ref(localStorage.getItem('theme') || 'dark')

const settingsVisible = ref(false)


// 鍘婚噸璁剧疆鐩稿叧
const dedupSettingsForm = ref({
  face_sim_th1: 0.80,
  face_sim_th2: 0.85,
  pose_sim_th: 0.98,
  face_ssim_th1: 0.95,
  face_ssim_th2: 0.90,
  bbox_tol_c: 0.04,
  bbox_tol_wh: 0.06
})

// 浠巐ocalStorage鍔犺浇鍘婚噸璁剧疆
const loadDedupSettings = () => {
  const savedSettings = localStorage.getItem('dedupSettings')
  if (savedSettings) {
    const parsed = JSON.parse(savedSettings)
    dedupSettingsForm.value = {
      ...dedupSettingsForm.value,
      ...parsed
    }
  }
}

// 鍔犺浇鍘婚噸璁剧疆
loadDedupSettings()

const currentTitle = computed(() => {
  if (route.path.includes('upload')) return '上传任务'
  if (route.path.includes('tasks')) return '任务列表'
  return '控制台'
})

const themeLabel = computed(() => (theme.value === 'dark' ? '切换为浅色' : '切换为深色'))

const statusLabel = (status: string) => {
  const map: Record<string, string> = {
    uploading: '上传中',
    pending: '待处理',
    processing: '处理中',
    completed: '已完成',
    error: '错误'
  }
  return map[status] || status
}

const statusTag = (status: string) => {
  switch (status) {
    case 'completed':
      return 'success'
    case 'error':
      return 'danger'
    case 'processing':
      return 'warning'
    case 'uploading':
      return 'info'
    default:
      return ''
  }
}

const mergeTasks = (incoming: Task[]) => {
  const map = new Map<number, Task>()
  tasks.value.forEach(t => map.set(t.id, t))
  incoming.forEach(t => map.set(t.id, { ...map.get(t.id), ...t }))
  tasks.value = Array.from(map.values()).sort((a, b) => b.id - a.id)
}

const loadTasks = async (silent = false) => {
  if (!silent) loadingTasks.value = true
  try {
    const fresh = await getTasks()
    mergeTasks(fresh)
  } catch (error) {
    console.error('加载任务失败', error)
  } finally {
    if (!silent) loadingTasks.value = false
  }
}

const goUpload = () => {
  router.push('/upload')
}

const goHome = () => {
  router.push('/')
}

const openTask = (id: number) => {
  selectedTaskId.value = id
  router.push({ path: '/tasks', query: { taskId: id } })
}

const applyTheme = () => {
  document.documentElement.setAttribute('data-theme', theme.value)
  localStorage.setItem('theme', theme.value)
}

const toggleTheme = () => {
  theme.value = theme.value === 'dark' ? 'light' : 'dark'
  applyTheme()
}

onMounted(() => {
  applyTheme()
  loadTasks()
  // Only set up refresh timer if no taskId is in URL initially
  if (!route.query.taskId) {
    refreshTimer.value = window.setInterval(() => loadTasks(true), 5000)
  }
  if (route.query.taskId) {
    selectedTaskId.value = Number(route.query.taskId)
  }
})

// Watch for route changes to pause/resume refresh timer
watch(() => route.query.taskId, (newTaskId, oldTaskId) => {
  selectedTaskId.value = newTaskId ? Number(newTaskId) : null
  
  if (newTaskId && !oldTaskId && refreshTimer.value) {
    // Pause refresh timer when taskId is added to URL
    clearInterval(refreshTimer.value)
    refreshTimer.value = null
  } else if (!newTaskId && oldTaskId && !refreshTimer.value) {
    // Resume refresh timer when taskId is removed from URL
    refreshTimer.value = window.setInterval(() => loadTasks(true), 5000)
  }
})

onBeforeUnmount(() => {
  if (refreshTimer.value) {
    clearInterval(refreshTimer.value)
  }
})


</script>

<style scoped>
:global(:root[data-theme='dark']) {
  --bg: #0f1115;
  --surface: #151a23;
  --panel: #1a1f2b;
  --card: #1a1f2b;
  --text: #e9ebf1;
  --muted: #9ba3b4;
  --border: rgba(255, 255, 255, 0.08);
  --shadow: 0 18px 48px rgba(0, 0, 0, 0.35);
  --accent: #409eff;
}

:global(:root[data-theme='light']) {
  --bg: #f7f9fc;
  --surface: #ffffff;
  --panel: #ffffff;
  --card: #ffffff;
  --text: #1f2937;
  --muted: #6b7280;
  --border: rgba(0, 0, 0, 0.08);
  --shadow: 0 14px 34px rgba(31, 41, 55, 0.12);
  --accent: #409eff;
}

:global(html),
:global(body),
:global(#app) {
  width: 100%;
  height: 100%;
  overflow-x: hidden;
}

:global(body) {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: 'Inter', 'PingFang SC', 'Helvetica Neue', Arial, sans-serif;
}

:global(.el-card) {
  background-color: var(--card);
  border-color: var(--border);
  color: var(--text);
}

:global(.el-input__wrapper),
:global(.el-select .el-input__wrapper) {
  background-color: var(--surface);
}

:global(.el-button--text) {
  color: var(--muted);
}

:global(.el-image-viewer__canvas) {
  opacity: 1 !important;
}

:global(.el-button) {
  font-size: 14px !important;
  padding: 8px 16px !important;
}

:global(.el-alert__content) {
  padding: 12px 0 !important;
}

.app-shell {
  display: grid;
  grid-template-columns: 320px 1fr;
  height: 100vh;
  width: 100%;
  min-width: 0;
  background: radial-gradient(circle at 20% 20%, rgba(64, 158, 255, 0.08), transparent 30%),
    radial-gradient(circle at 80% 0%, rgba(103, 194, 58, 0.06), transparent 25%),
    var(--bg);
}

.sidebar {
  border-right: 1px solid var(--border);
  padding: 24px 18px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  backdrop-filter: blur(6px);
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}
.brand-link {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
}
.logo-dot {
  width: 34px;
  height: 34px;
  border-radius: 12px;
  background: linear-gradient(135deg, #5cf0c5, #409eff);
  box-shadow: 0 8px 24px rgba(64, 158, 255, 0.35);
}
.brand-text {
  display: flex;
  flex-direction: column;
}
.brand-title {
  font-weight: 700;
  font-size: 18px;
}
.brand-sub {
  font-size: 12px;
  color: var(--muted);
}
.theme-toggle {
  margin-left: auto;
}

.nav-actions {
  display: flex;
  gap: 8px;
}

.section-title {
  margin-top: 6px;
  font-size: 12px;
  color: var(--muted);
  letter-spacing: 0.5px;
}

.task-list {
  flex: 1;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-right: 6px;
}

.task-item {
  padding: 10px 12px;
  border-radius: 12px;
  background: var(--panel);
  border: 1px solid var(--border);
  cursor: pointer;
  transition: all 0.2s;
}
.task-item:hover {
  border-color: var(--accent);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.18);
}
.task-item.active {
  border-color: var(--accent);
  background: rgba(64, 158, 255, 0.12);
}
.task-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 6px;
}
.task-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--muted);
  font-size: 12px;
}
.meta-text {
  color: var(--muted);
}
.empty-hint {
  padding: 12px;
  color: var(--muted);
  font-size: 13px;
}

.main-panel {
  display: flex;
  flex-direction: column;
  height: 100vh;
  padding: 20px 24px;
  min-width: 0;
}

.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-radius: 16px;
  background: var(--panel);
  border: 1px solid var(--border);
  box-shadow: var(--shadow);
}
.title-stack {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.page-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text);
}
.page-sub {
  font-size: 12px;
  color: var(--muted);
}
.top-actions {
  display: flex;
  gap: 8px;
}

.content-card {
  margin-top: 16px;
  flex: 1;
  border-radius: 16px;
  background: var(--card);
  border: 1px solid var(--border);
  box-shadow: var(--shadow);
  padding: 16px;
  overflow-y: auto;
  overflow-x: hidden;
  min-width: 0;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
.setting-hint {
  font-size: 12px;
  color: var(--muted);
}

/* 璁剧疆椤甸潰鏍峰紡 */
.settings-layout {
  display: flex;
  gap: 20px;
  min-height: 400px;
}
.settings-sidebar {
  width: 200px;
  background-color: var(--panel);
  border-radius: 8px;
  border: 1px solid var(--border);
  overflow: hidden;
}
.settings-menu {
  background-color: transparent;
  border-right: none;
}
.settings-menu :deep(.el-menu-item) {
  background-color: transparent;
  border-radius: 0;
}
.settings-menu :deep(.el-menu-item.is-active) {
  background-color: var(--accent);
  color: white;
}
.settings-content {
  flex: 1;
  overflow-y: auto;
}
.settings-section {
  padding: 10px 0;
}
.form-hint {
  font-size: 12px;
  color: var(--muted);
  margin-top: 4px;
  margin-bottom: 8px;
}
</style>
