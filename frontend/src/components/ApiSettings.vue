<template>
  <div class="provider-manager">
    <el-alert
      title="模型供应商管理"
      type="info"
      :closable="false"
      show-icon
      class="provider-alert"
    >
      <div>
        可以像模型客户端一样添加自定义供应商、保存 Base URL / API Key / 模型列表，并测试连通性。密钥只保存到后端本地运行时文件，不写入 Git，也不回显完整值。
      </div>
    </el-alert>

    <div class="manager-layout">
      <aside class="provider-sidebar">
        <div class="sidebar-title">供应商</div>
        <div class="provider-list">
          <button
            v-for="provider in modelInfo.providers"
            :key="provider.id"
            class="provider-item"
            :class="{ active: provider.id === selectedProviderId }"
            @click="selectedProviderId = provider.id"
          >
            <span class="provider-dot" :class="{ configured: provider.configured }"></span>
            <span class="provider-name">{{ provider.display_name || provider.id }}</span>
            <span v-if="provider.source === 'runtime'" class="provider-source">自定义</span>
          </button>
          <el-empty v-if="!modelInfo.providers.length" description="暂无供应商" />
        </div>
        <el-button class="add-provider-btn" type="primary" plain @click="addDialogVisible = true">
          + 添加供应商
        </el-button>
      </aside>

      <main class="provider-detail" v-if="selectedProvider">
        <div class="detail-header">
          <div>
            <div class="detail-title">
              <el-input v-model="providerForm.display_name" placeholder="供应商名称" class="title-input" />
            </div>
            <div class="provider-sub">{{ selectedProvider.id }}</div>
          </div>
          <div class="detail-actions">
            <el-tag :type="selectedProvider.configured || runtimeConfig.has_api_key ? 'success' : 'warning'">
              {{ selectedProvider.configured || runtimeConfig.has_api_key ? '已配置' : '缺少密钥' }}
            </el-tag>
            <el-tag :type="providerForm.enabled ? 'success' : 'info'">
              {{ providerForm.enabled ? '启用' : '禁用' }}
            </el-tag>
            <el-switch v-model="providerForm.enabled" active-text="启用" inactive-text="禁用" />
            <el-button v-if="selectedProvider.source === 'runtime'" type="danger" plain @click="handleDeleteProvider">
              删除
            </el-button>
          </div>
        </div>

        <el-form label-width="120px" class="provider-form">
          <el-form-item label="Base URL">
            <el-input v-model="providerForm.base_url" placeholder="例如 https://dashscope.aliyuncs.com/compatible-mode/v1" />
          </el-form-item>

          <el-form-item label="API 格式">
            <el-select v-model="providerForm.api_format" style="width: 100%">
              <el-option label="Chat Completions (/chat/completions)" value="openai_chat_completions" />
            </el-select>
          </el-form-item>

          <el-form-item label="API Key">
            <el-input
              v-model="providerForm.api_key"
              type="password"
              show-password
              placeholder="留空表示不修改已保存密钥"
            />
            <div class="form-hint">已保存：{{ runtimeConfig.api_key_masked || '未保存' }}</div>
          </el-form-item>

          <el-form-item label="模型列表接口">
            <el-input v-model="providerForm.model_list_path" placeholder="/models" style="max-width: 240px" />
            <el-switch v-model="providerForm.dynamic_model_list" active-text="动态查询" inactive-text="静态列表" class="inline-switch" />
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

          <el-form-item label="模型列表">
            <div class="model-editor">
              <div v-for="(model, index) in providerModels" :key="index" class="model-row">
                <el-input v-model="model.id" placeholder="模型 ID，例如 qwen-vl-plus" />
                <el-input v-model="model.label" placeholder="显示名称，可选" />
                <el-button text type="danger" @click="removeModel(index)">删除</el-button>
              </div>
              <el-button plain @click="addModel">+ 添加模型</el-button>
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
          <el-button :loading="testingProvider" plain @click="testConnectivity">测试连通性</el-button>
          <el-button :loading="savingProvider" type="warning" plain @click="saveProviderConfig(true)">保存供应商</el-button>
          <el-button type="primary" @click="saveSettings">保存裁切设置</el-button>
        </div>

        <el-alert
          v-if="testResult"
          class="test-result"
          :type="testResult.ok ? 'success' : 'error'"
          :title="testResult.ok ? '连通性测试成功' : '连通性测试失败'"
          :closable="false"
          show-icon
        >
          <div v-if="testResult.ok">
            状态码：{{ testResult.status_code }}；模型数量：{{ testResult.model_count ?? '未知' }}；样例：{{ testResult.sample_models?.join(', ') || '-' }}
          </div>
          <div v-else>
            {{ testResult.error || '未知错误' }}
          </div>
        </el-alert>
      </main>

      <main v-else class="provider-detail empty-detail">
        <el-empty description="请选择或添加一个供应商" />
      </main>
    </div>

    <el-dialog v-model="addDialogVisible" title="添加供应商" width="520px">
      <el-form label-width="110px">
        <el-form-item label="供应商名称">
          <el-input v-model="createForm.display_name" placeholder="例如 阿里云百炼" />
        </el-form-item>
        <el-form-item label="供应商 ID">
          <el-input v-model="createForm.provider_id" placeholder="可选，例如 aliyun_dashscope_custom" />
        </el-form-item>
        <el-form-item label="Base URL">
          <el-input v-model="createForm.base_url" placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="createForm.api_key" type="password" show-password />
        </el-form-item>
        <el-form-item label="默认模型">
          <el-input v-model="createForm.default_vision_model" placeholder="例如 qwen-vl-plus" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creatingProvider" @click="handleCreateProvider">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createProvider,
  deleteProvider,
  getModels,
  getProcessingSettings,
  getProviderRuntimeConfig,
  saveProviderRuntimeConfig,
  testProviderConnectivity,
  updateProcessingSettings,
  type ProviderInfo,
  type ProviderModel,
  type ProviderRuntimeConfig,
  type ProviderTestResult
} from '../services/api'

