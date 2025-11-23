# MySQL 数据库设置指南

## 快速开始

### 1. 确保 MySQL 已安装并运行

**Windows:**
- 检查服务管理器中的 MySQL 服务是否运行
- 或运行命令：`mysql -u root -p` 测试连接

**Linux/Mac:**
```bash
sudo systemctl status mysql
# 或
mysql -u root -p
```

### 2. 安装 Python 依赖

```bash
cd backend/mymeta
pip install -r requirements.txt
```

这会安装 `pymysql` 和 `cryptography`（MySQL 驱动）。

### 3. 配置数据库（可选）

创建 `.env` 文件（如果使用非默认配置）：

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=你的密码
DB_NAME=mymeta
```

**默认配置**（如果不创建 `.env` 文件）：
- 主机: `localhost`
- 端口: `3306`
- 用户: `root`
- 密码: (空)
- 数据库名: `mymeta`

### 4. 初始化数据库

```bash
python init_db.py
```

这会：
- 自动创建数据库（如果不存在）
- 创建所有必需的表

### 5. 验证连接

```bash
python test_connection.py
```

如果看到 "✅ All tests passed!" 说明一切正常。

### 6. 启动应用

```bash
python -m app.main
```

---

## 常见问题

### 问题：无法连接到 MySQL

**解决方案：**
1. 确认 MySQL 服务正在运行
2. 检查 `.env` 文件中的配置
3. 测试连接：`mysql -u root -p`

### 问题：Access denied for user

**解决方案：**
1. 检查用户名和密码是否正确
2. 确认用户有创建数据库的权限：
```sql
GRANT ALL PRIVILEGES ON *.* TO 'root'@'localhost';
FLUSH PRIVILEGES;
```

### 问题：数据库不存在

**解决方案：**
运行初始化脚本：
```bash
python init_db.py
```

或手动创建：
```sql
CREATE DATABASE IF NOT EXISTS mymeta CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

---

## 数据库配置说明

### 环境变量

所有数据库配置都可以通过环境变量覆盖：

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `DB_HOST` | `localhost` | MySQL 服务器地址 |
| `DB_PORT` | `3306` | MySQL 端口 |
| `DB_USER` | `root` | 数据库用户名 |
| `DB_PASSWORD` | (空) | 数据库密码 |
| `DB_NAME` | `mymeta` | 数据库名称 |

### 连接字符串格式

内部使用的连接字符串格式：
```
mysql+pymysql://用户名:密码@主机:端口/数据库名?charset=utf8mb4
```

---

## 从 SQLite 迁移到 MySQL

如果你之前使用 SQLite，现在切换到 MySQL：

1. **备份 SQLite 数据**（如果需要）：
```bash
# SQLite 数据在 app.db 文件中
```

2. **安装 MySQL 依赖**：
```bash
pip install -r requirements.txt
```

3. **配置 MySQL 连接**（创建 `.env` 文件）

4. **初始化 MySQL 数据库**：
```bash
python init_db.py
```

5. **迁移数据**（如果需要）：
   - 导出 SQLite 数据
   - 导入到 MySQL
   - 或手动迁移

---

## 生产环境建议

1. **使用专用数据库用户**（不要使用 root）：
```sql
CREATE USER 'mymeta_user'@'localhost' IDENTIFIED BY 'strong_password';
GRANT ALL PRIVILEGES ON mymeta.* TO 'mymeta_user'@'localhost';
FLUSH PRIVILEGES;
```

2. **设置强密码**：
   - 在 `.env` 文件中设置 `DB_PASSWORD`
   - 不要将 `.env` 文件提交到版本控制

3. **使用连接池**：
   - 已在 `database.py` 中配置连接池
   - `pool_pre_ping=True` 自动验证连接
   - `pool_recycle=3600` 每小时回收连接

4. **字符集**：
   - 使用 `utf8mb4` 支持完整的 Unicode（包括 emoji）

