<template>
  <div class="settings-container">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>系统设置</span>
        </div>
      </template>
      
      <el-tabs v-model="activeTab" class="settings-tabs">
        <el-tab-pane label="API设置" name="api">
          <el-form :model="apiSettings" label-width="120px" class="settings-form">
            <el-form-item label="API Key" required>
              <el-input
                v-model="apiSettings.apiKey"
                type="password"
                placeholder="请输入ModelScope API Key"
                show-password
                clearable
              />
              <div class="form-hint">用于调用模型服务的API密钥</div>
            </el-form-item>
            
            <el-form-item label="Base URL" required>
              <el-input
                v-model="apiSettings.baseUrl"
                placeholder="请输入API服务地址，例如：https://api-inference.modelscope.cn/v1/"
                clearable
              />
              <div class="form-hint">模型服务的API端点地址</div>
            </el-form-item>
            
            <el-form-item>
              <el-button type="primary" @click="saveApiSettings" :loading="savingApi">
                <el-icon>
                  <Download />
                </el-icon>
                保存API设置
              </el-button>
              <el-button @click="resetApiSettings">
                <el-icon>
                  <RefreshRight />
                </el-icon>
                重置API设置
              </el-button>
            </el-form-item>
          </el-form>
          
          <el-divider />
          
          <div class="settings-info">
            <h4>API设置说明</h4>
            <el-timeline>
              <el-timeline-item timestamp="API Key">
                <div>ModelScope或其他VL模型服务的API密钥</div>
              </el-timeline-item>
              <el-timeline-item timestamp="Base URL">
                <div>API服务的基础地址，用于调用模型</div>
              </el-timeline-item>
              <el-timeline-item timestamp="本地模型支持">
                <div>如果使用本地VL模型，可以输入本地服务地址，例如：http://localhost:8081/v1/</div>
              </el-timeline-item>
            </el-timeline>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, RefreshRight } from '@element-plus/icons-vue'

interface ApiSettings {
  apiKey: string
  baseUrl: string
}

const activeTab = ref('api')
const savingApi = ref(false)

const apiSettings = reactive<ApiSettings>({
  apiKey: '',
  baseUrl: 'https://api-inference.modelscope.cn/v1/'
})

const loadApiSettings = () => {
  const savedSettings = localStorage.getItem('appSettings')
  if (savedSettings) {
    const parsed = JSON.parse(savedSettings)
    apiSettings.apiKey = parsed.apiKey || ''
    apiSettings.baseUrl = parsed.baseUrl || 'https://api-inference.modelscope.cn/v1/'
  }
}

const saveApiSettings = () => {
  savingApi.value = true
  setTimeout(() => {
    localStorage.setItem('appSettings', JSON.stringify(apiSettings))
    ElMessage.success('API设置已保存')
    savingApi.value = false
  }, 300)
}

const resetApiSettings = () => {
  apiSettings.apiKey = ''
  apiSettings.baseUrl = 'https://api-inference.modelscope.cn/v1/'
}

onMounted(() => {
  loadApiSettings()
})
</script>

<style scoped>
.settings-container {
  max-width: 800px;
  margin: 0 auto;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.settings-form {
  margin-top: 20px;
}

.form-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 5px;
}

.settings-info {
  margin-top: 20px;
}

.settings-info h4 {
  margin-bottom: 20px;
  font-weight: 600;
}
</style>
