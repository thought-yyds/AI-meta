# AI Meta Chat Application

一个结合 FastAPI、Vue 3、Doubao LLM、WindowsMCP 桌面自动化工具以及自研 Agent 工具链的智能聊天应用，提供会话记忆、任务拆解、桌面操控与多步推理的完整体验。

## 项目优势

![AI Meta 聊天界面](img/image.png)

- 智能会话记忆：每 10 条消息自动触发总结，历史上下文+摘要一并存储，既保留细节又压缩上下文长度。
- 插件化 Agent：沿用 `src/` 下的工具链与 Doubao LLM，前端可视化地展示步骤和结果，方便排障与演示。
- 桌面自动化：集成 WindowsMCP，支持会议创建/加入、屏幕内容提取等跨应用操作，拓展真实办公场景。
- 双端可观测：后端记录所有推理步骤，前端 TaskInsight 面板提供“用户/开发者”双视角，结果透明可追溯。
- 易扩展易部署：FastAPI + Vue3 + SQLite 的轻量组合，配套 `.env`、初始化脚本、WindowsMCP 配置指南，落地成本低。

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

## WindowsMCP 配置

WindowsMCP 工具提供了 Windows 桌面自动化能力。配置方式有以下几种：

### 方式 1：全局安装（推荐）

使用 .NET 工具全局安装 WindowsMCP.Net：

```bash
dotnet tool install --global WindowsMCP.Net
```

安装后，工具会自动通过 `dotnet tool run` 命令找到并启动。

### 方式 2：配置系统 PATH

如果 WindowsMCP.Net 已安装但不在系统 PATH 中：

1. **找到可执行文件位置**：
   - 全局安装通常在：`%USERPROFILE%\.dotnet\tools\Windows-MCP.Net.exe`
   - 例如：`C:\Users\Lenovo\.dotnet\tools\Windows-MCP.Net.exe`
   - 或通过 `where Windows-MCP.Net` 查找

2. **添加到系统 PATH**：
   - 打开"系统属性" → "高级" → "环境变量"
   - 在"系统变量"中找到 `Path`，点击"编辑"
   - 添加包含 `WindowsMCP.Net.exe` 的目录路径
   - 重启终端或 IDE

### 方式 3：使用完整路径（无需配置 PATH）

如果不想修改系统 PATH，可以直接指定可执行文件的完整路径：

**在 `.env` 文件中配置**：

```env
# 方式 A：使用完整路径（Windows 路径，.exe 扩展名可选）
WINDOWS_MCP_COMMAND=C:\Users\Lenovo\.dotnet\tools\Windows-MCP.Net
# 或
WINDOWS_MCP_COMMAND=C:\Users\Lenovo\.dotnet\tools\Windows-MCP.Net.exe

# 方式 B：使用完整路径（相对路径，从项目根目录）
WINDOWS_MCP_COMMAND=./tools/Windows-MCP.Net.exe

# 可选：自定义参数（JSON 格式）
WINDOWS_MCP_ARGS=["--yes"]
```

> **注意**：代码会自动处理 `.exe` 扩展名，如果路径不存在，会自动尝试添加 `.exe` 扩展名。

**在代码中配置**：

```python
from src.tools.windows_mcp import WindowsMCPClient

# 使用完整路径（.exe 扩展名可选）
client = WindowsMCPClient(
    command=r"C:\Users\Lenovo\.dotnet\tools\Windows-MCP.Net",
    args=[]  # 如果可执行文件不需要额外参数
)
# 或
client = WindowsMCPClient(
    command=r"C:\Users\Lenovo\.dotnet\tools\Windows-MCP.Net.exe",
    args=[]
)
```

### 验证配置

运行以下命令测试 WindowsMCP 是否正常工作：

```python
from src.tools.windows_mcp import WindowsMCPClient

try:
    client = WindowsMCPClient()
    tools = client.list_tools_json()
    print("WindowsMCP 配置成功！")
    print(f"可用工具：{tools}")
except Exception as e:
    print(f"配置失败：{e}")
```

### 常见问题

1. **找不到命令**：
   - 检查是否已安装：`dotnet tool list -g`
   - 检查 PATH 是否包含工具目录
   - 或使用完整路径方式

2. **权限问题**：
   - 确保可执行文件有执行权限
   - Windows 可能需要以管理员身份运行

3. **路径格式**：
   - Windows 路径使用反斜杠 `\` 或正斜杠 `/`
   - 建议使用原始字符串 `r"C:\path\to\file.exe"` 或双反斜杠 `"C:\\path\\to\\file.exe"`
   - 可执行文件名是 `Windows-MCP.Net`（带连字符），不是 `WindowsMCP.Net`
   - `.exe` 扩展名可选，代码会自动处理

## 注意事项

- 确保后端服务运行在 `http://localhost:8000`
- 确保前端可以访问后端 API（检查 CORS 配置）
- 需要配置 LLM 服务的 API Key（DoubaoService）
- WindowsMCP 需要 .NET 运行时环境

## License

MIT