const emit = defineEmits<{
  save: []
}>()

const cropOutputSizeText = ref('1024x1024')
const loadingModels = ref(false)
const savingProvider = ref(false)
const creatingProvider = ref(false)
const testingProvider = ref(false)
const addDialogVisible = ref(false)
const selectedProviderId = ref('')
const modelInfo = ref<{ default_provider?: string; providers: ProviderInfo[] }>({ providers: [] })
const runtimeConfig = ref<ProviderRuntimeConfig>({ provider_id: '' })
const testResult = ref<ProviderTestResult | null>(null)
const providerModels = ref<ProviderModel[]>([])

const providerForm = reactive({
  display_name: '',
  enabled: true,
  base_url: '',
  api_key: '',
  api_format: 'openai_chat_completions',
  model_list_path: '/models',
  dynamic_model_list: true,
  default_vision_model: '',
  default_focus_model: '',
  default_tag_model: ''
})

const createForm = reactive({
  display_name: '',
  provider_id: '',
  base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
  api_key: '',
  default_vision_model: 'qwen-vl-plus'
})

const selectedProvider = computed(() => {
  return modelInfo.value.providers.find(provider => provider.id === selectedProviderId.value) || modelInfo.value.providers[0]
})

const resetProviderForm = (provider?: ProviderInfo, runtime?: ProviderRuntimeConfig) => {
  if (!provider) return
  const models = runtime?.models?.length ? runtime.models : provider.models || []
  providerForm.display_name = runtime?.display_name || provider.display_name || provider.id
  providerForm.enabled = runtime?.enabled ?? provider.enabled ?? true
  providerForm.base_url = runtime?.base_url || provider.base_url || ''
  providerForm.api_key = ''
  providerForm.api_format = runtime?.api_format || provider.api_format || 'openai_chat_completions'
  providerForm.model_list_path = runtime?.model_list_path || provider.model_list_path || '/models'
  providerForm.dynamic_model_list = runtime?.dynamic_model_list ?? provider.dynamic_model_list ?? true
  providerForm.default_vision_model = runtime?.default_vision_model || provider.default_vision_model || ''
  providerForm.default_focus_model = runtime?.default_focus_model || provider.default_focus_model || provider.default_vision_model || ''
  providerForm.default_tag_model = runtime?.default_tag_model || provider.default_tag_model || provider.default_vision_model || ''
  providerModels.value = models.map(model => ({
    id: model.id,
    label: model.label || model.id,
    tasks: model.tasks || ['vision_analyze', 'focus', 'caption', 'tag']
  }))
}

