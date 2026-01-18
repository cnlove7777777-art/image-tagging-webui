# 图片裁切功能修复文档

## 1. 问题根因分析

### 1.1 核心问题
- **问题现象**：红色裁切框未能根据前端返回数据正确渲染百分比位置，始终居中显示
- **根本原因**：后端数据库模型中 `meta_json` 字段使用了普通的 `JSON` 类型，导致"就地修改"的数据无法被SQLAlchemy跟踪，裁切坐标（`crop_square_model/user`）未能正确写入数据库
- **影响范围**：所有使用图片裁切功能的场景，包括模型自动裁切和手动调整裁切框

### 1.2 次要问题
- **模型返回不合理裁切参数**：模型偶尔返回极小的 `side` 值（如 0.05），导致裁切框几乎不可见
- **缺乏裁切参数验证与重试机制**：当模型返回异常结果时，系统没有验证和重试机制
- **裁切输出尺寸固定**：无法灵活配置裁切输出的图片尺寸

## 2. 修复方案

### 2.1 数据库模型修复

**文件**：`backend/app/models/image.py`

**修复前**：
```python
meta_json = Column(JSON, default=dict)
```

**修复后**：
```python
from sqlalchemy.ext.mutable import MutableDict
# ...
meta_json = Column(MutableDict.as_mutable(JSON), default=dict)
```

**原理**：
- 使用 `MutableDict.as_mutable(JSON)` 替代普通的 `JSON` 类型
- 确保每次更新裁切坐标时，SQLAlchemy能够跟踪到变更并将其持久化到数据库
- 解决了"就地修改"无法被跟踪的问题

### 2.2 提示词调整与重试逻辑

**文件**：`backend/app/services/model_client.py`

**修复前**：
```python
prompt = """Analyze this image and identify the main focus point. Return a JSON object with:
- focus_point: {x, y, side} normalized (0-1). side is the square crop ratio based on the short edge.
# ...
```

**修复后**：
```python
prompt = """Analyze this image and identify the main focus point. Return a JSON object with:
- focus_point: {x, y, side} normalized (0-1). side is the square crop ratio based on the short edge.
# ...

Crop rule: choose the LARGEST possible square crop. Prefer side=1.0 (use the full short edge).
Only reduce side if needed to fully include the main subject.
Only return valid JSON, no additional text."""
```

**文件**：`backend/app/tasks/processing.py`

**新增验证与重试逻辑**：
```python
# Model focus retry rules for crop selection.
_MIN_MODEL_CROP_SIDE = 0.9
_MAX_FOCUS_RETRIES = 2

# ...

def _is_focus_result_reasonable(focus_result: dict, image: Image, min_side: float) -> bool:
    # 验证focus_result是否合理的逻辑
    # ...

# ...

# 在crop_task函数中使用重试逻辑
valid = _is_focus_result_reasonable(focus_result, image, _MIN_MODEL_CROP_SIDE)
while not valid and attempt < _MAX_FOCUS_RETRIES:
    attempt += 1
    # 重新请求模型
    focus_result = model_client.get_focus_point(
        image.preview_path or image.orig_path,
        retry_hint=retry_hint,
    )
    valid = _is_focus_result_reasonable(focus_result, image, _MIN_MODEL_CROP_SIDE)
```

**原理**：
- 调整模型提示词，强调"最大化正方形，side接近1.0"
- 增加不合理结果检测机制，当side<0.9或bbox异常时重试2次
- 仍异常则回退到安全值，确保裁切结果始终可用

### 2.3 裁切输出边长可配置

**文件**：`backend/app/core/config.py` 或 `backend/app/services/app_settings.py`

**新增配置项**：
```python
# 新增crop_output_size配置项
crop_output_size = 1024
```

**文件**：`backend/app/services/image_processing.py`

**支持按设置输出**：
```python
def crop_1024_from_original(
    img_path: str,
    cx: float,
    cy: float,
    output_dir: str,
    quality: int = 95,
    side: float = 1.0,
    output_size: int = 1024,
) -> str:
    # 使用output_size参数作为输出尺寸
    # ...
```

**文件**：`backend/app/main.py`

**API支持**：
```python
# 在/api/settings中读写crop_output_size字段
@app.get("/api/settings")
def get_settings():
    # ...
    return {"crop_output_size": app_settings.get("crop_output_size", 1024)}

@app.post("/api/settings")
def update_settings(settings: SettingsUpdate):
    # ...
    if "crop_output_size" in settings:
        app_settings["crop_output_size"] = settings.crop_output_size
    # ...
```

**前端**：
- `ApiSettings.vue` 增加输入项并保存
- `api.ts` 类型补齐

**原理**：
- 新增`crop_output_size`配置项，默认值为1024
- 所有裁切操作都读取该配置项作为输出尺寸
- 支持通过API和前端界面修改输出尺寸

### 2.4 手动裁切功能更新

**文件**：`backend/app/main.py`

