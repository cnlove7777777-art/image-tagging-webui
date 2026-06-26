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
        可以添加自定义供应商、保存 Base URL / API Key / 模型列表，并测试连通性。密钥只保存到后端本地运行时文件，不写入 Git，也不回显完整值。
      </div>
    </el-alert>

    <div class="manager-layout">
      <aside class="provider-sidebar">
        <div class="sidebar-title">供应商</div>
        <div class="provider-list">
          <el-button
            v-for="provider in modelInfo.providers"
            :key="provider.id"
            native-type="button"
            class="provider-item"
            :class="{ active: provider.id === selectedProviderId }"
            @click.prevent="selectProvider(provider.id)"
          >
            <span class="provider-dot" :class="{ configured: provider.configured }"></span>
            <span class="provider-name">{{ provider.display_name || provider.id }}</span>
            <span v-if="provider.source === 'runtime'" class="provider-source">自定义</span>
          </el-button>
          <el-empty v-if="!modelInfo.providers.length" description="暂无供应商" :image-size="80" />
        </div>

        <el-button
          class="add-provider-btn"
          type="primary"
          plain
          native-type="button"
          @click="addDialogVisible = true"
        >
          + 添加供应商
        </el-button>
      </aside>

      <main class="provider-detail" v-if="selectedProvider">
        <div class="detail-header">
          <div>
            <el-input v-model="providerForm.display_name" placeholder="供应商名称" class="title-input" />
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
            <el-button
              v-if="selectedProvider.source === 'runtime'"
              type="danger"
              plain
              native-type="button"
              @click="handleDeleteProvider"
            >
              删除
            </el-button>
          </div>
        </div>

        <el-form label-width="110px" class="provider-form" @submit.prevent>
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
            <div class="model-section">
              <el-tabs v-model="modelTab" class="model-tabs" @tab-change="onModelTabChange">
                <el-tab-pane label="我的收藏" name="favorites">
                  <div v-if="favoriteModels.length" class="model-list-info">共 {{ favoriteModels.length }} 个收藏</div>
                  <div v-if="favoriteModels.length" class="model-grid">
                    <div
                      v-for="model in favoriteModels"
                      :key="model.id"
                      class="model-grid-item"
                      :class="{ selected: isModelSelected(model.id) }"
                    >
                      <span class="model-grid-id" title="点击设为默认模型" @click="useModel(model)">{{ model.id }}</span>
                      <el-button text type="warning" size="small" native-type="button" @click.stop="toggleFavorite(model)">
                        <el-icon><StarFilled /></el-icon>
                      </el-button>
                    </div>
                  </div>
                  <el-empty v-else description="暂无收藏模型，请到“动态查询”中点击星标添加" :image-size="80" />
                </el-tab-pane>

                <el-tab-pane label="自定义" name="custom">
                  <div class="model-editor">
                    <div v-if="providerModels.length" class="model-list-info">共 {{ providerModels.length }} 个模型</div>
                    <div v-for="(model, index) in providerModels" :key="`${model.id || 'new'}-${index}`" class="model-row">
                      <el-input v-model="model.id" placeholder="模型 ID，例如 qwen-vl-plus" />
                      <el-input v-model="model.label" placeholder="显示名称，可选" />
                      <el-button text type="danger" native-type="button" @click="removeModel(index)">删除</el-button>
                    </div>
                    <el-button plain native-type="button" @click="addModel">+ 添加模型</el-button>
                  </div>
                </el-tab-pane>

                <el-tab-pane label="动态查询" name="dynamic">
                  <div class="dynamic-query-bar">
                    <el-button type="primary" :loading="loadingModels" native-type="button" @click="handleDynamicQuery">
                      <el-icon><Search /></el-icon>
                      查询可用模型
                    </el-button>
                    <span v-if="queriedModels.length" class="model-list-info">共 {{ queriedModels.length }} 个模型</span>
                  </div>

                  <div v-if="queriedModels.length" class="model-grid">
                    <div
                      v-for="model in queriedModels"
                      :key="model.id"
                      class="model-grid-item"
                      :class="{ selected: isModelSelected(model.id) }"
                    >
                      <span class="model-grid-id" title="点击设为默认模型" @click="useModel(model)">{{ model.id }}</span>
                      <el-button
                        text
                        :type="isFavorite(model.id) ? 'warning' : 'info'"
                        size="small"
                        native-type="button"
                        @click.stop="toggleFavorite(model)"
                      >
                        <el-icon><StarFilled v-if="isFavorite(model.id)" /><Star v-else /></el-icon>
                      </el-button>
                    </div>
                  </div>
                  <el-empty v-else description="点击“查询可用模型”从供应商获取最新模型列表" :image-size="80" />
                </el-tab-pane>
              </el-tabs>
            </div>
          </el-form-item>

          <el-form-item label="裁切输出尺寸">
            <el-input v-model="cropOutputSizeText" placeholder="1024x1024" style="width: 220px" />
            <div class="form-hint">只支持正方形输出，例如 1024x1024。</div>
          </el-form-item>
        </el-form>

        <div class="dialog-footer">
          <el-button :loading="loadingModels" native-type="button" @click="handleRefresh">刷新配置</el-button>
          <el-button :loading="savingProvider" type="warning" plain native-type="button" @click="saveProviderConfig(true)">保存供应商</el-button>
          <el-button :loading="testingProvider" plain native-type="button" @click="testConnectivity">测试连通性</el-button>
          <el-button type="primary" native-type="button" @click="saveSettings">保存裁切设置</el-button>
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
          <div v-else>{{ testResult.error || '未知错误' }}</div>
        </el-alert>
      </main>

      <main v-else class="provider-detail empty-detail">
        <el-empty description="请选择或添加一个供应商" />
      </main>
    </div>

    <el-dialog v-model="addDialogVisible" title="添加供应商" width="520px">
      <el-form label-width="110px" @submit.prevent>
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
        <el-button native-type="button" @click="addDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creatingProvider" native-type="button" @click="handleCreateProvider">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Star, StarFilled } from '@element-plus/icons-vue'
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
const queriedModels = ref<ProviderModel[]>([])
const favoriteIds = ref<Set<string>>(new Set())
const modelTab = ref<'favorites' | 'custom' | 'dynamic'>('favorites')

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

