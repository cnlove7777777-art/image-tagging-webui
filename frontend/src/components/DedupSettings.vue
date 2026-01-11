<template>
  <div class="settings-section">
    <el-form :model="dedupSettingsForm" label-width="180px">
      <el-form-item label="人脸特征相似度阈值1">
        <el-input-number
          v-model="dedupSettingsForm.face_sim_th1"
          :min="0"
          :max="1"
          :step="0.01"
          :precision="2"
          placeholder="0.80"
        />
        <div class="form-hint">较宽松的人脸特征相似度阈值，用于结合其他条件判断重复</div>
      </el-form-item>
      
      <el-form-item label="人脸特征相似度阈值2">
        <el-input-number
          v-model="dedupSettingsForm.face_sim_th2"
          :min="0"
          :max="1"
          :step="0.01"
          :precision="2"
          placeholder="0.85"
        />
        <div class="form-hint">严格的人脸特征相似度阈值，达到此值直接判断为重复</div>
      </el-form-item>
      
      <el-form-item label="姿势相似度阈值">
        <el-input-number
          v-model="dedupSettingsForm.pose_sim_th"
          :min="0"
          :max="1"
          :step="0.01"
          :precision="2"
          placeholder="0.98"
        />
        <div class="form-hint">姿势相似度阈值，用于结合人脸特征判断重复</div>
      </el-form-item>
      
      <el-form-item label="人脸结构相似度阈值1">
        <el-input-number
          v-model="dedupSettingsForm.face_ssim_th1"
          :min="0"
          :max="1"
          :step="0.01"
          :precision="2"
          placeholder="0.95"
        />
        <div class="form-hint">较宽松的人脸结构相似度阈值，用于结合其他条件判断重复</div>
      </el-form-item>
      
      <el-form-item label="人脸结构相似度阈值2">
        <el-input-number
          v-model="dedupSettingsForm.face_ssim_th2"
          :min="0"
          :max="1"
          :step="0.01"
          :precision="2"
          placeholder="0.90"
        />
        <div class="form-hint">严格的人脸结构相似度阈值，达到此值结合人脸特征判断为重复</div>
      </el-form-item>
      
      <el-form-item label="边界框中心位置容差">
        <el-input-number
          v-model="dedupSettingsForm.bbox_tol_c"
          :min="0"
          :max="1"
          :step="0.01"
          :precision="2"
          placeholder="0.04"
        />
        <div class="form-hint">边界框中心位置的容差，用于判断两个边界框是否重叠</div>
      </el-form-item>
      
      <el-form-item label="边界框大小容差">
        <el-input-number
          v-model="dedupSettingsForm.bbox_tol_wh"
          :min="0"
          :max="1"
          :step="0.01"
          :precision="2"
          placeholder="0.06"
        />
        <div class="form-hint">边界框大小的容差，用于判断两个边界框大小是否相似</div>
      </el-form-item>
    
      <el-form-item label="??????">
        <el-input-number
          v-model="dedupSettingsForm.keep_per_cluster"
          :min="1"
          :max="5"
          :step="1"
        />
        <div class="form-hint">??1??????????</div>
      </el-form-item>
    </el-form>
    <div class="dialog-footer">
      <el-button :loading="loading" @click="resetDedupSettings">恢复默认</el-button>
      <el-button :loading="loading" type="primary" @click="saveDedupSettings">保存去重设置</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getProcessingSettings, updateProcessingSettings } from '../services/api'

const emit = defineEmits<{
  save: []
}>()

const defaultDedupSettings = {
  face_sim_th1: 0.8,
  face_sim_th2: 0.85,
  pose_sim_th: 0.98,
  face_ssim_th1: 0.95,
  face_ssim_th2: 0.9,
  bbox_tol_c: 0.04,
  bbox_tol_wh: 0.06,
  keep_per_cluster: 2
}

const dedupSettingsForm = ref({ ...defaultDedupSettings })
const loading = ref(false)

const loadDedupSettings = async () => {
  try {
    const settings = await getProcessingSettings()
    if (settings?.dedup_params) {
      dedupSettingsForm.value = { ...dedupSettingsForm.value, ...settings.dedup_params }
    }
  } catch (error) {
    console.error('Failed to load dedup settings', error)
  }
}

const saveDedupSettings = async () => {
  loading.value = true
  try {
    const updated = await updateProcessingSettings({ dedup_params: dedupSettingsForm.value })
    dedupSettingsForm.value = { ...dedupSettingsForm.value, ...updated.dedup_params }
    emit('save')
    ElMessage.success('???????')
  } catch (error) {
    console.error(error)
    ElMessage.error('????????')
  } finally {
    loading.value = false
  }
}

const resetDedupSettings = async () => {
  dedupSettingsForm.value = { ...defaultDedupSettings }
  await saveDedupSettings()
}

onMounted(() => {
  loadDedupSettings()
})
</script>

<style scoped>
.settings-section {
  padding: 10px 0;
}

.form-hint {
  font-size: 12px;
  color: var(--muted);
  margin-top: 4px;
  margin-bottom: 12px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 16px;
}
</style>