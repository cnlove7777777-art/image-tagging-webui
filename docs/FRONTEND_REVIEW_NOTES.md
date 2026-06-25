# Frontend Review Notes

Branch: `refactor/vision-analysis-schema`

## Review scope

Reviewed frontend areas affected by the backend-provider and vision-analysis refactor:

- `frontend/src/App.vue`
- `frontend/src/components/SettingsDialog.vue`
- `frontend/src/components/ApiSettings.vue`
- `frontend/src/services/api.ts`
- `frontend/src/types/task.ts`
- `frontend/src/views/Upload.vue`
- `frontend/src/views/TaskList.vue`

## Fixed in this pass

- `App.vue`
  - Removed stale localStorage dedup settings state that was no longer used by the app shell.
  - Removed mojibake comments from the old settings styles.
  - Updated the topbar subtitle to match the new structured visual analysis direction.
  - Kept theme switching, sidebar task list, route syncing, and refresh timer behavior.

- `SettingsDialog.vue`
  - Renamed the old `API设置` tab to `模型服务`, because API Key / Base URL are now backend-owned provider settings.
  - Removed stale comments.

- Previously fixed in this branch
  - `ApiSettings.vue`: removed API Key / Base URL input fields and now displays backend provider status.
  - `api.ts`: stopped sending `X-Ext-Api-Key`, `X-Ext-Base-Url`, `X-Ext-Models`, `api_key`, and `base_url` from the frontend.
  - `task.ts`: added `VisionMetadata` types.

## Remaining frontend issues

### P0: Upload.vue mojibake messages

`frontend/src/views/Upload.vue` still has two mojibake strings in `saveReviewChanges()`:

```ts
ElMessage.success('宸蹭繚瀛橀€夋嫨')
ElMessage.error('淇濆瓨澶辫触')
```

Expected replacement:

```ts
ElMessage.success('已保存选择')
ElMessage.error('保存失败')
```

This should be fixed in a small commit together with any other remaining Chinese text cleanup.

### P0: TaskList.vue stage options need vision_analysis

`TaskStage` now includes `vision_analysis`, but `TaskList.vue` stage filter and tag color logic do not yet include it.

Add:

```ts
{ label: '视觉分析', value: 'vision_analysis' }
```

and map `vision_analysis` to a visible tag type, probably `primary` or `success`.

### P1: TaskList.vue table pagination is visual only

The table currently uses `filteredTasks` directly while pagination exists below the table. This means pagination controls may not actually limit rows.

Recommended fix:

```ts
const pagedTasks = computed(() => {
  const start = (pagination.value.currentPage - 1) * pagination.value.pageSize
  return filteredTasks.value.slice(start, start + pagination.value.pageSize)
})
```

Then bind table data to `pagedTasks` instead of `filteredTasks`.

### P1: Upload.vue should display backend provider status

Upload page still shows only focus/tag model selects. After provider config is fully connected, it should display:

- current default provider
- provider configured / missing key warning
- selected model task support

### P1: TaskList.vue should display vision metadata

After backend `_image_summary()` returns `vision`, display image metadata cards:

- shot type
- body visibility
- pose family
- view angle
- expression
- occlusion
- environment
- dominant colors
- training value

### P2: Add Analyze action

After backend adds `POST /api/tasks/{task_id}/analyze`, add:

- task card button: `视觉分析`
- detail dialog button: `视觉分析`
- disabled state when task is processing
- tooltip if analysis is unavailable

## Do not regress

- Do not reintroduce frontend API Key / Base URL forms.
- Do not send model secrets from `api.ts`.
- Keep frontend model selection limited to public provider/model metadata from `/api/models`.
- Keep vision metadata display read-only until backend schema stabilizes.
