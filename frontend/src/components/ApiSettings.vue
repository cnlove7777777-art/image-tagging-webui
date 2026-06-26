<template>
  <div class="settings-section">
    <el-alert
      title="模型服务配置保存到后端"
      type="info"
      :closable="false"
      show-icon
      class="provider-alert"
    >
      <div>
        这里可以从前端填写供应商 Base URL 和 API Key，但保存位置在后端本地运行时文件，不写入 Git，也不会把完整密钥返回给前端。
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
              <el-tag :type="selectedProvider.configured || runtimeConfig.has_api_key ? 'success' : 'warning'">
                {{ selectedProvider.configured || runtimeConfig.has_api_key ? '后端已配置密钥' : '缺少后端密钥' }}
              </el-tag>
              <el-tag size="small" :type="selectedProvider.dynamic_model_list ? 'success' : 'info'">
                {{ selectedProvider.dynamic_model_list ? '支持动态查询' : '静态模型列表' }}
              </el-tag>
            </div>
          </div>
          <div class="provider-meta">Base URL：{{ selectedProvider.base_url || '-' }}</div>
          <div class="provider-meta">已保存密钥：{{ runtimeConfig.api_key_masked || '未保存' }}</div>
          <div class="provider-meta">默认视觉模型：{{ selectedProvider.default_vision_model || '-' }}</div>
          <div class="provider-meta">默认焦点模型：{{ selectedProvider.default_focus_model || '-' }}</div>
          <div class="provider-meta">默认打标模型：{{ selectedProvider.default_tag_model || '-' }}</div>
        </el-card>
        <el-empty v-else description="后端未返回模型供应商" />
      </el-form-item>

      <el-form-item label="后端 Base URL">
        <el-input v-model="providerForm.base_url" placeholder="例如 https://dashscope.aliyuncs.com/compatible-mode/v1" />
        <div class="form-hint">留空并保存会清除本地覆盖，回到 yml 默认值。</div>
      </el-form-item>

      <el-form-item label="API Key">
        <el-input
          v-model="providerForm.api_key"
          type="password"
          show-password
          placeholder="留空表示不修改已保存密钥"
        />
        <div class="form-hint">只提交给后端保存；接口返回时只显示脱敏结果，不回显完整 key。</div>
      </el-form-item>

      <el-form-item label="默认视觉模型">
        <el-input v-model="providerForm.default_vision_model" placeholder="例如 qwen-vl-plus" />
      </el-form-item>

      <el-form-item label="默认焦点模型">
        <el-input v-model="providerForm.default_focus_model" placeholder="例如 qwen-vl-plus" />
      </el-form-item>

      <el-form-item label="默认打标模型">
        <el-input v-model="providerForm.default_tag_model" placeholder="例如 qwen-vl-plus" />
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
      <el-button :loading="savingProvider" type="warning" plain @click="saveProviderConfig">保存模型服务</el-button>
      <el-button type="primary" @click="saveSettings">保存裁切设置</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getModels,
  getProcessingSettings,
  getProviderRuntimeConfig,
  saveProviderRuntimeConfig,
  updateProcessingSettings
} from '../services/api'

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
const savingProvider = ref(false)
const selectedProviderId = ref('')
const modelInfo = ref<{ default_provider?: string; providers: ProviderInfo[] }>({ providers: [] })
const runtimeConfig = ref<{ api_key_masked?: string; has_api_key?: boolean }>({})
const providerForm = reactive({
  base_url: '',
  api_key: '',
  default_vision_model: '',
  default_focus_model: '',
  default_tag_model: ''
})

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

const loadRuntimeConfig = async () => {
  if (!selectedProviderId.value) return
  try {
    const data = await getProviderRuntimeConfig(selectedProviderId.value)
    runtimeConfig.value = data
    const provider = selectedProvider.value
    providerForm.base_url = data.base_url || provider?.base_url || ''
    providerForm.api_key = ''
    providerForm.default_vision_model = data.default_vision_model || provider?.default_vision_model || ''
    providerForm.default_focus_model = data.default_focus_model || provider?.default_focus_model || ''
    providerForm.default_tag_model = data.default_tag_model || provider?.default_tag_model || ''
  } catch (error) {
    console.error('Failed to load provider runtime config', error)
    runtimeConfig.value = {}
  }
}

const saveProviderConfig = async () => {
  if (!selectedProviderId.value) return
  savingProvider.value = true
  try {
    const payload: any = {
      base_url: providerForm.base_url,
      default_vision_model: providerForm.default_vision_model,
      default_focus_model: providerForm.default_focus_model,
      default_tag_model: providerForm.default_tag_model
    }
    if (providerForm.api_key.trim()) {
      payload.api_key = providerForm.api_key.trim()
    }
    const saved = await saveProviderRuntimeConfig(selectedProviderId.value, payload)
    runtimeConfig.value = saved
    providerForm.api_key = ''
    ElMessage.success('模型服务配置已保存到后端本地')
    await loadModels(false)
  } catch (error) {
    console.error('Failed to save provider runtime config', error)
    ElMessage.error('模型服务配置保存失败')
  } finally {
    savingProvider.value = false
  }
}

const handleProviderChange = async () => {
  const provider = selectedProvider.value
  if (!provider) return
  await loadRuntimeConfig()
  if (!provider.configured && !runtimeConfig.value.has_api_key) {
    ElMessage.warning(`后端尚未保存 ${provider.id} 的 API Key`)
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
    await loadRuntimeConfig()
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

watch(selectedProviderId, () => {
  loadRuntimeConfig()
})

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
