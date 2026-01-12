# LoRA 写真数据集自动构建平台

一个既能本地运行（强隐私/省带宽），又能作为网站提供 UI 的 LoRA 写真数据集自动构建平台。
目前后端写的是我自己的模搭社区的apikey，大家测试一下然后写自己的就行了（乐）
前端设置或者后端写死都可以，开发者有每天两千次的免费调用，但是限额每个模型最多五百次，所以我写了一个满额自己切换的功能。

## 功能特性

### 核心功能
- **自动处理流程**：解压 -> 去重 -> 压缩预览 -> 调用 VL 取核心点 -> 用原图裁 1024 -> 最终打标 -> 打包
- **支持超高分辨率图片**：处理长边 3000~4000+ 像素甚至 4000 万像素的图片
- **多种运行模式**：本地 CLI 和 Web UI 两种方式
- **隐私保护**：本地模式无需上传原图到服务器
- **实时进度**：Web 模式支持 SSE 实时推送任务进度

### 本地 CLI 模式
- 支持完整的处理流程
- 详细的日志输出
- 灵活的配置参数
- 支持批量处理

### Web UI 模式
- Vue 前端：支持多选 zip 和文件夹选择
- FastAPI 后端：任务管理、进度展示、结果预览、下载
- 支持两种上传方式：原始 zip 和准备好的 1024 数据集 zip

## 目录结构

```
lora-dataset-builder/
├── backend/                 # FastAPI后端
│   ├── app/                 # 应用代码
│   ├── Dockerfile           # Docker构建文件
│   ├── requirements.txt     # 依赖列表
│   └── .env.example         # 环境变量示例
├── frontend/                # Vue前端
│   ├── src/                 # 应用代码
│   ├── Dockerfile           # Docker构建文件
│   ├── package.json         # 依赖列表
│   └── nginx.conf           # Nginx配置
├── client/                  # 本地Python CLI
│   ├── src/                 # 应用代码
│   ├── requirements.txt     # 依赖列表
│   └── setup.py             # 安装配置
├── docker-compose.yml       # Docker Compose配置
└── README.md                # 项目说明
```

## 快速开始

### 本地 CLI 模式

#### 安装依赖

```bash
cd client
pip install -r requirements.txt
pip install -e .
```