const favoriteModels = computed(() => {
  const merged = new Map<string, ProviderModel>()
  for (const model of [...providerModels.value, ...queriedModels.value]) {
    if (model.id && favoriteIds.value.has(model.id)) merged.set(model.id, model)
  }
  return [...merged.values()].sort((a, b) => String(a.id || '').localeCompare(String(b.id || ''), undefined, { sensitivity: 'base' }))
})

function sortAndDedup(models: ProviderModel[]): ProviderModel[] {
  const seen = new Set<string>()
  return [...models]
    .map(model => ({
      id: String(model.id || '').trim(),
      label: String(model.label || model.id || '').trim(),
      tasks: model.tasks?.length ? model.tasks : ['vision_analyze', 'focus', 'caption', 'tag']
    }))
    .filter(model => {
      if (!model.id || seen.has(model.id)) return false
      seen.add(model.id)
      return true
    })
    .sort((a, b) => String(a.id || '').localeCompare(String(b.id || ''), undefined, { sensitivity: 'base' }))
}

function mapToForm(models: any[]): ProviderModel[] {
  return sortAndDedup((models || []).map(model => ({
    id: model?.id || model?.model || model?.name || '',
    label: model?.label || model?.id || model?.model || model?.name || '',
    tasks: model?.tasks?.length ? model.tasks : ['vision_analyze', 'focus', 'caption', 'tag']
  })))
}

function isModelSelected(modelId: string): boolean {
  return providerForm.default_vision_model === modelId
}

const favoritesStorageKey = computed(() => `model_favorites_${selectedProviderId.value}`)

function loadFavorites() {
  try {
    const raw = localStorage.getItem(favoritesStorageKey.value)
    favoriteIds.value = raw ? new Set((JSON.parse(raw) || []).filter((id: unknown) => typeof id === 'string' && id)) : new Set()
  } catch {
    favoriteIds.value = new Set()
  }
}

function saveFavorites() {
  localStorage.setItem(favoritesStorageKey.value, JSON.stringify([...favoriteIds.value]))
}

function isFavorite(modelId: string) {
  return favoriteIds.value.has(modelId)
}

function toggleFavorite(model: ProviderModel) {
  if (!model.id) return
  const next = new Set(favoriteIds.value)
  if (next.has(model.id)) next.delete(model.id)
  else next.add(model.id)
  favoriteIds.value = next
  saveFavorites()
}

