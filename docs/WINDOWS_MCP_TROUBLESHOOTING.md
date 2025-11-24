# WindowsMCP.Net 故障排除指南

## 常见错误：TaskGroup 错误

### 错误信息
```
无法获取 WindowsMCP.Net 工具列表：unhandled errors in a TaskGroup (1 sub-exception)
调用 WindowsMCP.Net 工具 launch_app 失败：unhandled errors in a TaskGroup (1 sub-exception)
```

### 为什么在 main.py 中可以，但在前后端不行？

**根本原因：**
- `main.py` 在纯同步环境中运行，没有事件循环
- 前后端（FastAPI）运行在异步事件循环中
- 当在已有事件循环中创建新的 `stdio_client` 连接时，会导致事件循环冲突和 TaskGroup 错误

**技术细节：**
1. FastAPI 运行在异步事件循环中（即使端点函数是同步的）
2. WindowsMCP 的 `call_tool_json` 需要创建 `stdio_client` 连接
3. `stdio_client` 会启动 WindowsMCP.Net 子进程并通过 stdio 通信
4. 在已有事件循环中创建新的异步连接会导致 TaskGroup 错误

### 可能的原因

1. **WindowsMCP.Net 进程启动失败**
   - 可执行文件路径不正确
   - 可执行文件不存在或损坏
   - 权限问题

2. **WindowsMCP.Net 进程崩溃**
   - 进程启动后立即退出
   - 进程异常终止

3. **事件循环冲突**
   - 在已有事件循环中调用异步代码
   - 事件循环嵌套问题

4. **MCP SDK 问题**
   - MCP SDK 版本不兼容
   - stdio_client 初始化失败

### 诊断步骤

#### 1. 运行诊断工具

```bash
python -m src.main --diagnose-windows-mcp
```

诊断工具会检查：
- MCP SDK 安装
- stdio_client 可用性
- WindowsMCP.Net 命令路径
- 客户端创建
- 工具列表获取

#### 2. 测试 WindowsMCP 连接

```bash
python -m src.main --test-windows-mcp
```

#### 3. 检查 WindowsMCP.Net 安装

```bash
# 检查是否已安装
dotnet tool list -g

# 如果未安装，安装它
dotnet tool install --global WindowsMCP.Net

# 如果已安装但有问题，重新安装
dotnet tool uninstall --global WindowsMCP.Net
dotnet tool install --global WindowsMCP.Net
```

#### 4. 检查环境变量

```bash
# Windows PowerShell
$env:WINDOWS_MCP_COMMAND
$env:WINDOWS_MCP_ARGS

# 如果需要设置
$env:WINDOWS_MCP_COMMAND = "C:\Users\Lenovo\.dotnet\tools\Windows-MCP.Net.exe"
```

#### 5. 手动测试 WindowsMCP.Net

```bash
# 直接运行 WindowsMCP.Net，看是否有错误
dnx WindowsMCP.Net@ --yes

# 或者使用完整路径
C:\Users\Lenovo\.dotnet\tools\Windows-MCP.Net.exe
```

### 解决方案

#### 方案 1：修复事件循环问题（已自动处理）

代码已经改进了事件循环处理，会自动检测并处理嵌套事件循环问题。

#### 方案 2：使用完整路径

如果命令路径有问题，设置环境变量：

```bash
# Windows PowerShell
$env:WINDOWS_MCP_COMMAND = "C:\Users\Lenovo\.dotnet\tools\Windows-MCP.Net.exe"
$env:WINDOWS_MCP_ARGS = "[]"
```

#### 方案 3：重启服务

如果问题持续存在，尝试：
1. 重启 Python 服务
2. 重启 WindowsMCP.Net 进程
3. 检查是否有其他进程占用

#### 方案 4：检查日志

查看详细的错误信息，错误消息现在包含：
- 错误类型
- 可能的原因
- 使用的命令和参数

### 代码改进

已完成的改进（2024年最新）：

1. **改进事件循环处理** (`_run_async` 方法)
   - **自动检测运行中的事件循环**：检测 FastAPI 或其他异步框架的事件循环
   - **使用专用线程**：当检测到运行中的事件循环时，在新线程中创建独立的事件循环
   - **避免冲突**：确保 `stdio_client` 在独立的事件循环中运行，避免与 FastAPI 的事件循环冲突
   - **更好的错误恢复**：提供清晰的错误信息和恢复建议

2. **增强错误信息**
   - 详细的错误描述和类型
   - 可能的原因列表
   - 使用的命令和参数
   - 针对 TaskGroup 错误的特殊处理

3. **诊断工具**
   - 自动检查所有可能的问题
   - 提供详细的诊断报告
   - 帮助快速定位问题

### 修复说明

**关键修复：**
- 修改了 `WindowsMCPClient._run_async()` 方法
- 当检测到运行中的事件循环时，总是使用新线程和新事件循环
- 这确保了 `stdio_client` 不会与 FastAPI 的事件循环冲突
- 解决了"在 main.py 中可以，但在前后端不行"的问题

### 如果问题仍然存在

1. **检查 WindowsMCP.Net 版本**
   ```bash
   dotnet tool list -g
   ```

2. **更新 MCP SDK**
   ```bash
   pip install --upgrade mcp
   ```

3. **查看详细日志**
   - 启用 DEBUG 日志级别
   - 查看完整的错误堆栈

4. **联系支持**
   - 提供诊断工具的输出
   - 提供错误堆栈信息
   - 提供系统信息（Windows 版本、.NET 版本等）

### 预防措施

1. **定期更新**
   - 保持 WindowsMCP.Net 最新版本
   - 保持 MCP SDK 最新版本

2. **使用环境变量**
   - 使用环境变量配置路径，而不是硬编码

3. **错误处理**
   - 代码已添加更好的错误处理
   - 工具会优雅地处理失败情况

### 相关文件

- `src/tools/windows_mcp.py` - WindowsMCP 客户端实现
- `src/main.py` - 命令行工具和诊断功能
- `docs/MEETING_MONITORING_ARCHITECTURE.md` - 架构说明

