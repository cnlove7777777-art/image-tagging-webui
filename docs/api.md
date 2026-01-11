# API 文档（本地概要）

## 任务
- `POST /api/tasks` 上传单个 zip，Form：file、focus_model、tag_model，可选 header：`X-Ext-Base-Url`、`X-Ext-Api-Key`、`X-Ext-Models`。返回 TaskResponse。
- `POST /api/tasks/batch` 上传多个 zip，字段同上，返回 [{id, zip_name}].
- `GET /api/tasks` 列表，包含每个任务的 progress_detail、export_ready、items 摘要（预览/裁切 URL、keep、subject_area_ratio、has_face/pose、quality 等）。
- `GET /api/tasks/{id}` 单个任务详情，字段同上。
- `GET /api/tasks/{id}/images` 查询图片（可选 ?selected，include_prompt=true 读 txt），返回 TaskImage（preview_url、crop_url、subject_area_ratio、has_face/pose、width/height、quality、crop_square_model/user、decision、prompt_text）。
- `POST /api/tasks/{id}/images/select` {image_ids, selected} 批量保留/丢弃。
- `POST /api/tasks/{id}/items/{item_id}/decision` {keep} 单张保留/丢弃。
- `POST /api/tasks/{id}/items/{item_id}/crop` {crop_square:{cx,cy,side}, source:"user"} 更新裁切，生成新 crop。
- `POST /api/tasks/{id}/dedup` 启动去重。
- `POST /api/tasks/{id}/crop` 启动裁切。
- `POST /api/tasks/{id}/caption` 启动提示词。
- `POST /api/tasks/{id}/run-all` 一键流程。
- `GET /api/tasks/{id}/download` 下载导出包。
- `DELETE /api/tasks/{id}` 删除任务（数据库 + 本地 ./data/tasks/{id}）。
- `GET /api/tasks/{id}/events` SSE 进度推送。

## 设置
- `POST /api/settings/test` 校验自定义 header 是否收到。headers: `X-Ext-Base-Url`、`X-Ext-Api-Key`、`X-Ext-Models`。

## 数据字段（关键）
- `TaskResponse.progress_detail`: {overall_percent, stage_index, stage_total=4, stage_name, stage_percent, step_hint}
- `TaskImage`/items 摘要关键字段：
  - `preview_url`、`crop_url`
  - `width`、`height`
  - `subject_area_ratio`（来源：focus bbox；回退：skeleton 包围盒）
  - `has_face`（focus bbox 或 meta.has_face）、`face_conf`
  - `has_pose`（skeleton 是否存在）、`pose_conf`
  - `quality`: {usable, reject_reason}
  - `crop_square_model`、`crop_square_user`
  - `decision`: {keep}
  - `prompt_text`（include_prompt=true 时返回）

## 依赖
- mediapipe、opencv-python 已在运行环境中检查可导入（用于骨架与姿态）。

## 删除一致性
- `DELETE /api/tasks/{id}` 同步删除数据库记录（Task/Images/Logs）及本地目录 `./data/tasks/{id}`。
- 前端在删除后调用 `loadTasks(true)` 即刻刷新列表。

