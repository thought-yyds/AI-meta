# AI Meta Chat Application

一个基于 FastAPI 和 Vue 3 的智能聊天应用，集成了 AI Agent 和记忆总结功能。

## 功能特性

- ✅ 用户认证（注册/登录）
- ✅ 会话管理（创建、查看、删除会话）
- ✅ 实时聊天（与 AI Agent 对话）
- ✅ 消息历史记录
- ✅ 自动记忆总结（每 10 条消息自动生成总结）
- ✅ 手动生成总结

## 技术栈

### 后端
- FastAPI
- SQLAlchemy (SQLite)
- JWT 认证
- 集成现有的 Agent 和 LLM 服务

### 前端
- Vue 3 + TypeScript
- Vite
- 响应式设计

## 项目结构

```
AI-meta/
├── backend/
│   └── mymeta/
│       └── app/
│           ├── api/v1/          # API 路由
│           ├── core/            # 核心配置
│           ├── models/          # 数据库模型
│           ├── schemas/         # Pydantic schemas
│           └── services/        # 业务逻辑服务
├── frontend/
│   └── My-meta/                 # Vue 前端应用
└── src/                         # 现有的 Agent 和 LLM 代码
```

## 安装和运行

### 后端

1. 进入后端目录：
```bash
cd backend/mymeta
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. **初始化数据库**（首次运行需要）：
```bash
# 方法1：使用初始化脚本（推荐）
python init_db.py

# 方法2：直接运行应用（会自动创建数据库）
python -m app.main
```

4. **测试数据库连接**（可选）：
```bash
python test_connection.py
```

5. 配置环境变量（可选，创建 `.env` 文件）：
```env
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///./app.db
ARK_API_KEY=your-ark-api-key
ARK_MODEL_NAME=doubao-lite-4k
```

6. 运行后端服务：
```bash
python -m app.main
```

后端将在 `http://localhost:8000` 启动。

> **注意**：数据库文件 `app.db` 会在首次运行时自动创建在 `backend/mymeta/` 目录下。

### 前端

1. 进入前端目录：
```bash
cd frontend/My-meta
```

2. 安装依赖：
```bash
npm install
```

3. 配置环境变量（可选，创建 `.env` 文件）：
```bash
# 复制示例文件
cp .env.example .env

# 编辑 .env 文件，确保 API 地址正确
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

4. 运行开发服务器：
```bash
npm run dev
```

前端将在 `http://localhost:5173` 启动。

> **注意**：确保后端服务已启动，前端才能正常连接。如果后端运行在不同端口，请修改 `.env` 文件中的 `VITE_API_BASE_URL`。

## API 端点

### 认证
- `POST /api/v1/auth/register` - 注册新用户
- `POST /api/v1/auth/token` - 登录获取 token
- `GET /api/v1/auth/me` - 获取当前用户信息

### 会话
- `GET /api/v1/sessions/` - 获取所有会话
- `POST /api/v1/sessions/` - 创建新会话
- `GET /api/v1/sessions/{id}` - 获取特定会话
- `PATCH /api/v1/sessions/{id}` - 更新会话标题
- `DELETE /api/v1/sessions/{id}` - 删除会话

### 消息
- `GET /api/v1/messages/session/{session_id}` - 获取会话的所有消息
- `GET /api/v1/messages/{id}` - 获取特定消息

### 聊天
- `POST /api/v1/chat/` - 发送消息给 AI Agent

### 总结
- `GET /api/v1/summaries/session/{session_id}` - 获取会话的所有总结
- `POST /api/v1/summaries/session/{session_id}/generate` - 手动生成总结

## 使用说明

1. **注册/登录**：首次使用需要注册账号，之后可以登录。

2. **创建会话**：点击左侧的 "New" 按钮创建新会话，或直接开始发送消息（会自动创建会话）。

3. **发送消息**：在输入框中输入消息，按 Enter 发送（Shift+Enter 换行）。

4. **查看总结**：点击聊天界面顶部的 "Show Summary" 按钮查看对话总结。系统会在每 10 条消息后自动生成总结。

5. **管理会话**：在左侧会话列表中，可以查看所有会话，点击会话查看历史消息，或删除不需要的会话。

## 开发说明

### 数据库初始化

数据库表会在应用启动时自动创建。你也可以手动初始化：

```bash
cd backend/mymeta
python init_db.py
```

### 验证数据库和连接

运行测试脚本检查数据库和配置：

```bash
cd backend/mymeta
python test_connection.py
```

### 重置数据库

如果需要重置数据库，删除 `backend/mymeta/app.db` 文件，然后重新运行初始化脚本。

### 前后端连接验证

1. **检查后端是否运行**：
   - 访问 http://localhost:8000/docs 查看 API 文档
   - 访问 http://localhost:8000/health 检查健康状态

2. **检查前端配置**：
   - 确认 `frontend/My-meta/.env` 中的 `VITE_API_BASE_URL` 指向正确的后端地址
   - 默认应该是 `http://localhost:8000/api/v1`

3. **检查 CORS 配置**：
   - 后端已配置允许 `http://localhost:5173` 的跨域请求
   - 如果前端运行在不同端口，需要在 `backend/mymeta/app/core/config.py` 中添加该端口

### 添加新功能

- **后端**：在 `app/api/v1/` 下添加新的路由文件，在 `app/services/` 下添加业务逻辑。
- **前端**：在 `src/components/` 下添加新组件，在 `src/services/api.ts` 中添加 API 调用。

## 注意事项

- 确保后端服务运行在 `http://localhost:8000`
- 确保前端可以访问后端 API（检查 CORS 配置）
- 需要配置 LLM 服务的 API Key（DoubaoService）

## License

MIT