function useModel(model: ProviderModel) {
  if (!model.id) return
  providerForm.default_vision_model = model.id
  providerForm.default_focus_model = model.id
  providerForm.default_tag_model = model.id
  ElMessage.success(`已选用模型：${model.id}`)
}

function onModelTabChange() {
  // Element Plus tabs do not submit forms, but keep this as a single safe hook.
}

function applyProviderToForm(provider: ProviderInfo | undefined, runtime?: ProviderRuntimeConfig) {
  if (!provider) return
  const runtimeModels = runtime?.models?.length ? runtime.models : []
  const sourceModels = runtimeModels.length ? runtimeModels : (provider.models || [])
  providerModels.value = mapToForm(sourceModels)

  providerForm.display_name = runtime?.display_name || provider.display_name || provider.id
  providerForm.enabled = runtime?.enabled ?? provider.enabled ?? true
  providerForm.base_url = runtime?.base_url || provider.base_url || ''
  providerForm.api_key = ''
  providerForm.api_format = runtime?.api_format || provider.api_format || 'openai_chat_completions'
  providerForm.model_list_path = runtime?.model_list_path || provider.model_list_path || '/models'
  providerForm.dynamic_model_list = runtime?.dynamic_model_list ?? provider.dynamic_model_list ?? true
  providerForm.default_vision_model = runtime?.default_vision_model || provider.default_vision_model || ''
  providerForm.default_focus_model = runtime?.default_focus_model || provider.default_focus_model || providerForm.default_vision_model
  providerForm.default_tag_model = runtime?.default_tag_model || provider.default_tag_model || providerForm.default_vision_model
}

function cleanModels() {
  return sortAndDedup(providerModels.value)
}

function addModel() {
  providerModels.value.push({ id: '', label: '', tasks: ['vision_analyze', 'focus', 'caption', 'tag'] })
}

function removeModel(index: number) {
  providerModels.value.splice(index, 1)
}

async function loadRuntimeConfig() {
  if (!selectedProviderId.value) return
  try {
    const data = await getProviderRuntimeConfig(selectedProviderId.value)
    runtimeConfig.value = data
    applyProviderToForm(selectedProvider.value, data)
    testResult.value = null
  } catch (error) {
    console.error('Failed to load provider runtime config', error)
    runtimeConfig.value = { provider_id: selectedProviderId.value }
    applyProviderToForm(selectedProvider.value)
  }
}

async function fetchProviders(refresh = false) {
  loadingModels.value = true
  try {
    const models = await getModels(refresh)
    const providers = (models as any).providers || []
    modelInfo.value = { default_provider: (models as any).default_provider, providers }
    return providers
  } catch (error) {
    console.error('Failed to load models', error)
    ElMessage.error('模型列表加载失败')
    return []
  } finally {
    loadingModels.value = false
  }
}

async function handleRefresh() {
  const providers = await fetchProviders(false)
  const target = selectedProviderId.value
  if (!target || !providers.some((provider: ProviderInfo) => provider.id === target)) {
    selectedProviderId.value = modelInfo.value.default_provider || providers[0]?.id || ''
  }
  await loadRuntimeConfig()
  loadFavorites()
}

async function handleDynamicQuery() {
  loadingModels.value = true
  try {
    const models = await getModels(true)
    const providers = (models as any).providers || []
    modelInfo.value = { default_provider: (models as any).default_provider, providers }

    const current = providers.find((provider: ProviderInfo) => provider.id === selectedProviderId.value)
    queriedModels.value = current?.models?.length ? mapToForm(current.models) : []
    loadFavorites()
    ElMessage.success(`已查询到 ${queriedModels.value.length} 个模型，点击星标可收藏`)
  } catch (error) {
    console.error('Failed to query models', error)
    ElMessage.error('动态查询失败')
  } finally {
    loadingModels.value = false
  }
}

function selectProvider(id: string) {
  if (!id || selectedProviderId.value === id) return
  selectedProviderId.value = id
}

async function saveProviderConfig(showMessage = true) {
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
    return true
  } catch (error) {
    console.error('Failed to save provider runtime config', error)
    if (showMessage) ElMessage.error('供应商配置保存失败')
    return false
  } finally {
    savingProvider.value = false
  }
}

