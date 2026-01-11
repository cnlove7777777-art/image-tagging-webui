<template>
  <el-card shadow="hover">
    <template #header>
      <div class="card-header">
        <span>上传队列</span>
        <el-button 
          type="danger" 
          size="small" 
          :disabled="uploadingFiles.length === 0"
          @click="clearQueue"
        >
          清空队列
        </el-button>
      </div>
    </template>
    
    <div v-if="uploadingFiles.length === 0" class="empty-queue">
      <el-empty description="暂无上传任务" />
    </div>
    
    <el-timeline v-else>
      <el-timeline-item
        v-for="(file, index) in uploadingFiles"
        :key="index"
        :timestamp="formatTime(file.file.lastModified)"
        :type="getFileStatusType(file.status)"
      >
        <div class="timeline-content">
          <div class="file-info">
            <el-icon class="file-icon">
              <Document />
            </el-icon>
            <span class="file-name">{{ file.relativePath || file.file.name }}</span>
            <span class="file-size">({{ formatSize(file.file.size) }})</span>
          </div>
          
          <el-progress
            v-if="file.status === 'uploading'"
            :percentage="file.progress"
            :status="getFileProgressStatus(file.status)"
            :stroke-width="8"
          />
          
          <div v-else-if="file.status === 'success'" class="success-status">
            <el-icon color="#67c23a">
              <CircleCheck />
            </el-icon>
            <span>上传成功</span>
            <el-button 
              type="primary" 
              size="small"
              plain
              @click="viewTask()"
            >
              查看任务
            </el-button>
          </div>
          
          <div v-else-if="file.status === 'error'" class="error-status">
            <el-icon color="#f56c6c">
              <CircleClose />
            </el-icon>
            <span>{{ file.message || '上传失败' }}</span>
            <el-button 
              type="primary" 
              size="small"
              plain
              @click="retryUpload(file)"
            >
              重试
            </el-button>
          </div>
          
          <div v-else class="pending-status">
            <el-icon>
              <Clock />
            </el-icon>
            <span>等待上传</span>
          </div>
        </div>
      </el-timeline-item>
    </el-timeline>
  </el-card>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { 
  Document, 
  CircleCheck, 
  CircleClose, 
  Clock 
} from '@element-plus/icons-vue'
import type { UploadFile } from '../types/upload'

defineProps<{
  uploadingFiles: UploadFile[]
}>()

const emit = defineEmits<{
  (e: 'retry', file: UploadFile): void
  (e: 'clear'): void
}>()

const router = useRouter()

const formatTime = (timestamp: number): string => {
  const date = new Date(timestamp)
  return date.toLocaleString()
}

const formatSize = (bytes: number): string => {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const getFileStatusType = (status: string): string => {
  switch (status) {
    case 'success':
      return 'success'
    case 'error':
      return 'danger'
    case 'uploading':
      return 'primary'
    default:
      return 'info'
  }
}

const getFileProgressStatus = (status: string): string | undefined => {
  switch (status) {
    case 'success':
      return 'success'
    case 'error':
      return 'exception'
    default:
      return undefined
  }
}

const clearQueue = () => {
  emit('clear')
}

const retryUpload = (file: UploadFile) => {
  emit('retry', file)
}

const viewTask = () => {
  router.push('/tasks')
}
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.empty-queue {
  text-align: center;
  padding: 40px 0;
}

.timeline-content {
  padding: 10px 0;
}

.file-info {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

.file-icon {
  margin-right: 8px;
  color: #409eff;
}

.file-name {
  font-weight: 500;
  margin-right: 8px;
}

.file-size {
  color: #909399;
  font-size: 12px;
}

.success-status,
.error-status,
.pending-status {
  display: flex;
  align-items: center;
  margin-top: 8px;
}

.success-status .el-icon,
.error-status .el-icon,
.pending-status .el-icon {
  margin-right: 8px;
  font-size: 16px;
}

.success-status span,
.error-status span,
.pending-status span {
  margin-right: 12px;
}
</style>