#### 设置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，设置 MODELSCOPE_TOKEN
```

#### 运行命令

1. **准备文件夹**：解压、去重、生成预览
   ```bash
   lora-dataset-builder prepare-folder --input input_root --output prepared_root
   ```

2. **焦点检测**：调用 VL 模型获取核心点
   ```bash
   lora-dataset-builder focus --prepared prepared_root
   ```

3. **裁剪 1024**：用原图按核心点裁 1024x1024
   ```bash
   lora-dataset-builder crop1024 --prepared prepared_root
   ```

4. **生成标签**：调用 VL 模型生成标签
   ```bash
   lora-dataset-builder tag --prepared prepared_root
   ```

5. **打包**：生成最终的 train_package.zip
   ```bash
   lora-dataset-builder pack --prepared prepared_root --output output_root
   ```

6. **执行完整流程**：依次执行以上所有步骤
   ```bash
   lora-dataset-builder run-all --input input_root --output output_root
   ```

### Web UI 模式

#### 环境变量配置

1. **后端配置**
   ```bash
   cd backend
   cp .env.example .env
   # 编辑 .env 文件，设置 MODELSCOPE_TOKEN 等参数
   ```

2. **前端配置**
   ```bash
   cd frontend
   cp .env.example .env
   # 编辑 .env 文件，设置 API 地址等参数
   ```

#### 运行服务

使用 Docker Compose 启动所有服务：

```bash
docker-compose up -d
```

服务启动后：
- 前端访问：http://localhost:8080
- 后端 API：http://localhost:8081/api
- Redis：http://localhost:6379

端口配置写在 `config/ports.json`，前后端启动时会读取该文件并强制使用其中的端口（含 Redis 端口）。

#### 使用 Web UI

1. 打开浏览器访问 http://localhost:8080
2. 选择上传方式：
   - 选择多个 zip 文件
   - 选择一个文件夹，系统会自动过滤其中的 .zip 文件
3. 填写模型参数（可选，默认值已填充）
4. 点击上传，查看任务进度
5. 任务完成后，下载生成的 train_package.zip

## 环境变量配置

### 后端环境变量

| 变量名 | 描述 | 默认值 |
|-------|------|-------|
| DATABASE_URL | 数据库连接字符串 | sqlite:///./data/db.sqlite3 |
| REDIS_URL | Redis 连接字符串 | redis://localhost:6379/0 |
| MODELSCOPE_TOKEN | ModelScope API 令牌 | - |
| BASE_URL | ModelScope API 地址 | https://api-inference.modelscope.cn/v1/ |
| FOCUS_MODEL | 焦点检测模型 | Qwen/Qwen3-VL-30B-A3B-Instruct |
| TAG_MODEL | 打标模型 | Qwen/Qwen3-VL-235B-A22B-Instruct |
| FALLBACK_MODEL | 回退模型 | Qwen/Qwen3-VL-32B-Instruct |
| MAX_UPLOAD_MB | 最大上传大小（MB） | 2048 |
| PHASH_THRESHOLD | pHash 聚类阈值 | 6 |
| KEEP_PER_CLUSTER | 每簇保留图片数量 | 2 |
| PREVIEW_MAX_SIDE | 预览图最大边长 | 1200 |
| PREVIEW_JPEG_QUALITY | 预览图质量 | 86 |
| MAX_IMAGE_PIXELS | 最大图片像素 | 1000000000 |

### 本地 CLI 环境变量

| 变量名 | 描述 | 默认值 |
|-------|------|-------|
| MODELSCOPE_TOKEN | ModelScope API 令牌 | - |
| BASE_URL | ModelScope API 地址 | https://api-inference.modelscope.cn/v1/ |

## 核心 API

### 任务管理

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/tasks | 创建单个任务 |
| POST | /api/tasks/batch | 批量创建任务 |
| GET | /api/tasks | 获取所有任务 |
| GET | /api/tasks/{id} | 获取单个任务详情 |
| GET | /api/tasks/{id}/images | 获取任务图片列表 |
| GET | /api/tasks/{id}/download | 下载任务结果 |
| GET | /api/tasks/{id}/events | SSE 实时进度 |

## 技术栈

### 后端
- FastAPI
- Celery + Redis
- SQLAlchemy 2.x
- SQLite（默认）/ Postgres
- Pillow + numpy + imagehash
- OpenAI SDK（兼容 ModelScope API）

### 前端
- Vue3 + Vite + TS
- Element Plus
- Vue Router
- Axios

### 本地 CLI
- Python
- Typer
- Pillow + numpy + imagehash
- OpenAI SDK

### 部署
- Docker + Docker Compose
- Nginx

## 常见问题

### 1. 如何处理超大图片？

平台已经对超大图片做了优化：
- 任何阶段都不会一次性把所有图片读入内存
- pHash/清晰度计算只对缩略图做
- Pillow 的 MAX_IMAGE_PIXELS 可通过环境变量配置
- 采用流式处理，逐张处理图片

### 2. 如何提高处理速度？

- 本地模式比 Web 模式快，因为无需网络传输
- 可以调整并发数（Web 模式）
- 可以使用更强大的硬件

### 3. 如何处理模型调用失败？

- 平台会自动重试 5 次，每次间隔指数增长
- 如果连续失败，会使用回退模型
- 详细的错误日志会记录到数据库

### 4. 如何保护隐私？

- 推荐使用本地 CLI 模式，无需上传原图
- Web 模式支持上传准备好的 1024 数据集 zip，无需上传原图

### 5. 如何调整处理参数？

- 本地模式：通过命令行参数调整
- Web 模式：通过环境变量调整

## 开发指南

### 后端开发

```bash
cd backend
# 安装依赖
pip install -r requirements.txt
# 运行开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8081
# 运行 Celery worker
celery -A app.tasks.celery_app worker --loglevel=info
```

### 前端开发

```bash
cd frontend
# 安装依赖
npm install
# 运行开发服务器
npm run dev
```

## 许可证

MIT
