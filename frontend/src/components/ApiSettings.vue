<template>
  <div class="settings-section">
    <el-form :model="settingsForm" label-width="120px">
      <el-form-item label="Base URL">
        <el-input v-model="settingsForm.base_url" placeholder="https://api-inference.modelscope.cn/v1" />
      </el-form-item>
      <el-form-item label="API Key">
        <el-input v-model="settingsForm.api_key" type="password" show-password placeholder="ModelScope Token" />
      </el-form-item>
      <el-form-item label="模型优先级">
        <el-select v-model="settingsForm.model_priority" multiple collapse-tags placeholder="可选" style="width: 100%">
          <el-option
            v-for="item in defaultModels"
            :key="item"
            :label="item"
            :value="item"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="启用自定义">
        <el-switch v-model="settingsForm.enabled" />
      </el-form-item>
      <div class="setting-hint">启用后将通过请求头携带 Base URL / API Key / 模型优先级</div>
    </el-form>
    <div class="dialog-footer">
      <el-button @click="resetSettings">恢复默认</el-button>
      <el-button :loading="testing" @click="testConnection">测试连接</el-button>
      <el-button type="primary" @click="saveSettings">保存并启用</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { loadApiSettings, saveApiSettings, testSettings } from '../services/api'

const emit = defineEmits<{
  save: []
}>()

const settingsForm = ref(loadApiSettings())
const testing = ref(false)
const defaultModels = [
  'Qwen/Qwen3-VL-30B-A3B-Instruct',
  'Qwen/Qwen3-VL-235B-A22B-Instruct',
  'Qwen/Qwen3-VL-32B-Instruct',
  'Qwen/Qwen3-VL-72B-Instruct'
]

const saveSettings = () => {
  saveApiSettings(settingsForm.value)
  emit('save')
  ElMessage.success('已保存 API 设置')
}

const resetSettings = () => {
  settingsForm.value = {
    base_url: '',
    api_key: '',
    model_priority: [],
    enabled: false
  }
  saveApiSettings(settingsForm.value)
}

const testConnection = async () => {
  testing.value = true
  try {
    const res = await testSettings({ ...settingsForm.value, enabled: true })
    if (res?.ok) {
      ElMessage.success(res.message || '连接成功')
    } else {
      ElMessage.error(res?.message || '连接失败')
    }
  } catch (err) {
    console.error(err)
    ElMessage.error('连接测试失败')
  } finally {
    testing.value = false
  }
}
</script>

<style scoped>
.settings-section {
  padding: 10px 0;
}

.setting-hint {
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