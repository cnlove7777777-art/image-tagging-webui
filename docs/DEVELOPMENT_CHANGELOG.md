# Development Changelog

Branch: `refactor/vision-analysis-schema`

This document records recent development fixes that should be remembered by future agents and maintainers. Keep it short and focused on practical debugging history.

---

## 2026-06-26: Provider model-list tab refresh/crash fix

### Symptom

In the frontend custom model provider settings page, clicking the model-list tabs such as:

- `我的收藏`
- `自定义`
- `动态查询`

caused the page to refresh or appear to crash/exit the settings page.

### Root cause

The latest frontend version implemented the model-list tabs using native HTML `<button>` elements inside an `el-form`.

Native `<button>` defaults to `type="submit"`. Because these buttons were placed inside a form, clicking a tab triggered form submission and caused a full-page reload.

Problematic pattern:

```vue
<el-form>
  <button @click="modelTab = 'favorites'">我的收藏</button>
  <button @click="modelTab = 'custom'">自定义</button>
  <button @click="modelTab = 'dynamic'">动态查询</button>
</el-form>
```

### Fix

`frontend/src/components/ApiSettings.vue` was updated to:

- replace native tab buttons with Element Plus `el-tabs` / `el-tab-pane`;
- add `@submit.prevent` to settings forms;
- ensure operation buttons use explicit non-submit behavior;
- preserve all provider manager functions:
  - provider add/edit/delete;
  - save provider;
  - connectivity test;
  - dynamic model query;
  - favorite models;
  - custom model list.

### Guardrail

Do not use native submit-capable `<button>` elements inside settings forms. Prefer:

```vue
<el-button native-type="button" @click="...">操作</el-button>
```

or avoid form nesting for tab-like UI.

---

## 2026-06-26: Model provider manager architecture

### Current behavior

The frontend can configure model providers through `ApiSettings.vue`, but secrets are saved on the backend only.

Frontend supports:

- add custom provider;
- delete runtime provider;
- edit display name / Base URL / API Key / model list path;
- edit default vision/focus/tag model;
- manually maintain model list;
- dynamically query provider model list;
- test connectivity.

Backend endpoints:

```text
POST   /api/models/providers
DELETE /api/models/providers/{provider_id}
GET    /api/models/providers/{provider_id}/runtime-config
POST   /api/models/providers/{provider_id}/runtime-config
POST   /api/models/providers/{provider_id}/test
GET    /api/models?refresh=true
```

Runtime secrets are stored in:

```text
backend/data/runtime/model_provider_secrets.json
```

This file must stay ignored and must never be committed.

---

## 2026-06-26: Upload archive safety patch

### Current behavior

A runtime patch was added in:

```text
backend/sitecustomize.py
```

It wraps `zipfile.ZipFile.extract()` to harden legacy ZIP extraction in `processing.py`.

It currently handles:

- path traversal rejection;
- absolute path rejection;
- Windows drive path rejection;
- mixed slash normalization;
- unsafe Windows filename character replacement;
- best-effort GBK recovery for legacy Chinese Windows ZIP filenames.

### Follow-up

This is a pragmatic patch. When `processing.py` is refactored, replace it with an explicit helper such as:

```text
safe_extract_zip(zip_path, output_dir) -> list[Path]
```

Avoid leaving archive safety as an implicit monkey patch forever.

---

## Pending cleanup

### Vite cache files

The branch currently shows accidentally committed Vite cache files:

```text
.vite/deps/_metadata.json
.vite/deps/package.json
```

They should be removed from Git and `.vite/` should be added to `.gitignore` if missing.

### Provider task integration

Provider manager exists, but task creation still needs to be fully integrated with provider selection:

- remove legacy frontend/headers/form API key override paths from backend task creation;
- add explicit `provider` field to task creation;
- store provider id in `task.config` or schema;
- use `ModelClient.from_provider()` in processing tasks.

### Vision pipeline

Still not complete:

- add `vision_analyze_task()`;
- add `POST /api/tasks/{task_id}/analyze`;
- write `image.meta_json["vision"]`;
- make `crop_task()` prefer `vision.crop_square`;
- expose `vision` in `_image_summary()`;
- show vision metadata in `TaskList.vue`.
