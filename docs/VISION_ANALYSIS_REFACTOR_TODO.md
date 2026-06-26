# Vision Analysis Refactor TODO

Branch: `refactor/vision-analysis-schema`

## Goal

Upgrade the project from a crop-only / traditional-CV-assisted workflow to a backend-owned visual metadata workflow:

```text
prepare -> vision_analyze -> semantic_dedup -> crop -> caption
```

The target behavior is explicit: **one VLM image analysis call should produce the crop square plus key visual facts**, including composition, face/head visibility, pose, shot type, usable/training value, confidence, and reason. Later dedup/crop/caption stages should consume this cached `vision` result instead of repeatedly guessing from legacy fields.

Current reality: the branch has the provider manager, VLM analysis client, metadata normalization helpers, semantic dedup helpers, and frontend type support, but the main processing chain still primarily runs the old `dedup_people.py -> crop_task/get_focus_point()` path. This is why current cards may still show legacy fields such as `占比: - / 人脸: 无 / 可用: 是`.

## P0: Current bug/UX stabilization

- [x] Repair known mojibake log fragments on frontend display in `getLogs()`.
- [x] Repair known mojibake log fragments on new backend `Log(...)` writes.
- [x] Normalize task image summaries in `api.ts` so frontend cards can consume `meta_json.vision`, `meta_json.focus`, or legacy dedup metadata.
- [x] Fix provider model-list tab refresh/crash bug by replacing native form buttons with `el-tabs` and adding `@submit.prevent`.
- [x] Persist favorite model data across page refresh by storing model id + label/tasks, not id only.
- [ ] Investigate remaining “查看详情后空白页” with browser console stack trace.
- [ ] Add a defensive Vue error boundary / fallback block around the task detail dialog so one bad image record does not blank the whole page.
- [ ] Replace old dedup result labels with wording that makes pipeline state clear, for example: `传统去重结果` vs `视觉分析结果`.

## P0.1: Model provider manager

- [x] Add `config/model_providers.yml`.
- [x] Add `backend/app/core/model_providers.py`.
- [x] Add ModelScope provider config.
- [x] Add Alibaba Cloud DashScope provider config.
- [x] Add optional OpenAI-compatible provider placeholder.
- [x] Change `/api/models` to return provider-driven model lists.
- [x] Add runtime provider config storage: `backend/data/runtime/model_provider_secrets.json`.
- [x] Add frontend model provider manager UI in `ApiSettings.vue`.
- [x] Allow frontend to add/edit/delete custom providers.
- [x] Allow frontend to submit Base URL / API Key / model list to backend runtime storage.
- [x] Never store API keys in localStorage.
- [x] Never return full API keys to frontend; return only masked status.
- [x] Add provider connectivity test endpoint: `POST /api/models/providers/{provider_id}/test`.
- [x] Add dynamic model list refresh through `/api/models?refresh=true`.
- [ ] Remove backend acceptance of `api_key`, `base_url`, `X-Ext-Api-Key`, `X-Ext-Base-Url` from task creation endpoints.
- [ ] Add explicit `provider` field to task creation.
- [ ] Store provider id in task config or schema.
- [ ] Use `ModelClient.from_provider()` from processing tasks instead of task-level raw API key/base URL.
- [ ] Remove accidentally committed Vite cache files under `.vite/deps/` and add `.vite/` to `.gitignore` if missing.

## P0.5: Upload / archive reliability

- [x] Add `backend/sitecustomize.py` safe ZIP extraction patch.
- [x] Reject unsafe ZIP paths such as `../evil.jpg`, absolute paths, and Windows drive paths.
- [x] Normalize mixed ZIP slashes and unsafe Windows path characters.
- [x] Add best-effort GBK filename recovery for legacy Chinese Windows ZIP archives.
- [x] Add CI smoke test for safe ZIP extraction.
- [ ] Replace runtime monkey patch with explicit `safe_extract_zip()` inside `processing.py` when the large pipeline file is refactored.
- [ ] Validate ZIP file extension and duplicate queue items in `Upload.vue`.
- [ ] Improve backend error messages for empty ZIP, bad ZIP, and ZIP with no supported images.

## P1: Structured VLM analysis — required next milestone

This is the real architecture switch. Do not keep improving only the old `dedup_people.py` display as if it were the final pipeline.

