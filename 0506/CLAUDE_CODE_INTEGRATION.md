# AMP 平台与 Claude Code 集成指南

本指南介绍如何将 AMP 平台与 Claude Code CLI 集成，使 Claude 能够通过 MCP (Model Context Protocol) 使用 AMP 的渗透测试功能。

---

## 📋 前置要求

1. **Python 3.11+** 已安装
2. **Claude Code CLI** 已安装并配置
3. **AMP 平台** 已部署（本项目）
4. **依赖包** 已安装

---

## 🚀 快速开始

### 1. 安装 AMP 依赖

```bash
cd /home/xp/test/0506

# 安装依赖
pip install -e .

# 或者手动安装
pip install fastapi uvicorn sqlalchemy pydantic pydantic-settings \
    chromadb sentence-transformers psutil pexpect
```

### 2. 配置 AMP 服务器

创建配置文件 `.env`:

```bash
# 数据库配置
DATABASE_URL=sqlite:///./amp.db

# MCP 服务器配置
MCP_HOST=127.0.0.1
MCP_PORT=8000
MCP_AUTH_TOKEN=your-secret-token-here

# 隧道配置
CHISEL_BINARY=/usr/local/bin/chisel
LIGOLO_BINARY=/usr/local/bin/ligolo-ng

# 向量数据库配置
VECTOR_DB_PATH=./chroma_db
```

### 3. 启动 AMP MCP 服务器

```bash
# 方式 1: 使用 uvicorn 直接启动
uvicorn amp.mcp.server:create_app --factory --host 127.0.0.1 --port 8000

# 方式 2: 使用 Python 脚本启动
python -m amp.mcp.server

# 方式 3: 后台运行
nohup uvicorn amp.mcp.server:create_app --factory --host 127.0.0.1 --port 8000 > amp.log 2>&1 &
```

服务器启动后，访问 http://localhost:8000 查看 Web UI。

### 4. 配置 Claude Code MCP 集成

#### 方法 A: 使用 MCP 配置文件

创建或编辑 `~/.claude/mcp_servers.json`:

```json
{
  "amp": {
    "command": "python",
    "args": ["-m", "amp.mcp.server"],
    "env": {
      "DATABASE_URL": "sqlite:///./amp.db",
      "MCP_HOST": "127.0.0.1",
      "MCP_PORT": "8000",
      "MCP_AUTH_TOKEN": "your-secret-token-here"
    }
  }
}
```

#### 方法 B: 使用 HTTP MCP 服务器

如果 Claude Code 支持 HTTP MCP 服务器，配置如下：

```json
{
  "amp": {
    "type": "http",
    "url": "http://127.0.0.1:8000",
    "headers": {
      "Authorization": "Bearer your-secret-token-here"
    }
  }
}
```

### 5. 验证集成

启动 Claude Code 并测试 AMP 工具：

```bash
# 启动 Claude Code
claude

# 在 Claude Code 中测试
> 列出所有可用的 AMP 工具
> 创建一个到 192.168.1.100 的 Chisel 隧道
> 查看当前网络拓扑
```

---

## 🔧 可用的 MCP 工具

AMP 平台提供 17 个 MCP 工具，分为 4 类：

### 隧道管理工具 (6 个)

1. **create_tunnel** - 创建新隧道
   ```json
   {
     "name": "dmz-tunnel",
     "tunnel_type": "chisel",
     "local_port": 8080,
     "remote_host": "192.168.1.100",
     "remote_port": 22
   }
   ```

2. **start_tunnel** - 启动隧道
   ```json
   {"tunnel_id": "tunnel-uuid"}
   ```

3. **stop_tunnel** - 停止隧道
   ```json
   {"tunnel_id": "tunnel-uuid"}
   ```

4. **delete_tunnel** - 删除隧道
   ```json
   {"tunnel_id": "tunnel-uuid"}
   ```

5. **list_tunnels** - 列出所有隧道
   ```json
   {"status": "active"}  // 可选过滤
   ```

6. **get_tunnel_status** - 获取隧道状态
   ```json
   {"tunnel_id": "tunnel-uuid"}
   ```

### Shell 管理工具 (5 个)

