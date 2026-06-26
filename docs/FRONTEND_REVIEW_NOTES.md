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
  - Renamed the old `API设置` tab to `模型服务`, because provider configuration is now a backend-managed model service panel.
  - Removed stale comments.

- `ApiSettings.vue`
  - Reworked the page into a backend-provider model service panel.
  - Added provider dropdown, so users can inspect providers such as Alibaba Cloud DashScope, ModelScope, and OpenAI-compatible services.
  - Added provider configured/missing-key status.
  - Added Base URL / API Key / default model fields that submit to backend runtime config endpoints.
  - Added model list display for the selected provider.
  - Added `查询可用模型` action, which calls `/api/models?refresh=true` through `getModels(true)`.
  - API Key is never stored in localStorage and never committed to Git. The backend returns only masked key status.

- `api.ts`
  - Added `getProviderRuntimeConfig()` and `saveProviderRuntimeConfig()`.
  - Still does not attach model secrets to upload/task requests.

- Previously fixed in this branch
  - `task.ts`: added `VisionMetadata` types.

## Backend-saved provider config behavior

Frontend now saves model service settings to backend endpoints:

```text
GET  /api/models/providers/{provider_id}/runtime-config
POST /api/models/providers/{provider_id}/runtime-config
```

Backend stores runtime secrets in:

```text
backend/data/runtime/model_provider_secrets.json
```

This path is covered by `.gitignore` through `backend/data/`, so runtime secrets do not enter the repository.

The API response uses masked key fields only:

```json
{
  "provider_id": "aliyun_dashscope",
  "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
  "api_key_masked": "sk-x...abcd",
  "has_api_key": true
}
```

## Dynamic model list behavior

`查询可用模型` now calls `getModels(true)`. Backend behavior is:

1. Read static provider config from `config/model_providers.yml`.
2. Apply backend runtime overrides from `backend/data/runtime/model_provider_secrets.json`.
3. For providers with `dynamic_model_list: true`, try `GET {base_url}/{model_list_path}` with the backend-held API key.
4. If the provider endpoint fails, is unsupported, or the key is missing, keep the static yml model list.

This means Alibaba Cloud DashScope can be configured as:

```yaml
aliyun_dashscope:
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
  api_key_env: "DASHSCOPE_API_KEY"
  dynamic_model_list: true
  model_list_path: "/models"
```

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

- Do not commit real API keys or `backend/data/runtime/model_provider_secrets.json`.
- Do not put provider API keys in localStorage.
- Do not attach model secrets to upload/task requests.
- Keep frontend model selection limited to public provider/model metadata from `/api/models`.
- Keep vision metadata display read-only until backend schema stabilizes.
