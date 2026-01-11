<template>
  <div class="task-list-container">
    <div class="page-header">
      <div class="card-header">
        <span>任务列表</span>
        <div class="header-actions">
          <el-button 
            type="primary" 
            @click="refreshTasks"
            :loading="loading"
          >
            <el-icon>
              <Refresh />
            </el-icon>
            刷新
          </el-button>
          <el-button 
            type="danger" 
            plain
            size="small"
            @click="confirmDeleteAll"
            :loading="loading"
          >
            清空所有任务
          </el-button>
          <el-button size="small" @click="bulkRun('dedup')" :loading="loading">全量去重</el-button>
          <el-button size="small" @click="bulkRun('crop')" :loading="loading">全量裁切</el-button>
          <el-button size="small" @click="bulkRun('caption')" :loading="loading">全量提示词</el-button>
          <el-button size="small" type="success" @click="bulkRun('export')" :loading="loading">全量导出</el-button>
        </div>
      </div>
    </div>
      
    <!-- Task Filter -->
    <div class="task-filter">
      <el-input
        v-model="filter.text"
        placeholder="搜索任务名称"
        clearable
        prefix-icon="Search"
        style="width: 250px; margin-right: 10px"
      />
      
      <el-select
        v-model="filter.status"
        placeholder="筛选状态"
        clearable
        style="width: 150px; margin-right: 10px"
      >
        <el-option
          v-for="status in statusOptions"
          :key="status.value"
          :label="status.label"
          :value="status.value"
        />
      </el-select>
      
      <el-select
        v-model="filter.stage"
        placeholder="筛选阶段"
        clearable
        style="width: 150px"
      >
        <el-option
          v-for="stage in stageOptions"
          :key="stage.value"
          :label="stage.label"
          :value="stage.value"
        />
      </el-select>
    </div>
    
    <!-- Task Table -->
    <el-table
      v-loading="loading"
      :data="filteredTasks"
      stripe
      style="width: 100%"
      @row-click="handleRowClick"
    >
      <el-table-column
        prop="id"
        label="任务ID"
        width="80"
      />
      <el-table-column
        prop="name"
        label="任务名称"
        min-width="220"
        show-overflow-tooltip
      >
        <template #default="scope">
          <el-tooltip :content="scope.row.name" placement="top">
            <span class="name-ellipsis">{{ scope.row.name }}</span>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column
        prop="status"
        label="状态"
        width="120"
      >
        <template #default="scope">
          <el-tag :type="getStatusTagType(scope.row.status)">
            {{ getStatusLabel(scope.row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        prop="stage"
        label="阶段"
        width="150"
      >
        <template #default="scope">
          <el-tag :type="getStageTagType(scope.row.stage)">
            {{ getStageLabel(scope.row.stage) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        prop="progress"
        label="进度"
        width="260"
      >
        <template #default="scope">
          <task-progress-cell
            :overall-percent="scope.row.progress_detail?.overall_percent ?? scope.row.progress"
            :stage-index="scope.row.progress_detail?.stage_index || 1"
            :stage-total="scope.row.progress_detail?.stage_total || 4"
            :stage-percent="scope.row.progress_detail?.stage_percent || scope.row.progress"
            :stage-name="scope.row.progress_detail?.stage_name || getStageLabel(scope.row.stage)"
            :step-hint="scope.row.progress_detail?.step_hint"
          />
        </template>
      </el-table-column>
      <el-table-column
        label="照片数"
        width="140"
      >
        <template #default="scope">
          <span>{{ getTaskProcessedCount(scope.row) }}</span>
          /
          <span>{{ getTaskTotalCount(scope.row) }}</span>
        </template>
      </el-table-column>
      <el-table-column
        prop="created_at"
        label="创建时间"
        width="150"
        >
          <template #default="scope">
            {{ formatTime(scope.row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column
          prop="updated_at"
          label="更新时间"
          width="150"
        >
          <template #default="scope">
            {{ formatTime(scope.row.updated_at) }}
          </template>
        </el-table-column>
        <el-table-column
          label="操作"
          width="160"
          fixed="right"
        >
          <template #default="scope">
          <div class="table-actions">
            <el-button 
              type="primary" 
              size="small"
              class="action-button"
              @click.stop="viewTaskDetails(scope.row, true)"
            >
              查看详情
            </el-button>
            <el-tooltip
              :content="downloadDisableReason(scope.row)"
              placement="top"
              :disabled="!isDownloadDisabled(scope.row)"
            >
              <div>
                <el-button 
                  type="info" 
                  size="small"
                  plain
                  class="action-button"
                  :disabled="isDownloadDisabled(scope.row)"
                  @click.stop="downloadTask(scope.row.id)"
                >
                  <el-icon>
                    <Download />
                  </el-icon>
                  下载
                </el-button>
              </div>
            </el-tooltip>
            <el-button
              type="danger"
              size="small"
              plain
              class="action-button"
              @click.stop="confirmDelete(scope.row)"
            >
              删除
            </el-button>
          </div>
          </template>
        </el-table-column>
    </el-table>

    <!-- Pagination -->
    <div class="pagination-container">
      <el-pagination
        v-model:current-page="pagination.currentPage"
        v-model:page-size="pagination.pageSize"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        :total="filteredTasks.length"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </div>

    <div class="log-strip">
      <div class="log-header">后端日志（最近）</div>
      <div class="log-body">
        <div v-for="log in logs" :key="log.id" class="log-item">
          <span class="log-time">{{ formatTime(log.created_at) }}</span>
          <span class="log-level">{{ log.level }}</span>
          <span class="log-task">#{{ log.task_id }}</span>
          <span class="log-message">{{ log.message }}</span>
        </div>
        <div v-if="!logs.length" class="log-empty">暂无日志</div>
      </div>
    </div>
    
    <!-- Task Details Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="`任务详情 - ${selectedTask?.name || ''}`"
      width="65%"
      center
      class="task-detail-dialog"
      :close-on-click-modal="true"
      :close-on-press-escape="true"
      @close="closeDialog"
    >
      <div v-if="selectedTask" class="task-details">
        <!-- Task Basic Info -->
        <el-descriptions title="基本信息" :column="3" border>
          <el-descriptions-item label="任务ID">{{ selectedTask.id }}</el-descriptions-item>
          <el-descriptions-item label="名称">
            <el-tooltip :content="selectedTask.name">
              <span class="name-ellipsis">{{ selectedTask.name }}</span>
            </el-tooltip>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusTagType(selectedTask.status)" effect="plain">
              {{ getStatusLabel(selectedTask.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="当前阶段">
            <el-tag :type="getStageTagType(selectedTask.stage)" effect="plain">
              {{ getStageLabel(selectedTask.stage) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="进度" :span="2">
            <task-progress-cell
              :overall-percent="selectedTask.progress_detail?.overall_percent ?? selectedTask.progress"
              :stage-index="selectedTask.progress_detail?.stage_index || 1"
              :stage-total="selectedTask.progress_detail?.stage_total || 4"
              :stage-percent="selectedTask.progress_detail?.stage_percent || selectedTask.progress"
              :stage-name="selectedTask.progress_detail?.stage_name || getStageLabel(selectedTask.stage)"
              :step-hint="selectedTask.progress_detail?.step_hint"
            />
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatTime(selectedTask.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="更新时间" :span="2">{{ formatTime(selectedTask.updated_at) }}</el-descriptions-item>
        </el-descriptions>
        
        <el-divider />
        
        <!-- Task Processing Models -->
        <el-descriptions title="模型配置" :column="2" border>
          <el-descriptions-item label="焦点检测模型">{{ selectedTask.focus_model }}</el-descriptions-item>
          <el-descriptions-item label="打标模型">{{ selectedTask.tag_model }}</el-descriptions-item>
        </el-descriptions>
        
        <el-divider />
        
        <!-- Task Stats -->
        <el-descriptions title="统计信息" :column="2" border>
          <el-descriptions-item label="总文件数">{{ selectedTask.stats?.total_files || derivedStats.total }}</el-descriptions-item>
          <el-descriptions-item label="图像文件数">{{ selectedTask.stats?.image_files || derivedStats.total }}</el-descriptions-item>
          <el-descriptions-item label="去重后保留">{{ selectedTask.stats?.kept_files || derivedStats.kept }}</el-descriptions-item>
          <el-descriptions-item label="最终处理数">{{ selectedTask.stats?.processed_files || derivedStats.processed }}</el-descriptions-item>
        </el-descriptions>
        
        <el-divider />
        
        <!-- Task Actions -->
        <div class="task-actions">
          <h4>任务操作</h4>
          <div class="dedup-config">
            <div class="dedup-config-title">去重参数（更严格仅保留最优）</div>
            <div class="dedup-config-grid">
              <div class="config-field">
                <div class="label">人脸相似阈值1</div>
                <el-input-number v-model="dedupConfig.face_sim_th1" :step="0.01" :min="0" :max="1" />
                <div class="hint">越低越容易判为重复（默认0.70）</div>
              </div>
              <div class="config-field">
                <div class="label">人脸相似阈值2</div>
                <el-input-number v-model="dedupConfig.face_sim_th2" :step="0.01" :min="0" :max="1" />
                <div class="hint">次级阈值，默认0.80</div>
              </div>
              <div class="config-field">
                <div class="label">姿态相似阈值</div>
                <el-input-number v-model="dedupConfig.pose_sim_th" :step="0.01" :min="0" :max="1" />
                <div class="hint">越低越严格（默认0.95）</div>
              </div>
              <div class="config-field">
                <div class="label">每簇保留数量</div>
                <el-input-number v-model="dedupConfig.keep_per_cluster" :min="1" :max="5" />
                <div class="hint">设为1只保留每簇最清晰一张</div>
              </div>
            </div>
          </div>
          <div class="task-actions-buttons">
            <el-tooltip :content="dedupDisableReason" :disabled="!disableDedup">
              <div>
                <el-button size="small" @click="startDedup(selectedTask)" :disabled="disableDedup">去重</el-button>
              </div>
            </el-tooltip>
            <el-tooltip :content="cropDisableReason" :disabled="!disableCrop">
              <div>
                <el-button size="small" @click="startCrop(selectedTask)" :disabled="disableCrop">裁切</el-button>
              </div>
            </el-tooltip>
            <el-tooltip :content="captionDisableReason" :disabled="!disableCaption">
              <div>
                <el-button size="small" @click="startCaption(selectedTask)" :disabled="disableCaption">提示词</el-button>
              </div>
            </el-tooltip>
            <el-tooltip :content="runAllDisableReason" :disabled="!disableRunAll">
              <div>
                <el-button size="small" type="primary" plain @click="startRunAll(selectedTask)" :disabled="disableRunAll">一键</el-button>
              </div>
            </el-tooltip>
          </div>
        </div>
        
        <el-divider />
        
        <!-- Task Images Preview -->
        <div class="task-images">
          <div class="task-tabs-header">
            <h4>结果列表</h4>
            <el-button size="small" type="primary" @click="loadTaskImages" :loading="loadingImages">
              刷新列表
            </el-button>
          </div>
          <el-tabs v-model="activeResultTab">
            <el-tab-pane label="去重结果" name="dedup">
              <div class="tab-actions">
                <el-button size="small" @click="bulkKeep(dedupImages, true)">全选保留</el-button>
                <el-button size="small" @click="bulkKeep(dedupImages, false)">全选丢弃</el-button>
                <el-button size="small" @click="keepBySubject(dedupImages, 0.3)">仅保留占比>=30%</el-button>
              </div>
              <div class="result-grid">
                <div
                  v-for="image in dedupImages"
                  :key="image.id"
                  class="result-card"
                  :class="{ discard: !image.selected }"
                >
                  <div class="card-row">
                    <div class="thumb-box">
                      <el-image
                        :src="image.preview_url"
                        :preview-src-list="image.preview_url ? [image.preview_url] : []"
                        :hide-on-click-modal="true"
                        :preview-teleported="true"
                        fit="contain"
                        class="result-thumb"
                      />
                    </div>
                    <div class="result-meta">
                      <div class="meta-title">{{ image.orig_name }}</div>
                      <div class="meta-row">分辨率: {{ image.width && image.height ? `${image.width}x${image.height}` : '-' }}</div>
                      <div class="meta-row">占比: {{ fmtPercent(image.subject_area_ratio) }}</div>
                      <div class="meta-row">人脸: {{ image.has_face ? (image.face_conf?.toFixed?.(2) || '有') : '无' }}</div>
                      <div class="meta-row">可用: {{ image.quality?.usable === false ? '否(' + (image.quality?.reject_reason || '原因未知') + ')' : '是' }}</div>
                    </div>
                  </div>
                  <div class="result-actions bottom">
                    <el-switch
                      :model-value="image.selected"
                      active-text="保留"
                      inactive-text="丢弃"
                      @change="toggleKeep(image)"
                    />
                  </div>
                </div>
              </div>
              <el-empty v-if="!dedupImages.length && !loadingImages" description="暂无去重结果" />
            </el-tab-pane>
            <el-tab-pane label="裁切结果" name="crop">
              <div class="tab-actions">
                <el-button size="small" @click="bulkKeep(cropImages, true)">全选保留</el-button>
                <el-button size="small" @click="bulkKeep(cropImages, false)">全选丢弃</el-button>
              </div>
              <div class="result-grid">
                <div
                  v-for="image in cropImages"
                  :key="image.id"
                  class="result-card"
                  :class="{ discard: !image.selected }"
                >
                  <div class="card-row">
                    <div
                      class="crop-editor"
                      @mousedown.prevent.stop="onCropDragStart($event, image)"
                      @click="onCropClick($event, image)"
                    >
                      <el-image
                        :src="image.preview_url"
                        fit="contain"
                        :preview-src-list="image.preview_url ? [image.preview_url] : []"
                        :hide-on-click-modal="true"
                        :preview-teleported="true"
                        class="crop-base"
                      />
                      <div
                        class="crop-box"
                        :style="cropBoxStyle(image)"
                      ></div>
                    </div>
                    <div class="result-meta">
                      <div class="meta-title">{{ image.orig_name }}</div>
                      <div class="meta-row">分辨率: {{ image.width && image.height ? `${image.width}x${image.height}` : '-' }}</div>
                      <div class="meta-row">主体占比: {{ fmtPercent(image.subject_area_ratio) }}</div>
                      <div class="meta-row">置信度: {{ image.confidence?.toFixed?.(2) || '-' }}</div>
                      <div class="meta-row">类型: {{ image.shot_type || '未知' }}</div>
                      <div class="meta-row">可用: {{ image.quality?.usable === false ? '否(' + (image.quality?.reject_reason || '原因未知') + ')' : '是' }}</div>
                    </div>
                  </div>
                  <div class="result-actions bottom spaced">
                    <el-switch
                      :model-value="image.selected"
                      active-text="保留"
                      inactive-text="丢弃"
                      @change="toggleKeep(image)"
                    />
                  </div>
                </div>
              </div>
              <el-empty v-if="!cropImages.length && !loadingImages" description="暂无裁切结果" />
            </el-tab-pane>
            <el-tab-pane label="提示词" name="prompt">
              <div class="result-grid">
                <div
                  v-for="image in promptImages"
                  :key="image.id"
                  class="result-card prompt-card"
                >
                  <div class="card-row">
                    <div class="thumb-box">
                      <el-image
                        :src="image.crop_url || image.preview_url"
                        fit="contain"
                        :preview-src-list="(image.crop_url || image.preview_url) ? [image.crop_url || image.preview_url] : []"
                        :hide-on-click-modal="true"
                        :preview-teleported="true"
                        style="width: 100%; height: 100%;"
                        class="result-thumb"
                      />
                    </div>
                    <div class="result-meta">
                      <div class="meta-title">{{ image.orig_name }}</div>
                      <div class="meta-row">分辨率: {{ image.width && image.height ? `${image.width}x${image.height}` : '-' }}</div>
                      <div class="prompt-text">{{ image.prompt_text || '尚未生成' }}</div>
                    </div>
                  </div>
                </div>
              </div>
              <el-empty v-if="!promptImages.length && !loadingImages" description="暂无提示词" />
            </el-tab-pane>
          </el-tabs>
        </div>

      </div>
      
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  Refresh, 
  Download 
} from '@element-plus/icons-vue'
import type { Task, TaskImage } from '../types/task'
import {
  getTasks, 
  getTask,
  getTaskImages, 
  downloadTask as apiDownloadTask, 
  deleteTask,
  deleteAllTasks,
  getLogs,
  getProcessingSettings,
  createEventSource,
  triggerDedup,
  triggerCrop,
  triggerCaption,
  triggerRunAll,
  updateImageSelection,
  updateDecision,
  updateCropSquare
} from '../services/api'
import TaskProgressCell from '../components/TaskProgressCell.vue'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const loadFailCount = ref(0)
const tasks = ref<Task[]>([])
const selectedTask = ref<Task | null>(null)
const dialogVisible = ref(false)
const taskImages = ref<TaskImage[]>([])
const loadingImages = ref(false)
const logs = ref<{ id: number; task_id: number; level: string; message: string; created_at: string }[]>([])
const logsTimer = ref<number | null>(null)
const refreshTimer = ref<number | null>(null)
const openingTaskId = ref<number | null>(null)
const activeResultTab = ref('dedup')
const editingCropId = ref<number | null>(null)
const cropDraft = ref<Record<number, { cx: number; cy: number; side: number }>>({})
const savingCrop = ref(false)
const dedupConfig = ref({
  face_sim_th1: 0.8,
  face_sim_th2: 0.85,
  pose_sim_th: 0.98,
  face_ssim_th1: 0.95,
  face_ssim_th2: 0.9,
  bbox_tol_c: 0.04,
  bbox_tol_wh: 0.06,
  keep_per_cluster: 2
})

// Filter
const filter = ref({
  text: '',
  status: undefined as string | undefined,
  stage: undefined as string | undefined
})

// Pagination
const pagination = ref({
  currentPage: 1,
  pageSize: 10
})

// Event sources for real-time updates
const eventSources = ref<Map<number, EventSource>>(new Map())

// Status and stage options
const statusOptions = [
  { label: '上传中', value: 'uploading' },
  { label: '等待中', value: 'pending' },
  { label: '处理中', value: 'processing' },
  { label: '已完成', value: 'completed' },
  { label: '错误', value: 'error' }
]

const stageOptions = [
  { label: '待启动', value: 'initial' },
  { label: '解压', value: 'unpacking' },
  { label: '去重', value: 'de_duplication' },
  { label: '预览就绪', value: 'preview_generation' },
  { label: '焦点检测', value: 'focus_detection' },
  { label: '裁切', value: 'cropping' },
  { label: '提示词', value: 'tagging' },
  { label: '打包', value: 'packaging' },
  { label: '完成', value: 'finished' }
]

// Load tasks
const mergeTasks = (incoming: Task[]) => {
  const map = new Map<number, Task>()
  tasks.value.forEach(t => map.set(t.id, t))
  incoming.forEach(t => map.set(t.id, { ...map.get(t.id), ...t }))
  tasks.value = Array.from(map.values()).sort((a, b) => b.id - a.id)
}

const loadTasks = async (silent = false) => {
  if (!silent) loading.value = true
  try {
    const fresh = await getTasks()
    mergeTasks(fresh)
    loadFailCount.value = 0
    // Subscribe to real-time updates for processing tasks
    setupEventSources()
    syncRouteTask()
  } catch (error) {
    console.error('Failed to load tasks:', error)
    loadFailCount.value += 1
    if (!silent) ElMessage.error('加载任务失败')
    if (loadFailCount.value >= 3 && refreshTimer.value) {
      clearInterval(refreshTimer.value)
      refreshTimer.value = null
      ElMessage.warning('连续加载失败，已暂停自动刷新，请检查后端或手动刷新')
    }
  } finally {
    if (!silent) loading.value = false
  }
}

// Setup SSE event sources for processing tasks
const setupEventSources = () => {
  // Close existing event sources
  eventSources.value.forEach((es, taskId) => {
    es.close()
    eventSources.value.delete(taskId)
  })
  
  // Subscribe to processing tasks
  const processingTasks = tasks.value.filter(t => t.status === 'processing')
  processingTasks.forEach(task => {
    const es = createEventSource(task.id, (data) => {
      // Update task in list
      const index = tasks.value.findIndex(t => t.id === task.id)
      if (index !== -1) {
        tasks.value[index] = { ...tasks.value[index], ...data }
        
        // Update selected task if it's the same
        if (selectedTask.value?.id === task.id) {
          selectedTask.value = { ...selectedTask.value, ...data }
        }
      }
      
      // Close event source if task is completed or error
      if (data.status === 'completed' || data.status === 'error') {
        const es = eventSources.value.get(task.id)
        if (es) {
          es.close()
          eventSources.value.delete(task.id)
        }
        loadTasks(true)
        if (selectedTask.value?.id === task.id) {
          loadTaskImages()
        }
      }
    })
    eventSources.value.set(task.id, es)
  })
}

// Filter tasks
const filteredTasks = computed(() => {
  return tasks.value.filter(task => {
    // Text filter
    const matchesText = !filter.value.text || task.name.includes(filter.value.text)
    // Status filter
    const matchesStatus = !filter.value.status || task.status === filter.value.status
    // Stage filter
    const matchesStage = !filter.value.stage || task.stage === filter.value.stage
    
    return matchesText && matchesStatus && matchesStage
  })
})

const dedupImages = computed(() => taskImages.value)
const cropImages = computed(() => taskImages.value.filter(img => img.crop_url || img.crop_path))
const promptImages = computed(() => taskImages.value.filter(img => img.has_prompt || img.prompt_text))

// Format time
const formatTime = (timeStr: string) => {
  const date = new Date(timeStr)
  return date.toLocaleString()
}

const loadLogs = async () => {
  try {
    logs.value = await getLogs(120)
  } catch (error) {
    console.error('加载日志失败', error)
  }
}

// Get status label
const getStatusLabel = (status: string) => {
  const option = statusOptions.find(opt => opt.value === status)
  return option ? option.label : status
}

// Get stage label
const getStageLabel = (stage: string) => {
  const option = stageOptions.find(opt => opt.value === stage)
  return option ? option.label : stage
}

// Get status tag type
const getStatusTagType = (status: string) => {
  switch (status) {
    case 'completed':
      return 'success'
    case 'error':
      return 'danger'
    case 'processing':
    case 'uploading':
      return 'primary'
    case 'pending':
      return 'warning'
    default:
      return 'info'
  }
}

// Get stage tag type
const getStageTagType = (stage: string) => {
  switch (stage) {
    case 'finished':
      return 'success'
    case 'packaging':
      return 'info'
    case 'tagging':
      return 'warning'
    case 'cropping':
      return 'primary'
    case 'focus_detection':
      return 'success'
    case 'preview_generation':
      return 'info'
    case 'de_duplication':
      return 'warning'
    case 'unpacking':
      return 'primary'
    default:
      return 'info'
  }
}



// Handle row click
const handleRowClick = (row: Task) => {
  viewTaskDetails(row, true)
}

// View task details
const viewTaskDetails = (row: Task, syncRoute = false) => {
  if (syncRoute) {
    router.replace({ path: '/tasks', query: { taskId: row.id } })
  }
  selectedTask.value = row
  dialogVisible.value = true
  loadTaskImages()
}

const openTaskById = async (taskId: number) => {
  if (dialogVisible.value && selectedTask.value?.id === taskId) return
  openingTaskId.value = taskId
  let task = tasks.value.find(t => t.id === taskId)
  if (!task) {
    try {
      task = await getTask(taskId)
      if (task) {
        mergeTasks([task])
      }
    } catch (error) {
      task = undefined
    }
  }
  if (task) {
    viewTaskDetails(task)
  }
  openingTaskId.value = null
}

const closeDialog = () => {
  dialogVisible.value = false
  selectedTask.value = null
  router.replace({ path: '/tasks', query: {} })
}

const syncRouteTask = () => {
  const qid = route.query.taskId ? Number(route.query.taskId) : null
  if (!qid) {
    dialogVisible.value = false
    selectedTask.value = null
    return
  }
  if (!openingTaskId.value) {
    openTaskById(qid)
  }
}



const isDownloadDisabled = (task: Task) => {
  return task.status !== 'completed' || !task.export_ready
}

const downloadDisableReason = (task: Task) => {
  if (task.status !== 'completed') return '任务未完成，暂不可下载'
  if (!task.export_ready) return '尚未生成导出包'
  return ''
}

const getTaskTotalCount = (task: Task) => {
  return task.stats?.image_files ?? task.stats?.total_files ?? '-'
}

const getTaskProcessedCount = (task: Task) => {
  const processed = task.stats?.processed_files
  if (processed !== undefined && processed !== null && processed > 0) {
    return processed
  }
  const kept = task.stats?.kept_files
  if (kept !== undefined && kept !== null) {
    return kept
  }
  return task.stats?.image_files ?? task.stats?.total_files ?? '-'
}



// Load task images
const loadTaskImages = async () => {
  if (!selectedTask.value) return
  
  loadingImages.value = true
  try {
    taskImages.value = await getTaskImages(selectedTask.value.id)
    // refresh derived stats into selected task snapshot
    if (selectedTask.value) {
      selectedTask.value.stats = {
        ...(selectedTask.value.stats || {}),
        total_files: taskImages.value.length,
        image_files: taskImages.value.length,
        kept_files: taskImages.value.filter(i => i.selected).length,
        processed_files: taskImages.value.filter(i => i.crop_url && i.selected).length
      }
    }
  } catch (error) {
    console.error('Failed to load task images:', error)
    ElMessage.error('加载预览图失败')
  } finally {
    loadingImages.value = false
  }
}

const fmtPercent = (v?: number) => {
  if (v === undefined || v === null || Number.isNaN(v)) return '-'
  return `${Math.round(v * 100)}%`
}

const derivedStats = computed(() => {
  const total = taskImages.value.length
  const kept = taskImages.value.filter(i => i.selected).length
  const processed = taskImages.value.filter(i => i.crop_url && i.selected).length
  return { total, kept, processed }
})

const toggleKeep = async (image: TaskImage) => {
  if (!selectedTask.value) return
  try {
    await updateDecision(selectedTask.value.id, image.id, !image.selected)
    image.selected = !image.selected
    if (selectedTask.value.stats) {
      selectedTask.value.stats.kept_files = taskImages.value.filter(i => i.selected).length
      selectedTask.value.stats.processed_files = taskImages.value.filter(i => i.selected && i.crop_url).length
    }
  } catch (error) {
    ElMessage.error('更新失败')
  }
}

const bulkKeep = async (images: TaskImage[], keep: boolean) => {
  if (!selectedTask.value || !images.length) return
  try {
    await updateImageSelection(selectedTask.value.id, images.map(i => i.id), keep)
    images.forEach(i => (i.selected = keep))
    if (selectedTask.value.stats) {
      selectedTask.value.stats.kept_files = taskImages.value.filter(i => i.selected).length
      selectedTask.value.stats.processed_files = taskImages.value.filter(i => i.selected && i.crop_url).length
    }
  } catch (error) {
    ElMessage.error('批量更新失败')
  }
}

const keepBySubject = async (images: TaskImage[], threshold: number) => {
  const filtered = images.filter(i => (i.subject_area_ratio || 0) >= threshold)
  await bulkKeep(images, false)
  if (filtered.length) {
    await bulkKeep(filtered, true)
  }
}

const getCropSquare = (image: TaskImage) => {
  const square =
    image.crop_square_user ||
    image.crop_square_model ||
    (image.meta_json || {}).crop_square_user ||
    (image.meta_json || {}).crop_square_model
  return {
    cx: Number(square?.cx ?? 0.5),
    cy: Number(square?.cy ?? 0.5),
    side: Number(square?.side ?? 1.0)
  }
}

// 根据原图宽高限制裁切中心，保证方框能贴边
const clampCrop = (image: TaskImage, draft: { cx: number; cy: number; side: number }) => {
  const width = Number(image.width) || 1
  const height = Number(image.height) || 1
  const minDim = Math.min(width, height)
  const halfW = (draft.side * minDim) / (2 * width)
  const halfH = (draft.side * minDim) / (2 * height)
  return {
    cx: Math.max(halfW, Math.min(1 - halfW, draft.cx)),
    cy: Math.max(halfH, Math.min(1 - halfH, draft.cy)),
    side: draft.side
  }
}

const cropBoxStyle = (image: TaskImage) => {
  const draft = clampCrop(image, cropDraft.value[image.id] || getCropSquare(image))
  const side = Math.max(0.05, Math.min(1, Number(draft.side) || 1))
  const width = Number(image.width) || 1
  const height = Number(image.height) || 1
  const minDim = Math.min(width, height)
  const maxDim = Math.max(width, height)
  const cx = draft.cx
  const cy = draft.cy

  // 显示容器 1x1，图片等比缩放后有 letterbox，需要加偏移
  const displayW = width / maxDim
  const displayH = height / maxDim
  const offsetX = (1 - displayW) / 2
  const offsetY = (1 - displayH) / 2

  const boxSizeNorm = (side * minDim) / maxDim
  const leftNorm = (cx * width - (side * minDim) / 2) / maxDim + offsetX
  const topNorm = (cy * height - (side * minDim) / 2) / maxDim + offsetY

  const leftPct = Math.max(0, Math.min(1 - boxSizeNorm, leftNorm)) * 100
  const topPct = Math.max(0, Math.min(1 - boxSizeNorm, topNorm)) * 100
  const boxPct = Math.min(1, boxSizeNorm) * 100

  return {
    width: `${boxPct}%`,
    height: `${boxPct}%`,
    left: `${leftPct}%`,
    top: `${topPct}%`
  }
}

const ensureCropDraft = (image: TaskImage) => {
  if (!cropDraft.value[image.id]) {
    cropDraft.value[image.id] = { ...getCropSquare(image) }
  }
}

const pointToCrop = (event: MouseEvent, image: TaskImage, rectOverride?: DOMRect) => {
  const target = (event.currentTarget as HTMLElement) || null
  const rect = rectOverride || target?.getBoundingClientRect()
  if (!rect) return { cx: 0.5, cy: 0.5 }
  const relX = (event.clientX - rect.left) / rect.width
  const relY = (event.clientY - rect.top) / rect.height
  const width = Number(image.width) || 1
  const height = Number(image.height) || 1
  const maxDim = Math.max(width, height)
  const dispW = width / maxDim
  const dispH = height / maxDim
  const offsetX = (1 - dispW) / 2
  const offsetY = (1 - dispH) / 2
  const cx = Math.max(0, Math.min(1, (relX - offsetX) / dispW))
  const cy = Math.max(0, Math.min(1, (relY - offsetY) / dispH))
  return { cx, cy }
}

const onCropClick = async (event: MouseEvent, image: TaskImage) => {
  editingCropId.value = image.id
  ensureCropDraft(image)
  const { cx, cy } = pointToCrop(event, image)
  const current = cropDraft.value[image.id] || getCropSquare(image)
  cropDraft.value[image.id] = clampCrop(image, { ...current, cx, cy })
  await saveCropEdit(image)
}

let dragMoveHandler: ((e: MouseEvent) => void) | null = null
let dragStopHandler: ((e: MouseEvent) => void) | null = null
let draggingImageId: number | null = null

const onCropDragStart = (event: MouseEvent, image: TaskImage) => {
  event.preventDefault()
  editingCropId.value = image.id
  ensureCropDraft(image)
  draggingImageId = image.id
  const baseRect = (event.currentTarget as HTMLElement)?.getBoundingClientRect()

  const move = (e: MouseEvent) => {
    const img = taskImages.value.find(it => it.id === draggingImageId)
    if (!img) return
    const { cx, cy } = pointToCrop(e, img, baseRect || undefined)
    const current = cropDraft.value[img.id] || getCropSquare(img)
    cropDraft.value[img.id] = clampCrop(img, { ...current, cx, cy })
  }

  const stop = async () => {
    draggingImageId = null
    if (dragMoveHandler) window.removeEventListener('mousemove', dragMoveHandler)
    if (dragStopHandler) window.removeEventListener('mouseup', dragStopHandler)
    dragMoveHandler = null
    dragStopHandler = null
    if (editingCropId.value) {
      const img = taskImages.value.find(it => it.id === editingCropId.value)
      if (img) {
        await saveCropEdit(img)
      }
    }
  }

  dragMoveHandler = move
  dragStopHandler = stop
  window.addEventListener('mousemove', move)
  window.addEventListener('mouseup', stop)
}

const bulkRun = async (action: 'dedup' | 'crop' | 'caption' | 'export') => {
  const confirmMsg = {
    dedup: '将对所有任务重新去重，可能耗时，继续？',
    crop: '将对所有任务重新裁切，继续？',
    caption: '将对所有任务生成提示词，继续？',
    export: '将对所有任务重新打包导出，继续？'
  }[action]
  try {
    await ElMessageBox.confirm(confirmMsg, '确认', { type: 'warning' })
  } catch {
    return
  }
  loading.value = true
  try {
    const runners: Promise<any>[] = []
    tasks.value.forEach(t => {
      if (action === 'dedup') runners.push(triggerDedup(t.id, dedupConfig.value))
      if (action === 'crop') runners.push(triggerCrop(t.id))
      if (action === 'caption') runners.push(triggerCaption(t.id))
      if (action === 'export') runners.push(triggerRunAll(t.id))
    })
    await Promise.allSettled(runners)
    ElMessage.success('已触发全量操作')
  } catch (e) {
    ElMessage.error('触发失败')
  } finally {
    loading.value = false
  }
}

const saveCropEdit = async (image: TaskImage) => {
  if (!selectedTask.value) return
  const draft = clampCrop(image, cropDraft.value[image.id] || getCropSquare(image))
  savingCrop.value = true
  try {
    await updateCropSquare(selectedTask.value.id, image.id, draft)
    await loadTaskImages()
    editingCropId.value = null
    ElMessage.success('裁切已保存')
  } catch (error) {
    ElMessage.error('保存裁切失败')
  } finally {
    savingCrop.value = false
  }
}

// Download task result
const downloadTask = async (taskId?: number) => {
  if (!taskId) return
  
  try {
    await apiDownloadTask(taskId)
  } catch (error) {
    console.error('Failed to download task:', error)
    ElMessage.error('下载失败')
  }
}

// Task operation functions
const startDedup = async (task: Task) => {
  if (!task || task.status === 'processing') return
  try {
    await triggerDedup(task.id, dedupConfig.value)
    ElMessage.success('已启动去重')
    loadTasks()
  } catch (error) {
    ElMessage.error('启动失败')
  }
}

const startCrop = async (task: Task) => {
  if (!task || task.status === 'processing') return
  try {
    await triggerCrop(task.id)
    ElMessage.success('已启动裁切')
    loadTasks()
  } catch (error) {
    ElMessage.error('启动失败')
  }
}

const startCaption = async (task: Task) => {
  if (!task || task.status === 'processing') return
  try {
    await triggerCaption(task.id)
    ElMessage.success('已启动提示词生成')
    loadTasks()
  } catch (error) {
    ElMessage.error('启动失败')
  }
}

const confirmDelete = async (task: Task) => {
  try {
    await ElMessageBox.confirm(
      `删除任务「${task.name}」后将移除数据库记录并清空本地文件，确认继续？`,
      '确认删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
  } catch {
    return
  }
  try {
    await deleteTask(task.id)
    ElMessage.success('已删除任务')
    if (selectedTask.value?.id === task.id) {
      dialogVisible.value = false
      selectedTask.value = null
    }
    await loadTasks(true)
    tasks.value = tasks.value.filter(t => t.id !== task.id)
  } catch (error) {
    if ((error as any)?.response?.status === 404) {
      ElMessage.warning('后端不存在此任务，已在前端移除')
      tasks.value = tasks.value.filter(t => t.id !== task.id)
    } else {
      ElMessage.error('删除失败')
    }
  }
}

const confirmDeleteAll = async () => {
  try {
    await ElMessageBox.confirm(
      '将删除所有任务、数据库记录和本地文件，确认继续？',
      '清空所有任务',
      { type: 'warning' }
    )
  } catch {
    return
  }
  loading.value = true
  try {
    await deleteAllTasks()
    tasks.value = []
    selectedTask.value = null
    dialogVisible.value = false
    ElMessage.success('已清空所有任务')
  } catch (error) {
    ElMessage.error('清空失败')
  } finally {
    loading.value = false
  }
}

const startRunAll = async (task: Task) => {
  if (!task || task.status === 'processing') return
  try {
    await triggerRunAll(task.id)
    ElMessage.success('一键流程已启动')
    loadTasks()
  } catch (error) {
    ElMessage.error('启动失败')
  }
}

// Refresh tasks
const refreshTasks = () => {
  loadTasks(true)
}

// Watch for task count changes to update event sources
watch(() => tasks.value.length, () => {
  setupEventSources()
})

const disableDedup = computed(() => {
  if (!selectedTask.value) return true
  return selectedTask.value.status === 'processing'
})
const dedupDisableReason = computed(() => {
  if (!selectedTask.value) return '未选择任务'
  if (selectedTask.value.status === 'processing') return '任务执行中'
  return ''
})

const disableCrop = computed(() => {
  if (!selectedTask.value) return true
  return selectedTask.value.status === 'processing'
})
const cropDisableReason = computed(() => {
  if (!selectedTask.value) return '未选择任务'
  if (selectedTask.value.status === 'processing') return '任务执行中'
  return ''
})

const disableCaption = computed(() => {
  if (!selectedTask.value) return true
  return selectedTask.value.status === 'processing'
})
const captionDisableReason = computed(() => {
  if (!selectedTask.value) return '未选择任务'
  if (selectedTask.value.status === 'processing') return '任务执行中'
  return ''
})

const disableRunAll = computed(() => {
  if (!selectedTask.value) return true
  return selectedTask.value.status === 'processing'
})
const runAllDisableReason = computed(() => {
  if (!selectedTask.value) return '未选择任务'
  if (selectedTask.value.status === 'processing') return '任务执行中'
  return ''
})

// Watch for route changes to show task details
watch(
  () => route.query.taskId,
  async (newTaskId, _oldTaskId) => {
    if (!newTaskId) {
      dialogVisible.value = false
      selectedTask.value = null
      return
    }

  const taskId = Number(newTaskId)
  let task = tasks.value.find(t => t.id === taskId)
  let loadOk = true

  // If task not found in current list, load tasks again
  if (!task || tasks.value.length === 0) {
    try {
      await loadTasks()
      task = tasks.value.find(t => t.id === taskId)
    } catch (e) {
      loadOk = false
    }
  }
  
  if (task) {
    viewTaskDetails(task)
  } else if (loadOk) {
    await openTaskById(taskId)
    if (!selectedTask.value) {
      // Only remove route if backend is reachable
      router.replace({
        path: '/tasks',
        query: {}
      })
      ElMessage.warning('任务不存在或已删除')
    }
  }
},
  { immediate: true }
)

// Watch for dialog visibility to manage refresh timer
watch(() => dialogVisible.value, (isVisible) => {
  if (!isVisible && route.query.taskId) {
    router.replace({
      path: '/tasks',
      query: {}
    })
  }
  if (!refreshTimer.value) {
    refreshTimer.value = window.setInterval(() => loadTasks(true), 5000)
  }
})

// Pagination handlers
const handleSizeChange = (size: number) => {
  pagination.value.pageSize = size
  pagination.value.currentPage = 1
}

const handleCurrentChange = (current: number) => {
  pagination.value.currentPage = current
}

const loadDedupSettings = async () => {
  try {
    const settings = await getProcessingSettings()
    if (settings?.dedup_params) {
      dedupConfig.value = { ...dedupConfig.value, ...settings.dedup_params }
    }
  } catch (error) {
    console.warn('加载去重参数失败', error)
  }
}

// Lifecycle hooks
onMounted(() => {
  loadTasks()
  loadLogs()
  loadDedupSettings()
  // Only set up refresh timer if no taskId is in URL initially
  if (!route.query.taskId) {
    refreshTimer.value = window.setInterval(() => loadTasks(true), 3000)
  }
  logsTimer.value = window.setInterval(loadLogs, 4000)
})

onBeforeUnmount(() => {
  // Close all event sources
  eventSources.value.forEach((es) => {
    es.close()
  })
  eventSources.value.clear()
  if (refreshTimer.value) {
    clearInterval(refreshTimer.value)
  }
   if (logsTimer.value) {
    clearInterval(logsTimer.value)
  }
})
</script>

<style scoped>
.task-list-container {
  width: 100%;
  height: 100%;
}

.page-header {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.header-actions .el-button {
  height: 36px;
  line-height: 34px;
}

.task-filter {
  display: flex;
  align-items: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 10px;
}

.pagination-container {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}

.task-details {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.task-actions {
  margin-top: 20px;
}

.task-actions h4 {
  margin-bottom: 10px;
}

.task-actions-buttons {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.dedup-config {
  margin-bottom: 12px;
  padding: 10px;
  border: 1px solid var(--border, #ebeef5);
  border-radius: 8px;
  background: var(--panel, #f7f9fb);
}

.dedup-config-title {
  font-weight: 600;
  margin-bottom: 8px;
}

.dedup-config-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 10px;
}

.config-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.config-field .label {
  font-size: 13px;
  color: var(--text, #303133);
}

.config-field .hint {
  font-size: 12px;
  color: var(--muted, #909399);
}

.task-actions-buttons .el-button {
  font-size: 14px !important;
  padding: 0 16px !important;
  height: 36px;
  line-height: 34px;
  min-width: 100px;
}

.table-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: center;
  width: 100%;
}

.task-images {
  margin-top: 20px;
}

.task-tabs-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.tab-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.dialog-footer {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.footer-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.footer-actions .el-button {
  height: 36px;
  min-width: 96px;
}

.footer-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.table-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.action-button {
  min-width: 104px;
  height: 32px;
}

.name-ellipsis {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.log-strip {
  margin: 16px 0;
  padding: 12px 16px;
  background: var(--panel, #f5f7fa);
  border: 1px solid var(--border, #ebeef5);
  border-radius: 10px;
}

.log-header {
  font-weight: 600;
  margin-bottom: 8px;
}

.log-body {
  max-height: 220px;
  overflow-y: auto;
  font-size: 12px;
  line-height: 18px;
}

.log-item {
  display: grid;
  grid-template-columns: 140px 60px 60px 1fr;
  gap: 8px;
  padding: 4px 0;
  border-bottom: 1px dashed var(--border, #ebeef5);
}

.log-item:last-child {
  border-bottom: none;
}

.log-time {
  color: var(--muted, #909399);
}

.log-level {
  text-transform: uppercase;
  color: #f56c6c;
  font-weight: 600;
}

.log-task {
  color: var(--text, #303133);
}

.log-message {
  color: var(--text, #303133);
}

.log-empty {
  color: var(--muted, #909399);
}

.result-card.discard {
  opacity: 0.55;
  border-color: #f56c6c;
  background: rgba(245, 108, 108, 0.08);
}

.result-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 12px;
}

.result-card {
  background: var(--panel, #f5f7fa);
  border: 1px solid var(--border, #ebeef5);
  border-radius: 12px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.card-row {
  display: grid;
  grid-template-columns: 200px minmax(0, 1fr);
  gap: 12px;
  align-items: start;
}

:deep(.task-detail-dialog) {
  width: 65%;
  max-width: 65%;
  margin: 0 auto;
}

@media (max-width: 1200px) {
  :deep(.task-detail-dialog) {
    width: 92%;
    max-width: 92%;
  }
}

.thumb-box {
  width: 200px;
  height: 200px;
  flex: 0 0 200px;
  min-width: 200px;
  min-height: 200px;
  border-radius: 10px;
  overflow: hidden;
  background: #f1f2f5;
  display: flex;
  align-items: stretch;
  justify-content: stretch;
}

.thumb-box :deep(.el-image),
.thumb-box :deep(.el-image__inner) {
  width: 100% !important;
  height: 100% !important;
  display: block;
  object-fit: contain;
}

.thumb-box :deep(.el-image) {
  flex: 1 1 auto;
  min-width: 100%;
  min-height: 100%;
  display: flex;
}

.result-thumb {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #f1f2f5;
}

.result-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: var(--muted, #909399);
  flex: 1 1 auto;
  min-width: 0;
}

.meta-title {
  font-weight: 600;
  color: var(--text, #303133);
}

.meta-row {
  line-height: 16px;
}

.result-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.result-actions.bottom {
  flex-direction: row;
  justify-content: flex-end;
  align-items: center;
}

.result-actions.bottom.spaced {
  gap: 12px;
}

.crop-editor {
  position: relative;
  width: 200px;
  height: 200px;
  border-radius: 10px;
  overflow: hidden;
  cursor: grab;
  background: #f1f2f5;
  flex-shrink: 0;
}
.crop-editor:active {
  cursor: grabbing;
}

.crop-base {
  width: 100%;
  height: 100%;
  object-fit: contain;
  pointer-events: none;
}
.crop-editor :deep(.el-image),
.crop-editor :deep(.el-image__inner) {
  pointer-events: none;
}


.crop-box {
  position: absolute;
  border: 2px solid #f56c6c;
  box-shadow: 0 0 0 1px rgba(245, 108, 108, 0.4);
  pointer-events: none;
}

.prompt-card .prompt-text {
  font-size: 12px;
  color: var(--text, #303133);
  background: var(--surface, rgba(255, 255, 255, 0.6));
  border-radius: 8px;
  padding: 8px;
  line-height: 1.4;
  max-height: 140px;
  overflow: auto;
}

@media (max-width: 1279px) {
  .table-actions {
    flex-direction: row;
    flex-wrap: wrap;
  }
}
</style>