**更新手动裁切API**：
```python
@app.post("/api/tasks/{task_id}/images/{image_id}/crop")
def update_crop(
    task_id: int,
    image_id: int,
    crop_data: CropUpdate,
    db: Session = Depends(get_db),
):
    # ...
    app_settings = get_app_settings(db)
    crop_output_size = int(app_settings.get("crop_output_size", 1024) or 1024)
    # 使用crop_output_size参数
    # ...
```

**原理**：
- 手动裁切也会跟随输出尺寸配置
- 确保模型自动裁切和手动调整裁切使用相同的输出尺寸

## 3. 修复效果

### 3.1 核心问题解决
- ✅ 红色裁切框现在能根据数据库中的真实坐标正确渲染
- ✅ 模型自动裁切和手动调整的裁切参数都能正确保存到数据库
- ✅ 前后端数据同步问题得到解决

### 3.2 次要问题解决
- ✅ 模型返回不合理裁切参数的问题通过提示词调整和重试机制得到缓解
- ✅ 裁切输出尺寸现在可以灵活配置，默认1024x1024
- ✅ 手动裁切功能也支持自定义输出尺寸

## 4. 配置说明

### 4.1 主要配置项

| 配置项 | 位置 | 默认值 | 说明 |
|-------|------|-------|------|
| `_MIN_MODEL_CROP_SIDE` | `processing.py` | 0.9 | 模型返回的最小裁切边长比例，可根据需要调整 |
| `_MAX_FOCUS_RETRIES` | `processing.py` | 2 | 模型返回异常结果时的最大重试次数 |
| `crop_output_size` | 系统设置 | 1024 | 裁切输出的图片尺寸（1:1） |

### 4.2 调整建议
- 如果觉得0.9太严格，可以在`processing.py`中调小`_MIN_MODEL_CROP_SIDE`值
- 如果模型仍然经常返回异常结果，可以增加`_MAX_FOCUS_RETRIES`值
- 根据硬件性能和需求，可以调整`crop_output_size`来改变输出图片尺寸

## 5. 使用指南

### 5.1 查看裁切结果
1. 启动前后端服务
2. 上传图片并开始处理
3. 在任务详情页查看图片裁切结果
4. 红色裁切框将正确显示模型或手动调整的裁切位置

### 5.2 调整输出尺寸
1. 进入系统设置页面
2. 在"输出图片分辨率（1:1）"输入框中输入所需尺寸
3. 保存设置
4. 新的裁切任务将使用新的输出尺寸

### 5.3 手动调整裁切框
1. 在任务详情页选择需要调整的图片
2. 拖动红色裁切框调整位置和大小
3. 点击保存按钮
4. 新的裁切参数将正确保存并应用

## 6. 技术细节

### 6.1 数据流向
1. 模型生成裁切参数 → 写入数据库（`meta_json`）
2. 前端读取数据库中的裁切参数 → 渲染红色裁切框
3. 手动调整裁切框 → 更新数据库中的裁切参数
4. 再次读取数据库 → 渲染调整后的裁切框

### 6.2 关键函数

#### `_is_focus_result_reasonable`
- 位置：`processing.py`
- 功能：验证模型返回的裁切结果是否合理
- 参数：`focus_result`（模型返回结果）、`image`（图片对象）、`min_side`（最小边长比例）
- 返回：布尔值，表示结果是否合理

#### `_sanitize_focus_result`
- 位置：`processing.py`
- 功能：清理和修复不合理的裁切结果
- 参数：`focus_result`（模型返回结果）、`min_side`（最小边长比例）
- 返回：修复后的裁切结果

#### `crop_1024_from_original`
- 位置：`image_processing.py`
- 功能：根据裁切参数从原始图片生成裁切图片
- 参数：`img_path`（原始图片路径）、`cx`（中心点x坐标）、`cy`（中心点y坐标）、`output_dir`（输出目录）、`quality`（图片质量）、`side`（边长比例）、`output_size`（输出尺寸）
- 返回：裁切图片的路径

## 7. 兼容性说明

- ✅ 与现有数据兼容，历史数据将自动使用默认配置
- ✅ 与现有API兼容，无需修改前端代码即可使用新功能
- ✅ 支持模型自动裁切和手动调整两种方式
- ✅ 支持不同的输出尺寸配置

## 8. 未来改进方向

1. 增加更多的裁切参数配置选项
2. 优化模型提示词，进一步提高裁切质量
3. 增加批量调整裁切框功能
4. 提供更多的可视化反馈，显示裁切参数的具体数值

## 9. 修复验证

### 9.1 功能验证
- [x] 红色裁切框根据数据库数据正确渲染
- [x] 模型自动裁切参数正确保存
- [x] 手动调整裁切参数正确保存
- [x] 裁切输出尺寸可配置
- [x] 手动裁切跟随输出尺寸配置

### 9.2 边界测试
- [x] 模型返回极小side值时的处理
- [x] 模型返回异常bbox时的处理
- [x] 不同输出尺寸的裁切效果
- [x] 多次调整裁切框的稳定性

---

**修复日期**：2026-01-18
**修复人员**：技术团队
**版本**：1.0