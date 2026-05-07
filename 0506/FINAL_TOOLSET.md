# 🎯 AMP 修复后的最终工具集

## 保留的核心工具（12 个）

### Shell 管理（5 个）✅

1. **create_shell**
   - 创建 Shell 会话（bind/reverse/ssh）
   - 修复：添加连接验证，避免假成功

2. **execute_command**
   - 在 Shell 中执行命令
   - 修复：增强 prompt 识别，支持真实 bash

3. **close_shell**
   - 关闭 Shell 会话
   - 保持不变

4. **list_shells**
   - 列出 Shell（支持状态过滤）
   - 修复：支持 all/active/dead，提供完整视图

5. **get_shell_status**
   - 获取 Shell 状态和信息
   - 保持不变

---

### Tunnel 管理（6 个）✅

6. **create_tunnel**
   - 创建网络隧道（chisel/ligolo/ssh）
   - 保持不变

7. **start_tunnel**
   - 启动隧道
   - 保持不变

8. **stop_tunnel**
   - 停止隧道
   - 保持不变

9. **delete_tunnel**
   - 删除隧道
   - 保持不变

10. **list_tunnels**
    - 列出所有隧道（支持状态过滤）
    - 保持不变

11. **get_tunnel_status**
    - 获取隧道状态和统计
    - 保持不变

---

### 状态查询（1 个）✅

12. **get_current_state**
    - 获取当前完整状态（tunnels + shells + operations）
    - 新增：替代复杂的上下文工具
    - 返回黑板状态

---

## 删除的工具（5 个）

### 上下文管理（3 个）❌

13. ~~get_relevant_operations~~ - 删除
    - 原因：功能重复，get_current_state 已包含
    
14. ~~build_prompt~~ - 删除
    - 原因：AI 不需要帮它构建提示
    
15. ~~compress_context~~ - 删除
    - 原因：解决不存在的问题

### 网络拓扑（2 个）❌

16. ~~visualize_topology~~ - 删除
    - 原因：返回图形文本，AI 看不懂
    - 替代：get_current_state 返回结构化数据
    
17. ~~get_affected_segments~~ - 删除
    - 原因：使用场景不明确，实战中无用

---

## 可选保留（1 个）⚠️

18. **find_route** - 可选
    - 查找网络路由路径
    - 有一定价值，但可能过于复杂
    - 建议：简化实现或暂时保留

---

## 最终工具集对比

| 类别 | 修复前 | 修复后 |
|------|--------|--------|
| **Shell 管理** | 4 | 5 |
| **Tunnel 管理** | 6 | 6 |
| **状态查询** | 0 | 1 |
| **上下文管理** | 3 | 0 |
| **网络拓扑** | 3 | 0-1 |
| **命令执行** | 1 | 0 (合并到 Shell) |
| **总计** | 17 | 12-13 |

---

## 工具功能详解

### Shell 管理工具

```python
# 1. create_shell - 创建 Shell
{
  "name": "target-shell",
  "shell_type": "bind",  # bind/reverse/ssh
  "target_host": "192.168.1.100",
  "target_port": 22,
  "os_type": "linux"
}
# 修复：创建前验证连接

# 2. execute_command - 执行命令
{
  "shell_id": "shell-123",
  "command": "whoami",
  "timeout": 30
}
# 修复：支持彩色/多行 bash 提示符

# 3. close_shell - 关闭 Shell
{
  "shell_id": "shell-123"
}

# 4. list_shells - 列出 Shell
{
  "status": "all"  # all/active/dead
}
# 修复：支持完整状态过滤

# 5. get_shell_status - 获取状态
{
  "shell_id": "shell-123"
}
```

### Tunnel 管理工具

```python
# 6. create_tunnel - 创建隧道
{
  "name": "dmz-tunnel",
  "tunnel_type": "chisel",
  "local_port": 8080,
  "remote_host": "192.168.1.100",
  "remote_port": 22
}

# 7. start_tunnel - 启动隧道
{
  "tunnel_id": "tunnel-123"
}

# 8. stop_tunnel - 停止隧道
{
  "tunnel_id": "tunnel-123"
}

# 9. delete_tunnel - 删除隧道
{
  "tunnel_id": "tunnel-123"
}

# 10. list_tunnels - 列出隧道
{
  "status": "active"  # 可选过滤
}

# 11. get_tunnel_status - 获取状态
{
  "tunnel_id": "tunnel-123"
}
```

### 状态查询工具

```python
# 12. get_current_state - 获取当前状态
{}  # 无参数

# 返回：
{
  "tunnels": [
    {
      "id": "tunnel-123",
      "name": "dmz-tunnel",
      "type": "chisel",
      "status": "active",
      "local_port": 8080,
      "remote": "192.168.1.100:22"
    }
  ],
  "shells": [
    {
      "id": "shell-123",
      "name": "target-shell",
      "type": "bind",
      "status": "active",
      "target": "192.168.1.100",
      "os": "linux"
    }
  ],
  "network": {
    "segments": ["external", "dmz", "internal"],
    "segment_count": 3
  },
  "recent_operations": [
    {
      "command": "whoami",
      "output": "root",
      "timestamp": "2026-05-07T12:00:00Z"
    }
  ]
}
```

---

## 工具使用场景

### 场景 1: 建立内网访问

```
Agent: 帮我建立到 10.0.0.50 的访问路径

AMP 工具调用：
1. get_current_state() - 查看当前状态
2. create_tunnel(dmz-tunnel, 192.168.1.100:22) - 创建第一层
3. start_tunnel(tunnel-1) - 启动
4. create_tunnel(internal-tunnel, 10.0.0.50:22, parent=tunnel-1) - 创建第二层
5. start_tunnel(tunnel-2) - 启动
6. get_current_state() - 验证状态
```

### 场景 2: 执行命令

```
Agent: 在目标主机上执行 whoami

AMP 工具调用：
1. list_shells(status="active") - 查看可用 Shell
2. execute_command(shell-123, "whoami") - 执行命令
3. get_shell_status(shell-123) - 检查状态
```

### 场景 3: 资源清理

```
Agent: 清理所有死掉的 Shell

AMP 工具调用：
1. list_shells(status="dead") - 列出死 Shell
2. close_shell(shell-1) - 逐个关闭
3. close_shell(shell-2)
4. get_current_state() - 验证清理结果
```

---

## 核心优势

### 简化后的优势

1. **更专注** - 只保留核心执行能力
2. **更可靠** - 删除不稳定的复杂功能
3. **更易用** - 工具职责清晰
4. **更快速** - 无冷启动，无阻塞

### 符合初心

✅ **AI 的"手"** - Shell/Tunnel 执行工具  
✅ **AI 的"眼"** - 状态查询工具  
❌ **不是 AI 的"大脑"** - 删除了"替 AI 思考"的工具

---

## 总结

**最终工具集**: **12 个核心工具**

- **Shell 管理**: 5 个（修复后更可靠）
- **Tunnel 管理**: 6 个（保持稳定）
- **状态查询**: 1 个（新增，简单高效）

**删除**: 5 个过度设计的工具

**核心理念**: Simple > Smart

让 AMP 成为简单可靠的执行工具，而不是试图比 Claude 更聪明的系统。
