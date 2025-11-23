# 设置指南 - 解决数据库和前后端连接问题

## 问题1：数据库初始化

### 数据库类型

项目使用 **MySQL** 数据库。

### 前置要求

1. **安装 MySQL 服务器**
   - Windows: 下载并安装 [MySQL Community Server](https://dev.mysql.com/downloads/mysql/)
   - 或使用 XAMPP/WAMP 等集成环境
   - 确保 MySQL 服务正在运行

2. **创建数据库用户**（可选，默认使用 root）
   - 如果使用 root 用户，确保密码正确
   - 或创建新用户并授予权限

### 解决方案

1. **安装后端依赖**（包括 MySQL 驱动）：
```bash
cd backend/mymeta
pip install -r requirements.txt
```

2. **配置数据库连接**（可选）

创建 `.env` 文件（如果不存在）：
```bash
cd backend/mymeta
```

创建 `.env` 文件，内容：
```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=你的MySQL密码
DB_NAME=mymeta
```

如果不创建 `.env` 文件，将使用默认配置：
- 主机: localhost
- 端口: 3306
- 用户: root
- 密码: (空)
- 数据库名: mymeta

3. **初始化数据库**：

**方式1：使用初始化脚本（推荐）**
```bash
cd backend/mymeta
python init_db.py
```

脚本会自动：
- 创建数据库（如果不存在）
- 创建所有表

**方式2：手动创建数据库后启动应用**
```sql
-- 在 MySQL 中执行
CREATE DATABASE IF NOT EXISTS mymeta CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

然后启动应用（会自动创建表）：
```bash
cd backend/mymeta
python -m app.main
```

### 验证数据库

运行测试脚本：
```bash
cd backend/mymeta
python test_connection.py
```

如果看到 "✅ Database initialized successfully!" 说明数据库已创建。

### 数据库位置

MySQL 数据库存储在 MySQL 服务器的数据目录中，默认位置：
- Windows: `C:\ProgramData\MySQL\MySQL Server X.X\Data\mymeta\`
- Linux: `/var/lib/mysql/mymeta/`

---

## 问题2：前后端连接

### 后端配置

后端已配置 CORS，允许以下前端地址：
- `http://localhost:5173` (Vite 默认端口)
- `http://127.0.0.1:5173`
- `http://localhost:3000`
- `http://localhost:8080`

如果前端运行在其他端口，编辑 `backend/mymeta/app/core/config.py`：
```python
allowed_origins: List[str] = [
    "http://localhost:5173",
    "http://localhost:你的端口",  # 添加你的端口
]
```

### 前端配置

1. **创建 `.env` 文件**：
```bash
cd frontend/My-meta
# 创建 .env 文件
echo VITE_API_BASE_URL=http://localhost:8000/api/v1 > .env
```

或者手动创建 `frontend/My-meta/.env` 文件，内容：
```
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

2. **重启前端开发服务器**：
```bash
npm run dev
```

### 验证连接

1. **检查后端是否运行**：
   - 访问 http://localhost:8000/docs
   - 应该能看到 API 文档

2. **检查前端配置**：
   - 打开浏览器开发者工具（F12）
   - 查看 Network 标签
   - 发送一条消息，看请求是否发送到 `http://localhost:8000/api/v1/...`

3. **常见错误**：
   - **CORS 错误**：检查后端 `allowed_origins` 配置
   - **404 错误**：检查 `.env` 文件中的 `VITE_API_BASE_URL`
   - **连接拒绝**：确保后端正在运行

---

## 完整启动流程

### 1. 安装依赖

**后端**：
```bash
cd backend/mymeta
pip install -r requirements.txt
```

**前端**：
```bash
cd frontend/My-meta
npm install
```

### 2. 初始化数据库

```bash
cd backend/mymeta
python init_db.py
```

### 3. 启动后端

```bash
cd backend/mymeta
python -m app.main
```

后端运行在：http://localhost:8000

### 4. 配置前端

```bash
cd frontend/My-meta
# 创建 .env 文件
echo VITE_API_BASE_URL=http://localhost:8000/api/v1 > .env
```

### 5. 启动前端

```bash
cd frontend/My-meta
npm run dev
```

前端运行在：http://localhost:5173

### 6. 测试

1. 打开浏览器访问 http://localhost:5173
2. 注册一个新账号
3. 登录
4. 发送一条消息测试

---

## 故障排查

### 数据库问题

**问题**：`ModuleNotFoundError: No module named 'pymysql'`

**解决**：
```bash
cd backend/mymeta
pip install -r requirements.txt
```

**问题**：`Can't connect to MySQL server`

**解决**：
1. 确保 MySQL 服务正在运行
   - Windows: 在服务管理器中检查 MySQL 服务
   - 或运行 `mysql -u root -p` 测试连接
2. 检查 `.env` 文件中的配置是否正确
3. 确认 MySQL 端口（默认 3306）未被占用

**问题**：`Access denied for user`

**解决**：
1. 检查 `.env` 文件中的 `DB_USER` 和 `DB_PASSWORD`
2. 确认用户有创建数据库的权限：
```sql
GRANT ALL PRIVILEGES ON *.* TO 'root'@'localhost';
FLUSH PRIVILEGES;
```

**问题**：数据库未创建

**解决**：
```bash
cd backend/mymeta
python init_db.py
```

或手动创建数据库：
```sql
CREATE DATABASE IF NOT EXISTS mymeta CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 连接问题

**问题**：前端无法连接后端

**检查**：
1. 后端是否运行？（访问 http://localhost:8000/docs）
2. `.env` 文件是否存在且配置正确？
3. 浏览器控制台是否有错误？

**解决**：
- 确认后端运行在 8000 端口
- 确认 `.env` 文件：`VITE_API_BASE_URL=http://localhost:8000/api/v1`
- 检查 CORS 配置

**问题**：CORS 错误

**解决**：在 `backend/mymeta/app/core/config.py` 中添加前端地址到 `allowed_origins`

---

## 快速检查清单

- [ ] 后端依赖已安装 (`pip install -r requirements.txt`)
- [ ] 数据库已初始化 (`python init_db.py`)
- [ ] 后端正在运行 (http://localhost:8000/docs 可访问)
- [ ] 前端 `.env` 文件已创建且配置正确
- [ ] 前端正在运行 (http://localhost:5173 可访问)
- [ ] 浏览器控制台无错误
- [ ] 可以成功注册/登录
- [ ] 可以发送消息并收到回复

如果所有项目都打勾，说明前后端已成功连接！🎉