const cleanModels = () => providerModels.value
  .map(model => ({
    id: String(model.id || '').trim(),
    label: String(model.label || model.id || '').trim(),
    tasks: model.tasks?.length ? model.tasks : ['vision_analyze', 'focus', 'caption', 'tag']
  }))
  .filter(model => model.id)

const addModel = () => {
  providerModels.value.push({ id: '', label: '', tasks: ['vision_analyze', 'focus', 'caption', 'tag'] })
}

const removeModel = (index: number) => {
  providerModels.value.splice(index, 1)
}

const parseCropOutputSize = (value: string) => {
  const raw = String(value || '').trim().toLowerCase()
  const match = raw.match(/^(\d+)(?:\s*x\s*(\d+))?$/)
  if (!match) return { size: null, error: '请输入类似 1024x1024 的尺寸' }
  const size = Number(match[1])
  const size2 = match[2] ? Number(match[2]) : size
  if (!Number.isFinite(size) || size <= 0) return { size: null, error: '尺寸必须是正整数' }
  if (size2 !== size) return { size: null, error: '当前只支持 1:1 正方形输出' }
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
    resetProviderForm(selectedProvider.value, data)
    testResult.value = null
  } catch (error) {
    console.error('Failed to load provider runtime config', error)
    runtimeConfig.value = { provider_id: selectedProviderId.value }
    resetProviderForm(selectedProvider.value)
  }
}

const saveProviderConfig = async (showMessage = true) => {
  if (!selectedProviderId.value) return false
  savingProvider.value = true
  try {
    const payload: any = {
      display_name: providerForm.display_name,
      enabled: providerForm.enabled,
      base_url: providerForm.base_url,
      api_format: providerForm.api_format,
      model_list_path: providerForm.model_list_path,
      dynamic_model_list: providerForm.dynamic_model_list,
      default_vision_model: providerForm.default_vision_model,
      default_focus_model: providerForm.default_focus_model,
      default_tag_model: providerForm.default_tag_model,
      models: cleanModels()
    }
    if (providerForm.api_key.trim()) payload.api_key = providerForm.api_key.trim()
    const saved = await saveProviderRuntimeConfig(selectedProviderId.value, payload)
    runtimeConfig.value = saved
    providerForm.api_key = ''
    if (showMessage) ElMessage.success('供应商配置已保存到后端本地')
    await loadModels(false, selectedProviderId.value)
    return true
  } catch (error) {
    console.error('Failed to save provider runtime config', error)
    if (showMessage) ElMessage.error('供应商配置保存失败')
    return false
  } finally {
    savingProvider.value = false
  }
}

const testConnectivity = async () => {
  const saved = await saveProviderConfig(false)
  if (!saved || !selectedProviderId.value) return
  testingProvider.value = true
  try {
    const result = await testProviderConnectivity(selectedProviderId.value, providerForm.default_vision_model)
    testResult.value = result
    if (result.ok) {
      ElMessage.success('连通性测试成功')
    } else {
      ElMessage.error('连通性测试失败')
    }
  } catch (error) {
    console.error('Failed to test provider', error)
    ElMessage.error('连通性测试失败')
  } finally {
    testingProvider.value = false
  }
}