7. **create_shell** - 创建 Shell 会话
   ```json
   {
     "name": "target-shell",
     "shell_type": "reverse",
     "target_host": "192.168.1.100",
     "os_type": "linux"
   }
   ```

8. **execute_command** - 执行命令
   ```json
   {
     "shell_id": "shell-uuid",
     "command": "whoami",
     "timeout": 30
   }
   ```

9. **close_shell** - 关闭 Shell
   ```json
   {"shell_id": "shell-uuid"}
   ```

10. **list_shells** - 列出所有 Shell
    ```json
    {"status": "active"}  // 可选过滤
    ```

11. **get_shell_status** - 获取 Shell 状态
    ```json
    {"shell_id": "shell-uuid"}
    ```

### 上下文查询工具 (3 个)

12. **get_relevant_operations** - 获取相关操作历史
    ```json
    {
      "query": "list files",
      "shell_id": "shell-uuid",
      "limit": 10
    }
    ```

13. **build_prompt** - 构建动态提示
    ```json
    {
      "query": "enumerate network",
      "context": {"shell_id": "shell-uuid"}
    }
    ```

14. **compress_context** - 压缩上下文
    ```json
    {
      "operations": [...],
      "max_tokens": 8000
    }
    ```

### 网络拓扑工具 (3 个)

15. **visualize_topology** - 可视化拓扑
    ```json
    {"format": "mermaid"}  // 或 "ascii", "summary"
    ```

16. **find_route** - 查找路由
    ```json
    {
      "source": "external",
      "target": "internal"
    }
    ```

17. **get_affected_segments** - 获取受影响的网段
    ```json
    {"tunnel_id": "tunnel-uuid"}
    ```

---

## 💡 使用示例

### 示例 1: 创建多层隧道

```python
# 在 Claude Code 中
> 帮我创建一个多层隧道到内网

# Claude 会自动调用 AMP 工具：
1. create_tunnel(name="dmz-tunnel", tunnel_type="chisel", 
                 local_port=8080, remote_host="192.168.1.100", remote_port=22)
2. start_tunnel(tunnel_id="tunnel-1")
3. create_tunnel(name="internal-tunnel", tunnel_type="chisel",
                 local_port=9090, remote_host="10.0.0.50", remote_port=22,
                 parent_id="tunnel-1")
4. start_tunnel(tunnel_id="tunnel-2")
5. visualize_topology(format="mermaid")
```

### 示例 2: 创建 Shell 并执行命令

```python
# 在 Claude Code 中
> 在目标主机上创建一个 Shell 并列出文件

# Claude 会自动调用：
1. create_shell(name="target-shell", shell_type="reverse",
                target_host="192.168.1.100", os_type="linux")
2. execute_command(shell_id="shell-1", command="ls -la", timeout=30)
3. get_relevant_operations(query="list files", shell_id="shell-1")
```

### 示例 3: 网络拓扑分析

```python
# 在 Claude Code 中
> 显示当前网络拓扑并找到到内网的最优路径

# Claude 会自动调用：
1. visualize_topology(format="mermaid")
2. find_route(source="external", target="internal")
3. get_affected_segments(tunnel_id="tunnel-1")
```

---

## 🔐 安全配置

### 1. 配置认证 Token

在 `.env` 文件中设置强密码：

```bash
MCP_AUTH_TOKEN=$(openssl rand -hex 32)
```

### 2. 限制访问

只允许本地访问：

```bash
MCP_HOST=127.0.0.1  # 不要使用 0.0.0.0
```

### 3. 使用 HTTPS（生产环境）

```bash
# 生成自签名证书
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

# 启动时使用 SSL
uvicorn amp.mcp.server:create_app --factory \
  --host 127.0.0.1 --port 8000 \
  --ssl-keyfile=key.pem --ssl-certfile=cert.pem
```

---

## 🧪 测试集成

### 1. 测试 MCP 服务器

```bash
# 检查健康状态
curl http://localhost:8000/health

# 列出所有工具
curl http://localhost:8000/tools

# 测试工具执行
curl -X POST http://localhost:8000/tools/list_tunnels \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-secret-token-here" \
  -d '{"parameters": {}}'
```