- [x] Add `ModelClient.analyze_image()`.
- [x] Preserve `get_focus_point()` as a compatibility wrapper.
- [x] Add strict JSON prompt for crop + pose + scene + color + training value.
- [x] Add JSON response parsing and coordinate sanitization.
- [x] Add shared `vision_metadata` normalization helpers.
- [x] Add frontend TypeScript types for `vision` metadata.
- [x] Add backend task stage enum: `vision_analysis`.
- [x] Make frontend `getTaskImages()` merge `meta_json.vision` into displayed card fields when available.
- [ ] Add `vision_analyze_task(task_id, auto_continue=False)` in `backend/app/tasks/processing.py`.
- [ ] Add API endpoint: `POST /api/tasks/{task_id}/analyze`.
- [ ] Add frontend API client: `triggerAnalyze(taskId)`.
- [ ] Add an `Analyze / 视觉分析` button in `TaskList.vue` before dedup/crop.
- [ ] Write raw and normalized VLM result into `image.meta_json["vision"]`.
- [ ] Mirror `vision.crop_square` into `crop_square_model`.
- [ ] Mirror `vision.subject_bbox` into `subject_area_ratio` fallback.
- [ ] Mirror `vision.head_bbox` / `vision.face_occlusion` into face visibility display.
- [ ] Mirror `vision.shot_type`, `vision.pose_family`, `vision.confidence`, `vision.usable`, `vision.training_value` into summary fields.
- [ ] Update backend `_image_summary()` to return a top-level `vision` field.
- [ ] Change `crop_task()` to prefer `vision.crop_square` before calling VLM again.
- [ ] Update `run_full_pipeline()` to run `vision_analyze_task()` before semantic dedup and crop.
- [ ] Keep `get_focus_point()` fallback for old tasks or failed analysis only.

## P2: Semantic de-duplication

- [x] Add `backend/app/services/semantic_dedup.py`.
- [x] Add conservative `semantic_similarity()` scoring based on framing, pose signature, viewpoint, occlusion, and subject bbox.
- [x] Add representative selection helper based on training value and confidence.
- [ ] Add `semantic_dedup_task()` or integrate semantic scoring into `dedup_task()` after `vision_analyze_task()`.
- [ ] Output `cluster_id`, `similarity_score`, and `similarity_reasons` into image metadata.
- [ ] Keep the best 2-3 images per cluster by training value, confidence, sharpness, crop completeness, and pose diversity.
- [ ] Keep existing `dedup_people.py` as fallback / prefilter, not as the final semantic dedup source of truth.
- [ ] Make the UI label old results as traditional CV dedup when `vision` is missing.

## P3: Frontend inspection UI

- [x] Convert old API settings panel into a provider manager style UI.
- [x] Add provider add/edit/delete controls.
- [x] Add connectivity test button.
- [x] Add manual model list editor.
- [x] Fix model-list tab click refresh/crash in `ApiSettings.vue`.
- [x] Persist favorite models across refresh.
- [x] Normalize image card fields from `meta_json.vision` when available.
- [ ] Show visual metadata in task detail image cards:
  - shot type
  - body visibility
  - pose family
  - view angle
  - expression
  - occlusion
  - environment
  - colors
  - skin exposure / outfit coverage
  - training value
- [ ] Add filters by vision fields.
- [ ] Show duplicate cluster id and duplicate reasons.
- [ ] Add an "Analyze" button before Crop.
- [ ] Fix remaining `Upload.vue` mojibake messages.
- [ ] Add `vision_analysis` to `TaskList.vue` stage filters and tag rendering.
- [ ] Fix visual-only pagination in `TaskList.vue`.

## P4: CI and tests

- [x] Add `.github/workflows/ci.yml`.
- [x] Frontend CI: `npm ci && npm run build`.
- [x] Backend CI: `compileall` + provider config load check.
- [x] Add CI smoke checks for vision normalization and semantic similarity.
- [x] Add CI smoke check for safe ZIP extraction.
- [ ] Add pytest.
- [ ] Add unit tests for provider config parsing.
- [ ] Add unit tests for vision JSON sanitization.
- [ ] Add unit tests for semantic similarity scoring.
- [ ] Add unit tests for archive extraction edge cases.
- [ ] Add frontend regression test or smoke checklist for provider settings tabs, favorite persistence, and task detail dialog open.

## Notes

- DashScope model list fetching is implemented as optional OpenAI-compatible `GET {base_url}/models`. If Alibaba Cloud changes or restricts that endpoint, the yml/static model list remains the fallback.
- Runtime provider secrets are stored in `backend/data/runtime/model_provider_secrets.json`, which is ignored through `backend/data/` and must never be committed.
- The current branch has not yet completed the processing pipeline rewrite. It is safe as a partial refactor branch, not yet ready to merge into `main`.
- `processing.py` and `main.py` are large legacy files. Continue by changing them in small, reviewable commits rather than one full-file rewrite.
- `backend/sitecustomize.py` is a pragmatic safety patch for ZIP extraction. Prefer replacing it with an explicit helper when touching `processing.py` deeply.
- Avoid native submit-capable `<button>` elements inside settings forms. Use Element Plus components, `native-type="button"`, or `@submit.prevent` to prevent accidental full-page refreshes.
- Do not treat `face_conf=0` from the old traditional CV path as proof that the image has no face. The intended source of truth should become `vision.head_bbox` / `vision.face_occlusion` from VLM analysis.
