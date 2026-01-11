<template>
  <div class="task-progress-cell">
    <div class="progress-row">
      <el-progress :percentage="overallPercent" :stroke-width="6" :show-text="false" />
      <span class="progress-text">{{ stageIndex }}/{{ stageTotal }}</span>
    </div>
    <div class="progress-row">
      <el-progress :percentage="stagePercent" :stroke-width="6" :show-text="false" status="success" />
      <span class="progress-text">{{ Math.round(stagePercent) }}%</span>
    </div>
    <div class="hint" v-if="stageName || stepHint">
      <span class="stage">{{ stageName }}</span>
      <span class="step" v-if="stepHint">· {{ stepHint }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { defineProps } from 'vue'

defineProps<{
  overallPercent: number
  stageIndex: number
  stageTotal: number
  stagePercent: number
  stageName?: string
  stepHint?: string
}>()
</script>

<style scoped>
.task-progress-cell {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 56px;
}

.progress-row {
  display: grid;
  grid-template-columns: 1fr 48px;
  align-items: center;
  gap: 8px;
}

.progress-text {
  font-size: 12px;
  color: var(--muted, #909399);
  text-align: right;
  min-width: 42px;
}

.hint {
  font-size: 12px;
  color: var(--muted, #909399);
  line-height: 16px;
}

.stage {
  font-weight: 600;
}
</style>
