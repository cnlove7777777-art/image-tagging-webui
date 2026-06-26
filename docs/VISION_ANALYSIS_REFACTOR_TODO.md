# Vision Analysis Refactor TODO

Branch: `refactor/vision-analysis-schema`

## Goal

Upgrade the project from a crop-only VLM workflow to a backend-owned visual metadata workflow:

```text
prepare -> vision_analyze -> semantic_dedup -> crop -> caption
```

The VLM should output crop coordinates plus structured metadata for pose, framing, expression, occlusion, scene, color, and training value. Backend code validates/caches the result and uses it for crop execution and semantic de-duplication.

## P0: Model provider manager

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
- [x] Fix provider model-list tab refresh/crash bug by replacing native form buttons with `el-tabs` and adding `@submit.prevent`.
- [ ] Remove backend acceptance of `api_key`, `base_url`, `X-Ext-Api-Key`, `X-Ext-Base-Url` from task creation endpoints.
- [ ] Add explicit `provider` field to task creation.
- [ ] Store provider id in task config or schema.
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

## P1: Structured VLM analysis

- [x] Add `ModelClient.analyze_image()`.
- [x] Preserve `get_focus_point()` as a compatibility wrapper.
- [x] Add strict JSON prompt for crop + pose + scene + color + training value.
- [x] Add JSON response parsing and coordinate sanitization.
- [x] Add shared `vision_metadata` normalization helpers.
- [x] Add frontend TypeScript types for `vision` metadata.
- [x] Add backend task stage enum: `vision_analysis`.
- [ ] Add `vision_analyze_task()` in `backend/app/tasks/processing.py`.
- [ ] Add API endpoint: `POST /api/tasks/{task_id}/analyze`.
- [ ] Write `image.meta_json["vision"]`.
- [ ] Mirror `vision.crop_square` into `crop_square_model`.
- [ ] Mirror `vision.shot_type`, `vision.confidence`, `vision.usable` into summary fields.
- [ ] Update `_image_summary()` to return `vision`.
- [ ] Change `crop_task()` to prefer `vision.crop_square` before calling VLM again.

## P2: Semantic de-duplication

- [x] Add `backend/app/services/semantic_dedup.py`.
- [x] Add conservative `semantic_similarity()` scoring based on framing, pose signature, viewpoint, occlusion, and subject bbox.
- [x] Add representative selection helper based on training value and confidence.
- [ ] Output `cluster_id`, `similarity_score`, and `similarity_reasons` into image metadata.
- [ ] Keep the best 2-3 images per cluster by training value, confidence, sharpness, and crop completeness.
- [ ] Keep existing `dedup_people.py` as fallback / prefilter.

## P3: Frontend inspection UI

- [x] Convert old API settings panel into a provider manager style UI.
- [x] Add provider add/edit/delete controls.
- [x] Add connectivity test button.
- [x] Add manual model list editor.
- [x] Fix model-list tab click refresh/crash in `ApiSettings.vue`.
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
- [ ] Add frontend regression test or smoke checklist for provider settings tabs.

## Notes

- DashScope model list fetching is implemented as optional OpenAI-compatible `GET {base_url}/models`. If Alibaba Cloud changes or restricts that endpoint, the yml/static model list remains the fallback.
- Runtime provider secrets are stored in `backend/data/runtime/model_provider_secrets.json`, which is ignored through `backend/data/` and must never be committed.
- The current branch has not yet completed the processing pipeline rewrite. It is safe as a partial refactor branch, not yet ready to merge into `main`.
- `processing.py` and `main.py` are large legacy files. Continue by changing them in small, reviewable commits rather than one full-file rewrite.
- `backend/sitecustomize.py` is a pragmatic safety patch for ZIP extraction. Prefer replacing it with an explicit helper when touching `processing.py` deeply.
- Avoid native submit-capable `<button>` elements inside settings forms. Use Element Plus components, `native-type="button"`, or `@submit.prevent` to prevent accidental full-page refreshes.
