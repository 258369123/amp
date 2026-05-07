# 🎯 同时使用 MCP 和 Web UI 的完整指南

## 概述

AMP 平台提供两种接口，可以**同时使用**：

1. **MCP 协议** - 用于 Claude Code 集成
2. **Web UI + REST API** - 用于可视化和直接操作

---

## 🚀 推荐使用方式

### 方案 A: Claude Code + Web UI（推荐）

这是最佳使用方式，结合了两者的优势：

#### 步骤 1: 启动 Web UI 服务器

```bash
cd /home/xp/test/0506

# 启动 REST API 服务器（用于 Web UI）
python amp/mcp/run_server.py > web_ui.log 2>&1 &

# 记录 PID
echo $! > web_ui.pid
```

服务器启动后，Web UI 可在 http://127.0.0.1:8899 访问。

#### 步骤 2: 配置 Claude Code

在 Claude Code 的 MCP 设置中添加：

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

#### 步骤 3: 重启 Claude Code

Claude Code 会自动启动 MCP 服务器（`amp-mcp`）。

#### 步骤 4: 开始使用

**在 Claude Code 中**：
```
> 使用 AMP 创建一个到 192.168.1.100 的隧道
> 列出所有活跃的隧道
```

**在浏览器中**：
- 打开 http://127.0.0.1:8899
- 查看实时网络拓扑图
- 监控隧道和 Shell 状态

---

## 🔄 工作流示例

### 示例 1: 创建隧道并可视化

**在 Claude Code 中**：
```
> 创建一个 Chisel 隧道到 192.168.1.100:22，本地端口 8080
```

Claude 会调用 `create_tunnel` 工具创建隧道。

**在 Web UI 中**：
- 刷新页面（或等待 5 秒自动刷新）
- 在拓扑图中看到新的隧道节点
- 点击节点查看详细信息

### 示例 2: 执行命令并查看历史

**在 Claude Code 中**：
```
> 在 shell-123 中执行 whoami 命令
```

**在 Web UI 中**：
- 查看"Recent Operations"部分
- 看到刚执行的命令和输出

### 示例 3: 规划路由并执行

**在 Web UI 中**：
- 查看当前网络拓扑
- 识别需要的路由路径

**在 Claude Code 中**：
```
> 根据拓扑图，创建从 external 到 internal 的隧道链
```

---

## 📊 两种接口的优势

### MCP 协议（Claude Code）的优势

✅ **自然语言交互** - 用自然语言描述需求  
✅ **智能决策** - Claude 理解上下文并做出决策  
✅ **自动化工作流** - 一次性完成多步操作  
✅ **上下文感知** - 记住之前的操作  

**适合场景**：
- 复杂的多步操作
- 需要决策的任务
- 探索性测试
- 快速原型

### Web UI 的优势

✅ **可视化** - 直观的网络拓扑图  
✅ **实时监控** - 自动刷新状态  
✅ **快速浏览** - 一目了然的仪表板  
✅ **点击操作** - 直接点击节点查看详情  

**适合场景**：
- 监控系统状态
- 可视化网络结构
- 快速查看信息
- 演示和报告

---

## 🛠️ 实用脚本

### 启动脚本

创建 `start_amp.sh`：

```bash
#!/bin/bash
cd /home/xp/test/0506

# 启动 Web UI 服务器
echo "Starting Web UI server..."
python amp/mcp/run_server.py > web_ui.log 2>&1 &
WEB_PID=$!
echo $WEB_PID > web_ui.pid
echo "Web UI started (PID: $WEB_PID)"
echo "Access at: http://127.0.0.1:8899"

# 等待服务器启动
sleep 3

# 检查服务器状态
if curl -s http://127.0.0.1:8899/health > /dev/null; then
    echo "✓ Web UI is healthy"
else
    echo "✗ Web UI failed to start"
    exit 1
fi

echo ""
echo "AMP Platform is ready!"
echo "- Web UI: http://127.0.0.1:8899"
echo "- MCP: Configure Claude Code and restart"
echo ""
echo "To stop: ./stop_amp.sh"
```

### 停止脚本

创建 `stop_amp.sh`：

```bash
#!/bin/bash
cd /home/xp/test/0506

# 停止 Web UI 服务器
if [ -f web_ui.pid ]; then
    PID=$(cat web_ui.pid)
    echo "Stopping Web UI (PID: $PID)..."
    kill $PID 2>/dev/null
    rm web_ui.pid
    echo "✓ Web UI stopped"
else
    echo "No Web UI PID file found"
    pkill -f "python amp/mcp/run_server.py"
fi

echo "AMP Platform stopped"
```

### 状态检查脚本

创建 `check_amp.sh`：