async function testConnectivity() {
  const saved = await saveProviderConfig(false)
  if (!saved || !selectedProviderId.value) return
  testingProvider.value = true
  try {
    const result = await testProviderConnectivity(selectedProviderId.value, providerForm.default_vision_model)
    testResult.value = result
    if (result.ok) ElMessage.success('连通性测试成功')
    else ElMessage.error('连通性测试失败')
  } catch (error) {
    console.error('Failed to test provider', error)
    ElMessage.error('连通性测试失败')
  } finally {
    testingProvider.value = false
  }
}

async function handleCreateProvider() {
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
      models: createForm.default_vision_model
        ? [{ id: createForm.default_vision_model, label: createForm.default_vision_model, tasks: ['vision_analyze', 'focus', 'caption', 'tag'] }]
        : []
    })
    addDialogVisible.value = false
    createForm.display_name = ''
    createForm.provider_id = ''
    createForm.api_key = ''
    await handleRefresh()
    selectProvider(saved.provider_id)
    await loadRuntimeConfig()
    loadFavorites()
    ElMessage.success('供应商已添加')
  } catch (error) {
    console.error('Failed to create provider', error)
    ElMessage.error('添加供应商失败')
  } finally {
    creatingProvider.value = false
  }
}

async function handleDeleteProvider() {
  if (!selectedProvider.value) return
  try {
    await ElMessageBox.confirm(`确认删除供应商「${selectedProvider.value.display_name || selectedProvider.value.id}」？`, '删除供应商', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteProvider(selectedProvider.value.id)
    selectedProviderId.value = ''
    queriedModels.value = []
    await handleRefresh()
    ElMessage.success('供应商已删除')
  } catch (error) {
    console.error('Failed to delete provider', error)
    ElMessage.error('删除供应商失败')
  }
}

function parseCropOutputSize(value: string) {
  const raw = String(value || '').trim().toLowerCase()
  const match = raw.match(/^(\d+)(?:\s*x\s*(\d+))?$/)
  if (!match) return { size: null, error: '请输入类似 1024x1024 的尺寸' }
  const size = Number(match[1])
  const size2 = match[2] ? Number(match[2]) : size
  if (!Number.isFinite(size) || size <= 0) return { size: null, error: '尺寸必须是正整数' }
  if (size2 !== size) return { size: null, error: '当前只支持 1:1 正方形输出' }
  return { size, error: null }
}

async function saveSettings() {
  const parsed = parseCropOutputSize(cropOutputSizeText.value)
  if (!parsed.size) {
    if (parsed.error) ElMessage.error(parsed.error)
    return
  }
  try {
    const updated = await updateProcessingSettings({ crop_output_size: parsed.size })
    if (updated?.crop_output_size) cropOutputSizeText.value = `${updated.crop_output_size}x${updated.crop_output_size}`
    emit('save')
    ElMessage.success('裁切设置已保存')
  } catch (error) {
    console.error('Failed to save crop settings', error)
    ElMessage.error('裁切设置保存失败')
  }
}

watch(selectedProviderId, (newId) => {
  if (!newId) return
  queriedModels.value = []
  loadRuntimeConfig()
  loadFavorites()
})

onMounted(async () => {
  try {
    const settings = await getProcessingSettings()
    if (settings?.crop_output_size) cropOutputSizeText.value = `${settings.crop_output_size}x${settings.crop_output_size}`
  } catch (error) {
    console.error('Failed to load crop output size', error)
  }
  await handleRefresh()
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
  grid-template-columns: 220px minmax(0, 1fr);
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
  justify-content: flex-start;
  gap: 8px;
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
.provider-source,
.provider-sub,
.form-hint {
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
.title-input {
  width: 260px;
  font-size: 20px;
  font-weight: 700;
}
.detail-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.provider-form {
  max-width: 100%;
}
.model-section {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0 14px 14px;
}
.model-list-info {
  font-size: 13px;
  color: var(--muted);
  margin-bottom: 8px;
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
.model-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 8px;
}
.model-grid-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--panel);
}
.model-grid-item.selected {
  border-color: var(--accent);
  background: rgba(64, 158, 255, 0.08);
}
.model-grid-id {
  font-size: 13px;
  font-family: monospace;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
}
.model-grid-id:hover {
  color: var(--accent);
}
.dynamic-query-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
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
