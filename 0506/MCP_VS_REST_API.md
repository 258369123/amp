# ⚠️ 重要：MCP vs REST API

## 问题说明

您遇到的错误是因为启动了错误的服务器。AMP 平台有两个不同的服务器：

### 1. MCP 协议服务器（用于 Claude Code）✅
- **命令**: `amp-mcp`
- **协议**: JSON-RPC 2.0 over stdio
- **用途**: Claude Code 集成
- **不需要手动启动** - Claude Code 会自动启动

### 2. REST API 服务器（用于 Web UI）
- **命令**: `uvicorn amp.mcp.server:create_app --factory --host 127.0.0.1 --port 8899`
- **协议**: HTTP REST
- **用途**: Web UI 和直接 API 调用
- **需要手动启动**

---

## ✅ 正确的 Claude Code 配置

### 配置文件

在 Claude Code 的 MCP 设置中使用：

```json
{
  "mcpServers": {
    "amp": {
      "command": "amp-mcp",
      "cwd": "/home/xp/test/0506",
      "env": {
        "PYTHONPATH": "/home/xp/test/0506"
      }
    }
  }
}
```

### 重要提示

1. **不要手动启动 amp-mcp** - Claude Code 会自动启动它
2. **不要使用 uvicorn** - 那是 REST API 服务器
3. **确保配置中使用 `amp-mcp` 命令**

---

## 🧪 测试 MCP 服务器

### 测试 1: 验证命令可用

```bash
cd /home/xp/test/0506
which amp-mcp
# 应该输出: /home/xp/miniforge3/bin/amp-mcp
```

### 测试 2: 手动测试 MCP 协议

```bash
# 发送 initialize 请求
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | amp-mcp
```

应该返回类似：
```json
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"amp","version":"0.1.0"}}}
```

### 测试 3: 运行测试脚本

```bash
python amp/mcp/test_mcp_server.py
```

应该显示：
```
✓ All tests passed!
```

---

## 🔧 故障排除

### 问题 1: "command not found: amp-mcp"

**解决方案**:
```bash
cd /home/xp/test/0506
pip install -e .
```

### 问题 2: Claude Code 报告 "MCP startup failed"

**可能原因**:
1. 配置文件路径错误
2. Python 环境不正确
3. 依赖包未安装

**解决方案**:
```bash
# 1. 检查配置
cat claude_code_mcp_config.json

# 2. 测试命令
amp-mcp --help 2>&1 | head -5

# 3. 重新安装
pip install -e .
```

### 问题 3: "Deserialize error: data did not match any variant"

**原因**: 这个错误说明 Claude Code 连接到了 REST API 服务器而不是 MCP 服务器

**解决方案**:
1. 停止所有 uvicorn 进程：`pkill -f uvicorn`
2. 确认配置使用 `amp-mcp` 命令
3. 重启 Claude Code

---

## 📋 正确的使用流程

### 步骤 1: 确认安装

```bash
cd /home/xp/test/0506
pip install -e .
amp-mcp --version 2>&1 | head -1
```

### 步骤 2: 测试 MCP 服务器

```bash
python amp/mcp/test_mcp_server.py
```

### 步骤 3: 配置 Claude Code

将 `claude_code_mcp_config.json` 的内容添加到 Claude Code 的 MCP 设置中。

### 步骤 4: 重启 Claude Code

重启后，Claude Code 会自动启动 `amp-mcp` 进程。

### 步骤 5: 验证集成

在 Claude Code 中：
```
> 列出所有 AMP 工具
```

---

## 🎯 两种服务器的使用场景

### 场景 1: 使用 Claude Code（推荐）

```bash
# 不需要手动启动任何服务器
# Claude Code 会自动启动 amp-mcp
```

在 Claude Code 中：
```
> 使用 AMP 创建隧道
> 显示网络拓扑
```

### 场景 2: 使用 Web UI

```bash
# 启动 REST API 服务器
python amp/mcp/run_server.py

# 访问 Web UI
open http://127.0.0.1:8899
```

### 场景 3: 同时使用两者

```bash
# 终端 1: 启动 REST API 服务器（用于 Web UI）
python amp/mcp/run_server.py

# 终端 2: Claude Code 会自动启动 amp-mcp（用于 MCP）
# 不需要手动操作
```

---

## ✅ 检查清单

在配置 Claude Code 之前，确认：

- [ ] `amp-mcp` 命令可用（`which amp-mcp`）
- [ ] 测试脚本通过（`python amp/mcp/test_mcp_server.py`）
- [ ] 配置文件正确（使用 `amp-mcp` 而不是 `uvicorn`）
- [ ] 没有运行 uvicorn 服务器（`pkill -f uvicorn`）
- [ ] Python 环境正确（`which python`）

---

## 🎉 成功标志

当配置正确时，您会看到：

1. Claude Code 启动时没有 MCP 错误
2. 可以在 Claude Code 中列出 AMP 工具
3. 可以成功调用 AMP 工具

---

**记住**: 
- ❌ 不要使用 `uvicorn amp.mcp.server:create_app` 用于 Claude Code
- ✅ 使用 `amp-mcp` 命令（在配置文件中，由 Claude Code 自动启动）