```bash
#!/bin/bash

echo "=== AMP Platform Status ==="
echo ""

# 检查 Web UI
if curl -s http://127.0.0.1:8899/health > /dev/null; then
    echo "✓ Web UI: Running (http://127.0.0.1:8899)"
    curl -s http://127.0.0.1:8899/health | jq -r '"  Version: \(.version) | Status: \(.status)"'
else
    echo "✗ Web UI: Not running"
fi

echo ""

# 检查 MCP 命令
if command -v amp-mcp &> /dev/null; then
    echo "✓ MCP command: Available"
else
    echo "✗ MCP command: Not found"
fi

echo ""

# 检查数据库
if [ -f amp.db ]; then
    echo "✓ Database: Exists"
    sqlite3 amp.db "SELECT COUNT(*) FROM tunnels" 2>/dev/null | xargs echo "  Tunnels:"
    sqlite3 amp.db "SELECT COUNT(*) FROM shells" 2>/dev/null | xargs echo "  Shells:"
else
    echo "✗ Database: Not found"
fi

echo ""
echo "==========================="
```

---

## 📋 完整工作流程

### 1. 启动环境

```bash
cd /home/xp/test/0506

# 启动 Web UI
./start_amp.sh

# 或手动启动
python amp/mcp/run_server.py > web_ui.log 2>&1 &
```

### 2. 打开工具

- **浏览器**: 打开 http://127.0.0.1:8899
- **Claude Code**: 启动并确认 MCP 连接成功

### 3. 使用场景

#### 场景 A: 创建隧道链

**Claude Code**:
```
> 创建一个多层隧道：
> 1. 从本地到 DMZ (192.168.1.100:22)
> 2. 从 DMZ 到内网 (10.0.0.50:22)
```

**Web UI**:
- 查看拓扑图中的隧道链
- 验证连接状态

#### 场景 B: 执行命令

**Claude Code**:
```
> 在内网 Shell 中执行网络扫描
```

**Web UI**:
- 在"Recent Operations"中查看命令历史
- 监控 Shell 状态

#### 场景 C: 故障排查

**Web UI**:
- 发现某个隧道状态异常
- 点击查看详细错误信息

**Claude Code**:
```
> 重启 tunnel-123 并检查日志
```

### 4. 监控和维护

**Web UI**:
- 实时监控所有资源状态
- 查看网络拓扑变化

**Claude Code**:
- 定期清理过期资源
- 自动化维护任务

---

## 🎯 最佳实践

### 1. 始终保持 Web UI 运行

```bash
# 使用 nohup 确保后台运行
nohup python amp/mcp/run_server.py > web_ui.log 2>&1 &
```

### 2. 定期检查状态

```bash
# 每小时检查一次
./check_amp.sh
```

### 3. 使用 Claude Code 进行复杂操作

```
> 分析当前网络拓扑，找出最优路径到达 10.0.0.50
> 创建必要的隧道链
> 测试连接性
```

### 4. 使用 Web UI 进行监控

- 保持浏览器标签页打开
- 利用自动刷新功能
- 快速识别问题

---

## 🔧 故障排除

### 问题 1: Web UI 无法访问

```bash
# 检查服务器是否运行
ps aux | grep "python amp/mcp/run_server.py"

# 检查端口
lsof -i :8899

# 重启服务器
pkill -f "python amp/mcp/run_server.py"
python amp/mcp/run_server.py > web_ui.log 2>&1 &
```

### 问题 2: Claude Code MCP 连接失败

```bash
# 测试 MCP 命令
amp-mcp --version

# 运行测试
python amp/mcp/test_mcp_server.py

# 检查配置
cat claude_code_mcp_config.json
```

### 问题 3: 数据不同步

Web UI 和 Claude Code 使用同一个数据库，数据应该是同步的。如果不同步：

```bash
# 检查数据库
sqlite3 amp.db ".tables"

# 刷新 Web UI
# 按 F5 或等待自动刷新
```

---

## 📊 资源使用

### 内存使用

- **Web UI 服务器**: ~100-200 MB
- **MCP 服务器**: ~50-100 MB（按需启动）
- **总计**: ~150-300 MB

### 端口使用

- **Web UI**: 8899 (HTTP)
- **MCP**: 无（stdio 传输）

---

## 🎉 总结

**推荐配置**：

1. ✅ **始终运行 Web UI** - 用于监控和可视化
2. ✅ **配置 Claude Code MCP** - 用于智能操作
3. ✅ **两者配合使用** - 发挥各自优势

**工作流**：
- 用 Claude Code 执行操作
- 用 Web UI 监控状态
- 用 Claude Code 分析和决策
- 用 Web UI 验证结果

这样可以获得最佳的使用体验！🚀
