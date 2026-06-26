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
        前端可以选择和查看模型供应商，但 API Key 仍由后端 yml / 环境变量管理。点击“查询可用模型”会请求后端尝试动态拉取 provider 模型列表。
      </div>
    </el-alert>

    <el-form label-width="120px">
      <el-form-item label="模型供应商">
        <el-select
          v-model="selectedProviderId"
          placeholder="选择模型供应商"
          style="width: 320px"
          :loading="loadingModels"
          @change="handleProviderChange"
        >
          <el-option
            v-for="provider in modelInfo.providers"
            :key="provider.id"
            :label="provider.display_name || provider.id"
            :value="provider.id"
          >
            <div class="provider-option">
              <span>{{ provider.display_name || provider.id }}</span>
              <el-tag size="small" :type="provider.configured ? 'success' : 'warning'">
                {{ provider.configured ? '已配置' : '缺少密钥' }}
              </el-tag>
            </div>
          </el-option>
        </el-select>
        <div class="form-hint">
          当前后端默认：{{ modelInfo.default_provider || '未配置' }}。供应商默认值由 config/model_providers.yml 决定。
        </div>
      </el-form-item>

      <el-form-item label="供应商状态">
        <el-card v-if="selectedProvider" shadow="never" class="provider-card">
          <div class="provider-header">
            <div>
              <div class="provider-title">{{ selectedProvider.display_name || selectedProvider.id }}</div>
              <div class="provider-sub">{{ selectedProvider.id }}</div>
            </div>
            <div class="provider-tags">
              <el-tag :type="selectedProvider.configured ? 'success' : 'warning'">
                {{ selectedProvider.configured ? '后端已配置密钥' : '缺少环境变量密钥' }}
              </el-tag>
              <el-tag size="small" :type="selectedProvider.dynamic_model_list ? 'success' : 'info'">
                {{ selectedProvider.dynamic_model_list ? '支持动态查询' : '静态模型列表' }}
              </el-tag>
            </div>
          </div>
          <div class="provider-meta">Base URL：{{ selectedProvider.base_url || '-' }}</div>
          <div class="provider-meta">默认视觉模型：{{ selectedProvider.default_vision_model || '-' }}</div>
          <div class="provider-meta">默认焦点模型：{{ selectedProvider.default_focus_model || '-' }}</div>
          <div class="provider-meta">默认打标模型：{{ selectedProvider.default_tag_model || '-' }}</div>
        </el-card>
        <el-empty v-else description="后端未返回模型供应商" />
      </el-form-item>

      <el-form-item label="可用模型">
        <div class="model-list">
          <el-tag v-for="model in selectedProviderModels" :key="model.id" size="small">
            {{ model.label || model.id }}
            <span v-if="model.tasks?.length" class="model-tasks"> / {{ model.tasks.join(', ') }}</span>
          </el-tag>
          <el-empty v-if="selectedProvider && !selectedProviderModels.length" description="该供应商暂无模型列表" />
        </div>
      </el-form-item>

      <el-form-item label="裁切输出尺寸">
        <el-input v-model="cropOutputSizeText" placeholder="1024x1024" style="width: 220px" />
        <div class="form-hint">只支持正方形输出，例如 1024x1024。</div>
      </el-form-item>
    </el-form>

    <div class="dialog-footer">
      <el-button :loading="loadingModels" @click="loadModels(false)">刷新配置</el-button>
      <el-button :loading="loadingModels" type="primary" plain @click="loadModels(true)">查询可用模型</el-button>
      <el-button type="primary" @click="saveSettings">保存裁切设置</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
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
  dynamic_model_list?: boolean
  default_vision_model?: string
  default_focus_model?: string
  default_tag_model?: string
  models: ProviderModel[]
}

const cropOutputSizeText = ref('1024x1024')
const loadingModels = ref(false)
const selectedProviderId = ref('')
const modelInfo = ref<{ default_provider?: string; providers: ProviderInfo[] }>({ providers: [] })

const selectedProvider = computed(() => {
  return modelInfo.value.providers.find(provider => provider.id === selectedProviderId.value) || modelInfo.value.providers[0]
})

const selectedProviderModels = computed(() => selectedProvider.value?.models || [])

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

const handleProviderChange = () => {
  const provider = selectedProvider.value
  if (!provider) return
  if (!provider.configured) {
    ElMessage.warning(`后端缺少 ${provider.id} 的密钥环境变量`)
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

const loadModels = async (refresh = false) => {
  loadingModels.value = true
  try {
    const models = await getModels(refresh)
    const providers = (models as any).providers || []
    modelInfo.value = {
      default_provider: (models as any).default_provider,
      providers
    }
    if (!selectedProviderId.value || !providers.some((provider: ProviderInfo) => provider.id === selectedProviderId.value)) {
      selectedProviderId.value = (models as any).default_provider || providers[0]?.id || ''
    }
    if (refresh) {
      ElMessage.success('模型列表已刷新；若供应商不支持动态接口，将显示 yml 静态列表')
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
  loadModels(false)
})
</script>

<style scoped>
.settings-section {
  padding: 10px 0;
}

.provider-alert {
  margin-bottom: 16px;
}

.provider-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
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

.provider-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: flex-end;
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

.model-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  width: 100%;
}

.model-tasks {
  opacity: 0.7;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 16px;
}
</style>