const handleCreateProvider = async () => {
  if (!createForm.display_name.trim()) {
    ElMessage.warning('请填写供应商名称')
    return
  }
  creatingProvider.value = true
  try {
    const saved = await createProvider({
      provider_id: createForm.provider_id,
      display_name: createForm.display_name,
      base_url: createForm.base_url,
      api_key: createForm.api_key,
      api_format: 'openai_chat_completions',
      model_list_path: '/models',
      dynamic_model_list: true,
      default_vision_model: createForm.default_vision_model,
      default_focus_model: createForm.default_vision_model,
      default_tag_model: createForm.default_vision_model,
      models: createForm.default_vision_model ? [{ id: createForm.default_vision_model, label: createForm.default_vision_model, tasks: ['vision_analyze', 'focus', 'caption', 'tag'] }] : []
    })
    addDialogVisible.value = false
    selectedProviderId.value = saved.provider_id
    createForm.display_name = ''
    createForm.provider_id = ''
    createForm.api_key = ''
    await loadModels(false, saved.provider_id)
    ElMessage.success('供应商已添加')
  } catch (error) {
    console.error('Failed to create provider', error)
    ElMessage.error('添加供应商失败')
  } finally {
    creatingProvider.value = false
  }
}

const handleDeleteProvider = async () => {
  if (!selectedProvider.value) return
  try {
    await ElMessageBox.confirm(`确认删除供应商「${selectedProvider.value.display_name || selectedProvider.value.id}」？`, '删除供应商', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteProvider(selectedProvider.value.id)
    selectedProviderId.value = ''
    await loadModels(false)
    ElMessage.success('供应商已删除')
  } catch (error) {
    console.error('Failed to delete provider', error)
    ElMessage.error('删除供应商失败')
  }
}

const loadCropOutputSize = async () => {
  try {
    const settings = await getProcessingSettings()
    if (settings?.crop_output_size) cropOutputSizeText.value = `${settings.crop_output_size}x${settings.crop_output_size}`
  } catch (error) {
    console.error('Failed to load crop output size', error)
  }
}

const loadModels = async (refresh = false, preferredProviderId = '') => {
  loadingModels.value = true
  try {
    const models = await getModels(refresh)
    const providers = (models as any).providers || []
    modelInfo.value = { default_provider: (models as any).default_provider, providers }
    const target = preferredProviderId || selectedProviderId.value
    if (target && providers.some((provider: ProviderInfo) => provider.id === target)) {
      selectedProviderId.value = target
    } else {
      selectedProviderId.value = (models as any).default_provider || providers[0]?.id || ''
    }
    await loadRuntimeConfig()
    if (refresh) ElMessage.success('模型列表已刷新；若供应商不支持动态接口，将显示本地静态列表')
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
.provider-manager {
  padding: 10px 0;
}
.provider-alert {
  margin-bottom: 16px;
}
.manager-layout {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
  min-height: 520px;
}
.provider-sidebar {
  padding: 16px 12px;
  border-right: 1px solid var(--border);
  background: var(--panel);
}
.sidebar-title {
  font-weight: 700;
  color: var(--muted);
  margin-bottom: 12px;
}
.provider-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 14px;
}
.provider-item {
  width: 100%;
  border: 1px solid transparent;
  border-radius: 10px;
  padding: 10px 12px;
  background: transparent;
  color: var(--text);
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  text-align: left;
}
.provider-item:hover,
.provider-item.active {
  border-color: var(--accent);
  background: rgba(64, 158, 255, 0.12);
}
.provider-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #a8abb2;
  flex: none;
}
.provider-dot.configured {
  background: #2ba471;
}
.provider-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.provider-source {
  font-size: 12px;
  color: var(--muted);
}
.add-provider-btn {
  width: 100%;
}
.provider-detail {
  padding: 22px 28px;
  min-width: 0;
}
.empty-detail {
  display: flex;
  align-items: center;
  justify-content: center;
}
.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}
.detail-title {
  display: flex;
  align-items: center;
  gap: 8px;
}
.title-input {
  width: 260px;
  font-size: 20px;
  font-weight: 700;
}
.provider-sub,
.form-hint {
  font-size: 12px;
  color: var(--muted);
}
.detail-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.provider-form {
  max-width: 880px;
}
.inline-switch {
  margin-left: 12px;
}
.model-editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}
.model-row {
  display: grid;
  grid-template-columns: minmax(160px, 1fr) minmax(140px, 0.8fr) auto;
  gap: 8px;
  align-items: center;
}
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 16px;
  flex-wrap: wrap;
}
.test-result {
  margin-top: 16px;
}
</style>
