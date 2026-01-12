# LoRA 写真数据集自动构建平台

一个高效、灵活的 LoRA 写真数据集自动构建工具，支持本地 CLI 和 Web UI 两种运行模式，支持本地部署的多模态模型的调用，专注于隐私保护和高性能处理。

### 目前后端写的是我自己的模搭社区的apikey，大家测试一下然后写自己的就行了（乐）前端设置或者后端写死都可以，开发者有每天两千次的免费调用，但是限额每个模型最多五百次，所以我写了一个满额自己切换的功能。


<img width="2560" height="1047" alt="image" src="https://github.com/user-attachments/assets/9fe07660-8559-45bf-b22c-66348455952c" />

<img width="1625" height="757" alt="image" src="https://github.com/user-attachments/assets/c27e1a92-3103-48fd-9d98-e8d6d50fb858" />

## 功能特性

### 核心功能
- **自动化处理流程**：解压 -> 去重 -> 预览生成 -> 焦点检测 -> 1024x1024 裁剪 -> 智能打标 -> 打包输出
- **超高分辨率支持**：轻松处理长边 3000+ 像素甚至 4000 万像素的图片
- **双模式运行**：
  - 本地 CLI 模式：强隐私、省带宽、速度快
  - Web UI 模式：直观操作、进度实时展示、结果预览
- **隐私优先**：本地模式无需上传原始图片

<img width="1652" height="1006" alt="image" src="https://github.com/user-attachments/assets/a50faf0b-dff6-4573-bb58-c47b47bbb73a" />


## 快速开始

### Web UI 模式（推荐）

#### 1. 配置端口（可选）

编辑 `config/ports.json` 文件，自定义端口配置：

```json
{
  "backend_port": 8081,
  "backend_host": "0.0.0.0",
  "frontend_port": 8080,
  "redis_port": 6379
}
```

#### 2. 启动后端服务

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8081
```

#### 3. 启动前端服务

```bash
cd frontend
npm install
npm run dev
```

#### 4. 访问应用

打开浏览器访问：http://localhost:8080

### 本地 CLI 模式

```bash
cd client
pip install -r requirements.txt
pip install -e .

# 执行完整处理流程
lora-dataset-builder run-all --input input_root --output output_root
```

## 项目结构

```
lora-dataset-builder/
├── backend/                 # FastAPI后端
│   ├── app/                 # 应用核心代码
│   │   ├── api/             # API接口定义
│   │   ├── core/            # 配置和核心功能
│   │   ├── db/              # 数据库配置
│   │   ├── models/          # 数据模型
│   │   ├── services/        # 业务逻辑服务
│   │   └── tasks/           # 异步任务
│   ├── requirements.txt     # 后端依赖
│   └── Dockerfile           # Docker构建文件
├── client/                  # 本地Python CLI工具
│   ├── src/                 # CLI源代码
│   ├── requirements.txt     # CLI依赖
│   └── setup.py             # 安装配置
├── config/                  # 配置文件
│   └── ports.json           # 端口配置
├── frontend/                # Vue前端应用
│   ├── src/                 # 前端源代码
│   │   ├── components/      # Vue组件
│   │   ├── router/          # 路由配置
│   │   ├── services/        # API服务
│   │   └── views/           # 页面视图
│   ├── package.json         # 前端依赖
│   └── vite.config.ts       # Vite配置
├── docs/                    # 文档
└── docker-compose.yml       # Docker Compose配置
```

## 技术实现

### 后端实现
- **框架**：FastAPI 提供高性能 RESTful API
- **数据库**：SQLAlchemy + SQLite 轻量级数据存储
- **任务处理**：异步任务处理，支持进度实时更新
- **图像处理**：Pillow + NumPy 高效图像操作
- **模型调用**：兼容 OpenAI SDK 的模型客户端，支持自定义模型服务

### 前端实现
- **框架**：Vue3 + TypeScript 提供类型安全的开发体验
- **UI 组件**：Element Plus 构建现代化界面
- **路由**：Vue Router 实现单页应用路由
- **API 交互**：Axios 处理 HTTP 请求，支持 SSE 实时进度

### 核心处理流程

1. **解压与初始化**：解析上传的 ZIP 文件，创建任务记录
2. **智能去重**：基于 pHash 和图像特征的高效去重算法
3. **预览生成**：生成压缩预览图，优化前端加载速度
4. **焦点检测**：调用视觉模型检测图像核心区域
5. **精确裁剪**：根据焦点区域裁剪 1024x1024 训练图像
6. **智能打标**：使用视觉语言模型生成详细图像标签
7. **打包输出**：生成最终的训练数据集 ZIP 包

## 使用说明

### Web UI 使用
1. 访问 http://localhost:8080
2. 选择上传方式：多个 ZIP 文件或文件夹
3. 配置模型参数（可选）
4. 点击上传，查看实时进度
5. 任务完成后，下载生成的 train_package.zip

### 自定义模型服务

在设置页面中，可以配置自定义的模型服务地址和 API 密钥，支持：
- 自定义模型地址
- API 密钥配置
- 焦点检测模型选择
- 打标模型选择

## 许可证

MIT License
# 运行开发服务器
npm run dev
```

## 许可证

MIT
