# 后端启动指南

## 前置要求

1. **Python 3.8+**
2. **MySQL 数据库**（已安装并运行）
3. **pip**（Python 包管理器）

## 启动步骤

### 1. 安装依赖

```bash
cd backend/mymeta
pip install -r requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件（在 `backend/mymeta` 目录下）：

```env
# 应用配置
SECRET_KEY=your-secret-key-change-this-in-production
DEBUG=True

# 数据库配置
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=mymeta

# 服务器配置
HOST=0.0.0.0
PORT=8000
```

**注意**：请根据你的 MySQL 配置修改数据库相关参数。

### 3. 初始化数据库

首次启动前，需要初始化数据库：

```bash
python init_db.py
```

这会：
- 创建数据库（如果不存在）
- 创建所有数据表

### 4. 启动后端服务

#### 方式一：使用启动脚本（最简单，推荐）

**Windows (CMD)**:
```cmd
start.bat
```

**Windows (PowerShell)**:
```powershell
.\start.bat
```

**Linux/Mac**:
```bash
chmod +x start.sh
./start.sh
```

启动脚本会自动：
- 检查 `.env` 文件是否存在
- 检查数据库连接
- 如果数据库未初始化，自动运行 `init_db.py`
- 启动开发服务器（带自动重载）

#### 方式二：使用 uvicorn 命令（手动启动）

```bash
# 开发模式（自动重载）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 生产模式
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

#### 方式三：直接运行 main.py

```bash
python -m app.main
```

#### 方式四：使用 Python 模块方式

```bash
python -m uvicorn app.main:app --reload
```

### 5. 验证启动

启动成功后，访问以下地址：

- **API 文档（Swagger）**: http://localhost:8000/docs
- **API 文档（ReDoc）**: http://localhost:8000/redoc
- **健康检查**: http://localhost:8000/health
- **根路径**: http://localhost:8000/

## 创建测试用户

启动后端后，可以创建测试用户：

```bash
# 创建默认测试用户（用户名: testuser, 密码: testpass123）
python create_test_user.py

# 或创建自定义用户
python create_test_user.py [用户名] [邮箱] [密码]
```

## 常见问题

### 1. 数据库连接失败

**错误信息**：`Could not connect to MySQL`

**解决方法**：
- 确保 MySQL 服务正在运行
- 检查 `.env` 文件中的数据库配置是否正确
- 确认数据库用户有足够的权限

### 2. 端口被占用

**错误信息**：`Address already in use`

**解决方法**：
- 修改 `.env` 文件中的 `PORT` 值
- 或使用 `--port` 参数指定其他端口：
  ```bash
  uvicorn app.main:app --reload --port 8001
  ```

### 3. 模块导入错误

**错误信息**：`ModuleNotFoundError`

**解决方法**：
- 确保在 `backend/mymeta` 目录下运行命令
- 确保已安装所有依赖：`pip install -r requirements.txt`

### 4. PowerShell 中无法运行 start.bat

**错误信息**：`无法将"start.bat"项识别为 cmdlet、函数、脚本文件或可运行程序的名称`

**解决方法**：
- 在 PowerShell 中需要使用 `.\start.bat` 而不是 `start.bat`
- 或者切换到 CMD 命令提示符运行 `start.bat`

## 开发建议

1. **使用虚拟环境**（推荐）：
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # Linux/Mac
   source venv/bin/activate
   ```

2. **启用自动重载**：使用 `--reload` 参数，代码修改后会自动重启

3. **查看日志**：日志文件位于 `logs/` 目录

## 生产环境部署

生产环境建议：
- 设置 `DEBUG=False`
- 使用强密码的 `SECRET_KEY`
- 使用反向代理（如 Nginx）
- 配置 HTTPS
- 使用进程管理器（如 systemd、supervisor）

