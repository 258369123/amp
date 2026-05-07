# AMP 平台快速启动指南

## ✅ 服务器已成功启动！

您的 AMP MCP 服务器现在正在运行：
- **地址**: http://127.0.0.1:8899
- **状态**: ✅ 健康
- **工具数**: 17 个
- **认证**: Bearer Token (fuckfuck123)

---

## 🎯 验证服务器

### 1. 检查健康状态
```bash
curl http://127.0.0.1:8899/health
```

### 2. 列出所有工具
```bash
curl -H "Authorization: Bearer fuckfuck123" http://127.0.0.1:8899/tools
```

### 3. 测试工具执行
```bash
curl -X POST http://127.0.0.1:8899/tools/list_tunnels \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer fuckfuck123" \
  -d '{"parameters": {}}'
```

### 4. 访问 Web UI
在浏览器中打开: http://127.0.0.1:8899

---

## 🔧 可用的 17 个工具

### 隧道管理 (6)
1. `create_tunnel` - 创建新隧道
2. `start_tunnel` - 启动隧道
3. `stop_tunnel` - 停止隧道
4. `delete_tunnel` - 删除隧道
5. `list_tunnels` - 列出所有隧道
6. `get_tunnel_status` - 获取隧道状态

### Shell 管理 (5)
7. `create_shell` - 创建 Shell 会话
8. `execute_command` - 执行命令
9. `close_shell` - 关闭 Shell
10. `list_shells` - 列出所有 Shell
11. `get_shell_status` - 获取 Shell 状态

### 上下文查询 (3)
12. `get_relevant_operations` - 获取相关操作
13. `build_prompt` - 构建动态提示
14. `compress_context` - 压缩上下文

### 网络拓扑 (3)
15. `visualize_topology` - 可视化拓扑
16. `find_route` - 查找路由
17. `get_affected_segments` - 获取受影响网段

---

## 🚀 与 Claude Code 集成

### 方法 1: 配置 MCP 服务器

创建 `~/.claude/mcp_servers.json`:
```json
{
  "amp": {
    "type": "http",
    "url": "http://127.0.0.1:8899",
    "headers": {
      "Authorization": "Bearer fuckfuck123"
    }
  }
}
```

### 方法 2: 在 Claude Code 中使用

```bash
# 启动 Claude Code
claude

# 使用 AMP 工具
> 列出所有 AMP 工具
> 创建一个到 192.168.1.100 的 Chisel 隧道
> 显示当前网络拓扑
```

---

## 📁 重要文件

- **配置文件**: `.env`
- **数据库**: `amp.db`
- **向量数据库**: `./chroma_db/`
- **日志文件**: `amp_server.log`
- **启动脚本**: `amp/mcp/run_server.py`
- **数据库初始化**: `init_db.py`

---

## 🔄 服务器管理

### 启动服务器
```bash
python amp/mcp/run_server.py > amp_server.log 2>&1 &
```

### 停止服务器
```bash
pkill -f "python amp/mcp/run_server.py"
```

### 查看日志
```bash
tail -f amp_server.log
```

### 重新初始化数据库
```bash
rm amp.db
python init_db.py
```

---

## 🌐 Web UI 功能

访问 http://127.0.0.1:8899 查看：

1. **实时拓扑图** - D3.js 交互式网络图
2. **状态仪表板** - 隧道、Shell、网段统计
3. **详情面板** - 点击节点查看详细信息
4. **自动刷新** - 每 5 秒自动更新

---

## 📊 当前状态

- ✅ 服务器运行中 (PID: 93222)
- ✅ 17 个工具已注册
- ✅ 数据库已初始化
- ✅ Web UI 可访问
- ✅ 认证已配置

---

## 🎉 下一步

1. **测试工具** - 使用 curl 测试各个工具
2. **访问 Web UI** - 在浏览器中查看拓扑
3. **集成 Claude Code** - 配置 MCP 服务器
4. **创建隧道** - 开始使用 AMP 功能

---

## 💡 示例工作流

### 创建隧道并查看拓扑
```bash
# 1. 创建隧道
curl -X POST http://127.0.0.1:8899/tools/create_tunnel \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer fuckfuck123" \
  -d '{
    "parameters": {
      "name": "dmz-tunnel",
      "tunnel_type": "chisel",
      "local_port": 8080,
      "remote_host": "192.168.1.100",
      "remote_port": 22
    }
  }'

# 2. 查看拓扑
curl -X POST http://127.0.0.1:8899/tools/visualize_topology \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer fuckfuck123" \
  -d '{"parameters": {"format": "mermaid"}}'

# 3. 列出所有隧道
curl -X POST http://127.0.0.1:8899/tools/list_tunnels \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer fuckfuck123" \
  -d '{"parameters": {}}'
```

---

## 📖 更多文档

- [PROJECT_SUMMARY.md](./PROJECT_SUMMARY.md) - 项目总览
- [CLAUDE_CODE_INTEGRATION.md](./CLAUDE_CODE_INTEGRATION.md) - 详细集成指南
- [OpenAPI 文档](http://127.0.0.1:8899/docs) - 自动生成的 API 文档

---

**恭喜！AMP 平台已成功部署并运行！** 🎊