### 2. 测试 Web UI

打开浏览器访问 http://localhost:8000，应该看到：
- 实时拓扑图
- 状态仪表板
- 隧道和 Shell 列表

### 3. 测试 Claude Code 集成

```bash
# 启动 Claude Code
claude

# 测试命令
> 列出所有 AMP 工具
> 显示当前网络拓扑
> 创建一个测试隧道
```

---

## 🐛 故障排除

### 问题 1: MCP 服务器无法启动

**症状**: `uvicorn` 命令失败

**解决方案**:
```bash
# 检查依赖
pip install -r requirements.txt

# 检查端口占用
lsof -i :8000

# 查看详细错误
uvicorn amp.mcp.server:create_app --factory --log-level debug
```

### 问题 2: Claude Code 无法连接

**症状**: Claude Code 报告 MCP 服务器不可用

**解决方案**:
```bash
# 1. 确认服务器正在运行
curl http://localhost:8000/health

# 2. 检查配置文件
cat ~/.claude/mcp_servers.json

# 3. 查看 Claude Code 日志
tail -f ~/.claude/logs/mcp.log
```

### 问题 3: 工具执行失败

**症状**: 工具调用返回错误

**解决方案**:
```bash
# 1. 检查数据库
sqlite3 amp.db ".tables"

# 2. 查看服务器日志
tail -f amp.log

# 3. 测试工具直接调用
curl -X POST http://localhost:8000/tools/list_tunnels \
  -H "Content-Type: application/json" \
  -d '{"parameters": {}}'
```

---

## 📚 高级配置

### 1. 自定义工具注册

编辑 `amp/mcp/tools/registry.py` 添加自定义工具：

```python
from amp.mcp.protocol import ToolParameter, ParameterType
from amp.mcp.tool_registry import tool_registry

def my_custom_tool(param1: str, param2: int) -> dict:
    # 实现自定义逻辑
    return {"success": True, "data": {...}}

# 注册工具
tool_registry.register_tool(
    name="my_custom_tool",
    func=my_custom_tool,
    description="My custom tool description",
    parameters=[
        ToolParameter(name="param1", type=ParameterType.STRING, required=True),
        ToolParameter(name="param2", type=ParameterType.INTEGER, required=True),
    ]
)
```

### 2. 配置日志级别

在 `.env` 中添加：

```bash
LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR
LOG_FILE=amp.log
```

### 3. 配置数据库

使用 PostgreSQL 替代 SQLite：

```bash
DATABASE_URL=postgresql://user:password@localhost/amp_db
```

---

## 🎯 最佳实践

1. **始终使用认证** - 在生产环境中启用 Bearer token 认证
2. **限制网络访问** - 只允许本地或受信任的网络访问
3. **定期备份数据库** - 备份 `amp.db` 和 `chroma_db/`
4. **监控日志** - 定期检查 `amp.log` 查找异常
5. **更新依赖** - 定期更新 Python 包以获取安全补丁
6. **测试工具** - 在生产环境使用前先在测试环境验证

---

## 📖 相关文档

- [PROJECT_SUMMARY.md](./PROJECT_SUMMARY.md) - 项目总览
- [README.md](./README.md) - 项目介绍
- [amp/mcp/README.md](./amp/mcp/README.md) - MCP 服务器文档
- [OpenAPI 文档](http://localhost:8000/docs) - 自动生成的 API 文档

---

## 🤝 获取帮助

如果遇到问题：

1. 查看 [故障排除](#-故障排除) 部分
2. 检查服务器日志 `amp.log`
3. 访问 Web UI 查看系统状态
4. 查看 OpenAPI 文档了解 API 详情

---

## 🎉 开始使用

现在您已经了解如何集成 AMP 平台与 Claude Code，可以开始使用了！

```bash
# 1. 启动 AMP 服务器
uvicorn amp.mcp.server:create_app --factory --host 127.0.0.1 --port 8000

# 2. 打开 Web UI
open http://localhost:8000

# 3. 启动 Claude Code
claude

# 4. 开始使用 AMP 工具！
> 帮我创建一个到 DMZ 的隧道并列出网络拓扑
```

祝您使用愉快！🚀
