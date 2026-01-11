<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="handleClose"
    title="系统设置"
    width="800px"
    :close-on-click-modal="true"
    :close-on-press-escape="true"
  >
    <div class="settings-layout">
      <!-- 左侧菜单 -->
      <div class="settings-sidebar">
        <el-menu :default-active="activeSettingsTab" class="settings-menu" @select="handleSettingsTabChange">
          <el-menu-item index="api">API设置</el-menu-item>
          <el-menu-item index="dedup">去重参数</el-menu-item>
          <el-menu-item index="caption">提示词模板</el-menu-item>
        </el-menu>
      </div>
      
      <!-- 右侧内容 -->
      <div class="settings-content">
        <ApiSettings v-if="activeSettingsTab === 'api'" @save="settingsSaved" />
        <DedupSettings v-else-if="activeSettingsTab === 'dedup'" @save="settingsSaved" />
        <CaptionSettings v-else @save="settingsSaved" />
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import ApiSettings from './ApiSettings.vue'
import DedupSettings from './DedupSettings.vue'
import CaptionSettings from './CaptionSettings.vue'

defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  save: []
}>()

const activeSettingsTab = ref('api')

const handleSettingsTabChange = (tabIndex: string) => {
  activeSettingsTab.value = tabIndex
}

const handleClose = (value: boolean) => {
  emit('update:visible', value)
}

const settingsSaved = () => {
  emit('save')
}
</script>

<style scoped>
/* 设置页面样式 */
.settings-layout {
  display: flex;
  gap: 20px;
  min-height: 400px;
}
.settings-sidebar {
  width: 200px;
  background-color: var(--panel);
  border-radius: 8px;
  border: 1px solid var(--border);
  overflow: hidden;
}
.settings-menu {
  background-color: transparent;
  border-right: none;
}
.settings-menu :deep(.el-menu-item) {
  background-color: transparent;
  border-radius: 0;
}
.settings-menu :deep(.el-menu-item.is-active) {
  background-color: var(--accent);
  color: white;
}
.settings-content {
  flex: 1;
  overflow-y: auto;
}
</style>
