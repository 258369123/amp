# 🎯 Claude Code MCP 配置指南

## ✅ MCP 服务器已实现！

AMP 平台现在完全支持标准的 MCP (Model Context Protocol) 协议，可以直接与 Claude Code 集成。

---

## 📋 配置步骤

### 1. 确认安装

```bash
cd /home/xp/test/0506

# 安装依赖（如果还没安装）
pip install -e .

# 测试 MCP 服务器
python amp/mcp/test_mcp_server.py
```

### 2. 配置 Claude Code

在 Claude Code 的 MCP 配置中添加 AMP 服务器：

**配置文件位置**: 
- Linux/Mac: `~/.config/Code/User/settings.json` 或 Claude Code 设置
- Windows: `%APPDATA%\Code\User\settings.json`

**添加以下配置**:

```json
{
  "mcpServers": {
    "amp": {
      "command": "python",
      "args": ["-m", "amp.mcp.run_mcp_server"],
      "cwd": "/home/xp/test/0506",
      "env": {
        "PYTHONPATH": "/home/xp/test/0506",
        "AMP_DATABASE__URL": "sqlite:///amp.db",
        "AMP_CONTEXT__VECTOR_DB_PATH": "./chroma_db"
      }
    }
  }
}
```

**或者使用 amp-mcp 命令**:

```json
{
  "mcpServers": {
    "amp": {
      "command": "amp-mcp",
      "cwd": "/home/xp/test/0506"
    }
  }
}
```

### 3. 重启 Claude Code

配置完成后，重启 Claude Code 以加载 MCP 服务器。

---

## 🧪 验证集成

### 方法 1: 在 Claude Code 中测试

启动 Claude Code 后，尝试：

```
> 列出所有 AMP 工具
> 显示 AMP 服务器状态
> 创建一个测试隧道
```

### 方法 2: 手动测试 MCP 协议

```bash
# 测试 initialize 请求
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | python -m amp.mcp.run_mcp_server

# 测试 tools/list 请求
echo '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | python -m amp.mcp.run_mcp_server
```

---

## 🔧 可用的 17 个 MCP 工具

### 隧道管理 (6)
1. **create_tunnel** - 创建新隧道
2. **start_tunnel** - 启动隧道
3. **stop_tunnel** - 停止隧道
4. **delete_tunnel** - 删除隧道
5. **list_tunnels** - 列出所有隧道
6. **get_tunnel_status** - 获取隧道状态

### Shell 管理 (5)
7. **create_shell** - 创建 Shell 会话
8. **execute_command** - 执行命令
9. **close_shell** - 关闭 Shell
10. **list_shells** - 列出所有 Shell
11. **get_shell_status** - 获取 Shell 状态

### 上下文查询 (3)
12. **get_relevant_operations** - 获取相关操作
13. **build_prompt** - 构建动态提示
14. **compress_context** - 压缩上下文

### 网络拓扑 (3)
15. **visualize_topology** - 可视化拓扑
16. **find_route** - 查找路由
17. **get_affected_segments** - 获取受影响网段

---

## 💡 使用示例

### 示例 1: 创建隧道

在 Claude Code 中：
```
> 使用 AMP 创建一个到 192.168.1.100:22 的 Chisel 隧道，本地端口 8080
```

Claude 会自动调用：
```json
{
  "tool": "create_tunnel",
  "arguments": {
    "name": "dmz-tunnel",
    "tunnel_type": "chisel",
    "local_port": 8080,
    "remote_host": "192.168.1.100",
    "remote_port": 22
  }
}
```

### 示例 2: 查看网络拓扑

```
> 显示当前的网络拓扑图
```

Claude 会调用 `visualize_topology` 工具。

### 示例 3: 执行命令

```
> 在 shell-123 中执行 whoami 命令
```

Claude 会调用：
```json
{
  "tool": "execute_command",
  "arguments": {
    "shell_id": "shell-123",
    "command": "whoami"
  }
}
```

---

## 🐛 故障排除

### 问题 1: MCP 服务器无法启动

**症状**: Claude Code 报告 MCP 服务器启动失败

**解决方案**:
```bash
# 1. 检查 Python 环境
which python
python --version

# 2. 测试服务器
python amp/mcp/test_mcp_server.py

# 3. 检查依赖
pip list | grep mcp

# 4. 查看日志
# Claude Code 会显示 MCP 服务器的错误输出
```

### 问题 2: 工具无法执行

**症状**: 工具调用返回错误

**解决方案**:
```bash
# 1. 确认数据库已初始化
python init_db.py

# 2. 检查环境变量
cat .env

# 3. 测试工具执行
python amp/mcp/test_mcp_integration.py
```

### 问题 3: 找不到 amp-mcp 命令

**症状**: `command not found: amp-mcp`

**解决方案**:
```bash
# 重新安装包
pip install -e .

# 或使用完整路径
python -m amp.mcp.run_mcp_server
```

---

## 📊 MCP vs REST API

AMP 现在提供两种接口：

### MCP 协议（推荐用于 Claude Code）
- **协议**: JSON-RPC 2.0
- **传输**: stdio (标准输入/输出)
- **用途**: Claude Code 集成
- **启动**: `amp-mcp` 或 `python -m amp.mcp.run_mcp_server`

### REST API（用于 Web UI 和直接调用）
- **协议**: HTTP REST
- **传输**: HTTP
- **用途**: Web UI、curl、Python 脚本
- **启动**: `python amp/mcp/run_server.py`
- **地址**: http://127.0.0.1:8899

---

## 🎯 下一步

1. ✅ **配置完成** - 按照上述步骤配置 Claude Code
2. ✅ **测试工具** - 在 Claude Code 中测试 AMP 工具
3. ✅ **创建隧道** - 开始使用渗透测试功能
4. ✅ **查看拓扑** - 可视化网络结构

---

## 📖 相关文档

- **amp/mcp/README_MCP.md** - MCP 服务器详细文档
- **amp/mcp/IMPLEMENTATION_SUMMARY.md** - 实现细节
- **CLAUDE_CODE_INTEGRATION.md** - 完整集成指南
- **PROJECT_SUMMARY.md** - 项目总览

---

## 🎉 成功！

AMP 平台现在完全支持 MCP 协议，可以无缝集成到 Claude Code 中！

**配置文件**: `amp/mcp/claude_code_config.json`  
**测试脚本**: `amp/mcp/test_mcp_server.py`  
**启动命令**: `amp-mcp`

祝您使用愉快！🚀
