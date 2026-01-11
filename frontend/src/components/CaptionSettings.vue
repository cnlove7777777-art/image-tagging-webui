<template>
  <div class="settings-section">
    <el-form label-width="120px">
      <el-form-item label="提示词模板">
        <el-input
          v-model="captionPrompt"
          type="textarea"
          :rows="10"
          resize="vertical"
          placeholder="请输入提示词模板"
        />
        <div class="form-hint">
          保存后将作为打标提示词模板写入数据库，并用于后续提示词生成。
        </div>
      </el-form-item>
    </el-form>
    <div class="dialog-footer">
      <el-button :loading="loading" @click="resetPrompt">恢复默认</el-button>
      <el-button type="primary" :loading="loading" @click="savePrompt">保存提示词模板</el-button>
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

const defaultPrompt = `Generate a training caption for a photo-realistic portrait / cosplay photoshoot.
Comma-separated short phrases in this exact order:
subject (female model, count),
face & body features,
hair (style/color/length),
makeup & expression (makeup style, micro-expression, gaze direction/target, mouth state),
outfit (color/material/style),
accessories,
pose & action (body orientation, weight on which leg, head tilt, shoulder/hip angle, hand placement + finger shape, action verb + interaction target),
setting/background,
lighting (type, direction, softness, catchlights),
composition & camera (shot, angle, focus point, lens/aperture vibe),
mood & color tone.
English first, allow a few Chinese phrases when helpful ("日系写真", "窗边柔光", "干净背景").
Rules: be specific; omit unknown; no vague words; no meta words.
Keep under 200 words.
End with: tags: ... (10–25 tags, photography/lighting/lens/style focused)`

const captionPrompt = ref(defaultPrompt)
const loading = ref(false)

const loadPrompt = async () => {
  try {
    const settings = await getProcessingSettings()
    if (settings?.caption_prompt) {
      captionPrompt.value = settings.caption_prompt
    }
  } catch (error) {
    console.error('Failed to load caption prompt', error)
  }
}

const savePrompt = async () => {
  loading.value = true
  try {
    await updateProcessingSettings({ caption_prompt: captionPrompt.value })
    emit('save')
    ElMessage.success('已保存提示词模板')
  } catch (error) {
    console.error(error)
    ElMessage.error('保存提示词模板失败')
  } finally {
    loading.value = false
  }
}

const resetPrompt = async () => {
  captionPrompt.value = defaultPrompt
  await savePrompt()
}

onMounted(() => {
  loadPrompt()
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
