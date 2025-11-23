# 快速启动指南

本指南将帮助你快速启动并验证前后端连接。

## 第一步：初始化数据库

```bash
cd backend/mymeta
python init_db.py
```

你应该看到：
```
Initializing database at: sqlite:///./app.db
Creating all tables...
✅ Database initialized successfully!
```

## 第二步：启动后端

```bash
# 在 backend/mymeta 目录下
python -m app.main
```

后端启动后，你应该看到类似输出：
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**验证后端**：
- 打开浏览器访问 http://localhost:8000/docs
- 应该能看到 Swagger API 文档页面

## 第三步：配置前端

```bash
cd frontend/My-meta

# 创建 .env 文件（如果还没有）
echo "VITE_API_BASE_URL=http://localhost:8000/api/v1" > .env
```

## 第四步：启动前端

```bash
# 在 frontend/My-meta 目录下
npm install  # 如果还没安装依赖
npm run dev
```

前端启动后，你应该看到：
```
  VITE v5.x.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
```

## 第五步：验证连接

1. **打开前端页面**：http://localhost:5173
2. **注册账号**：填写用户名、邮箱和密码
3. **登录**：使用刚注册的账号登录
4. **测试聊天**：发送一条消息，看是否能收到 AI 回复

## 常见问题排查

### 问题1：数据库未创建

**症状**：后端启动时报错或无法访问 API

**解决**：
```bash
cd backend/mymeta
python init_db.py
```

### 问题2：前端无法连接后端

**症状**：前端显示网络错误或 404

**检查清单**：
1. ✅ 后端是否正在运行？（访问 http://localhost:8000/docs）
2. ✅ `.env` 文件中的 `VITE_API_BASE_URL` 是否正确？
3. ✅ 浏览器控制台是否有 CORS 错误？

**解决**：
- 确认后端运行在 `http://localhost:8000`
- 确认前端 `.env` 文件：`VITE_API_BASE_URL=http://localhost:8000/api/v1`
- 如果前端运行在不同端口，需要在 `backend/mymeta/app/core/config.py` 的 `allowed_origins` 中添加该端口

### 问题3：CORS 错误

**症状**：浏览器控制台显示 CORS 相关错误

**解决**：
编辑 `backend/mymeta/app/core/config.py`，在 `allowed_origins` 列表中添加你的前端地址：
```python
allowed_origins: List[str] = [
    "http://localhost:3000",
    "http://localhost:8080",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:你的端口"  # 添加你的端口
]
```

### 问题4：数据库文件位置

数据库文件 `app.db` 会创建在 `backend/mymeta/` 目录下。

查看数据库状态：
```bash
cd backend/mymeta
python test_connection.py
```

## 测试脚本

运行完整的连接测试：
```bash
cd backend/mymeta
python test_connection.py
```

这会检查：
- ✅ 数据库连接
- ✅ 表是否创建
- ✅ 配置是否正确

## 下一步

一切正常后，你可以：
1. 注册/登录账号
2. 创建新会话
3. 开始与 AI 聊天
4. 查看对话总结

享受使用！🎉

