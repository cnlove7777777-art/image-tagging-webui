<template>
  <div class="settings-section">
    <el-alert
      title="模型服务由后端配置"
      type="info"
      :closable="false"
      show-icon
      class="provider-alert"
    >
      <div>
        API Key、Base URL 和模型供应商现在从后端 yml / 环境变量读取。前端只展示可用供应商与模型，不再保存密钥。
      </div>
    </el-alert>

    <el-form label-width="120px">
      <el-form-item label="默认供应商">
        <el-tag type="primary">{{ modelInfo.default_provider || '未配置' }}</el-tag>
      </el-form-item>

      <el-form-item label="供应商状态">
        <div class="provider-list">
          <el-card v-for="provider in modelInfo.providers" :key="provider.id" shadow="never" class="provider-card">
            <div class="provider-header">
              <div>
                <div class="provider-title">{{ provider.display_name || provider.id }}</div>
                <div class="provider-sub">{{ provider.id }}</div>
              </div>
              <el-tag :type="provider.configured ? 'success' : 'warning'">
                {{ provider.configured ? '后端已配置密钥' : '缺少环境变量密钥' }}
              </el-tag>
            </div>
            <div class="provider-meta">Base URL：{{ provider.base_url || '-' }}</div>
            <div class="provider-meta">默认视觉模型：{{ provider.default_vision_model || '-' }}</div>
            <div class="provider-models">
              <el-tag v-for="model in provider.models" :key="model.id" size="small">
                {{ model.label || model.id }}
              </el-tag>
            </div>
          </el-card>
          <el-empty v-if="!modelInfo.providers.length" description="后端未返回模型供应商" />
        </div>
      </el-form-item>

      <el-form-item label="裁切输出尺寸">
        <el-input v-model="cropOutputSizeText" placeholder="1024x1024" style="width: 220px" />
        <div class="form-hint">只支持正方形输出，例如 1024x1024。</div>
      </el-form-item>
    </el-form>

    <div class="dialog-footer">
      <el-button :loading="loadingModels" @click="loadModels">刷新模型列表</el-button>
      <el-button type="primary" @click="saveSettings">保存裁切设置</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getModels, getProcessingSettings, updateProcessingSettings } from '../services/api'

const emit = defineEmits<{
  save: []
}>()

interface ProviderModel {
  id: string
  label?: string
  tasks?: string[]
}

interface ProviderInfo {
  id: string
  display_name?: string
  configured?: boolean
  base_url?: string
  default_vision_model?: string
  models: ProviderModel[]
}

const cropOutputSizeText = ref('1024x1024')
const loadingModels = ref(false)
const modelInfo = ref<{ default_provider?: string; providers: ProviderInfo[] }>({ providers: [] })

const parseCropOutputSize = (value: string) => {
  const raw = String(value || '').trim().toLowerCase()
  const match = raw.match(/^(\d+)(?:\s*x\s*(\d+))?$/)
  if (!match) return { size: null, error: '请输入类似 1024x1024 的尺寸' }
  const size = Number(match[1])
  const size2 = match[2] ? Number(match[2]) : size
  if (!Number.isFinite(size) || size <= 0) {
    return { size: null, error: '尺寸必须是正整数' }
  }
  if (size2 !== size) {
    return { size: null, error: '当前只支持 1:1 正方形输出' }
  }
  return { size, error: null }
}

const saveCropOutputSize = async () => {
  const parsed = parseCropOutputSize(cropOutputSizeText.value)
  if (!parsed.size) {
    if (parsed.error) ElMessage.error(parsed.error)
    return false
  }
  const updated = await updateProcessingSettings({ crop_output_size: parsed.size })
  if (updated?.crop_output_size) {
    cropOutputSizeText.value = `${updated.crop_output_size}x${updated.crop_output_size}`
  }
  return true
}

const saveSettings = async () => {
  const ok = await saveCropOutputSize()
  if (ok) {
    emit('save')
    ElMessage.success('裁切设置已保存')
  }
}

const loadCropOutputSize = async () => {
  try {
    const settings = await getProcessingSettings()
    if (settings?.crop_output_size) {
      cropOutputSizeText.value = `${settings.crop_output_size}x${settings.crop_output_size}`
    }
  } catch (error) {
    console.error('Failed to load crop output size', error)
  }
}

const loadModels = async () => {
  loadingModels.value = true
  try {
    const models = await getModels()
    modelInfo.value = {
      default_provider: (models as any).default_provider,
      providers: (models as any).providers || []
    }
  } catch (error) {
    console.error('Failed to load models', error)
    ElMessage.error('模型列表加载失败')
  } finally {
    loadingModels.value = false
  }
}

onMounted(() => {
  loadCropOutputSize()
  loadModels()
})
</script>

<style scoped>
.settings-section {
  padding: 10px 0;
}

.provider-alert {
  margin-bottom: 16px;
}

.provider-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
}

.provider-card {
  width: 100%;
  background-color: var(--card);
  border-color: var(--border);
}

.provider-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.provider-title {
  font-weight: 600;
  color: var(--text);
}

.provider-sub,
.provider-meta,
.form-hint {
  font-size: 12px;
  color: var(--muted);
}

.provider-models {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 16px;
}
</style>
