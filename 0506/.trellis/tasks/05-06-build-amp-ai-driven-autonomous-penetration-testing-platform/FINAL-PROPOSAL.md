# AMP 最终技术方案

## 研究完成 ✅

所有 4 个研究 agent 已完成调研，共生成 4 份详细文档（总计 ~5000 行）：

1. ✅ Shell session management patterns
2. ✅ MCP protocol best practices
3. ✅ Tunnel management patterns
4. ✅ Context compression strategies

---

## 核心技术决策（基于研究结果）

### 1. 架构选型

| 组件 | 技术选择 | 理由 |
|------|---------|------|
| **MCP 传输** | stdio | 单用户部署更简单、更安全 |
| **隧道技术** | Chisel (主) + Ligolo-ng (备) | Chisel 易用性好，Ligolo-ng 用于 Layer 3 场景 |
| **Shell 持久化** | tmux (Linux) + PowerShell Remoting (Windows) | 行业标准，成熟可靠 |
| **状态存储** | SQLite | 轻量级，支持重启恢复 |
| **向量存储** | ChromaDB | 嵌入式，无需独立服务 |
| **嵌入模型** | all-MiniLM-L6-v2 | 384 维，快速，质量好 |
| **容器隔离** | Docker | 安全沙箱，环境一致 |

### 2. 隧道管理设计

**健康监控策略**：混合模式
- 被动监控：跟踪最后活动时间
- 主动探测：30 秒心跳间隔（仅在被动失败时启用）
- 失败阈值：3 次心跳失败

**故障恢复**：
- 自动重连：指数退避（1s, 2s, 4s, 8s, 16s）
- 最大重试：5 次
- 级联清理：通过依赖图自动清理下游隧道

**性能优化**：
- 连接池：每个隧道 10 个连接
- 隧道链限制：最多 3 跳（防止延迟放大）
- 端口范围：10000-20000

**状态机**：
```
CREATING → ACTIVE → DISCONNECTED → RECONNECTING → DEAD
```

### 3. Shell 管理设计

**Linux 目标**：
- tmux 后端：`tmux new-session -d -s <name>`
- PTY 分配：`pty.spawn()` 实现完整 TTY
- Shell 升级：`python -c 'import pty; pty.spawn("/bin/bash")'`

**Windows 目标**：
- PowerShell 优先：`powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass`
- WinRM 远程：`Enter-PSSession -ComputerName target`
- UAC 绕过：fodhelper, eventvwr（研究文档中有详细实现）

**命令执行**：
- 超时控制：默认 30 秒
- 异步执行：长时间命令使用 asyncio
- 流式输出：防止内存溢出
- 进程组管理：确保完整清理

**状态跟踪**：
- 工作目录、环境变量、权限级别
- 僵尸进程检测（psutil）
- 优雅降级（fallback shell）

### 4. 上下文引擎设计

**Token 预算分配**（8000 tokens 总计）：
- 系统提示：18.75% (1500 tokens)
- 当前任务：10% (800 tokens)
- 活跃资源：15% (1200 tokens) - 隧道、shell
- 近期历史：20% (1600 tokens) - 最近 10-20 个操作
- 检索上下文：15% (1200 tokens) - 向量搜索结果
- 网络拓扑：7.5% (600 tokens) - 图可视化
- 错误上下文：5% (400 tokens) - 近期失败
- 缓冲区：8.75% (700 tokens) - 溢出保护

**压缩策略**：
- 层次化摘要：L0（当前任务）→ L1（近期操作）→ L2（向量搜索）→ L3（SQLite 归档）
- 滑动窗口：最近 5 个操作全细节，6-20 摘要，21-100 仅命令，100+ 统计
- 语义去重：合并相似操作（如多个 `ls` 命令）
- 预期压缩比：85-92%

**相关性评分**（多因子算法）：
- 语义相似度：30%
- 时间衰减：20%
- 任务对齐：25%
- 依赖关系：15%
- 结果重要性：10%

**渐进式披露**：
- 仅显示与当前任务相关的隧道和 shell
- 按需加载详细历史（通过向量搜索）
- 突出显示关键状态变化（提权、新网段）

### 5. MCP Server 设计

**工具定义**（7 个核心工具）：
1. `create_tunnel(target, method, pivot_host)` - 创建隧道
2. `execute_command(shell_id, command, timeout)` - 执行命令
3. `get_context(task_description, detail_level)` - 获取上下文摘要
4. `scan_network(target, tunnel_id, scan_type)` - 网络扫描
5. `create_shell(target, method, tunnel_id, payload)` - 建立 shell
6. `upload_file(shell_id, local_path, remote_path)` - 上传文件
7. `visualize_topology(format)` - 生成拓扑图

**工具设计原则**：
- 清晰命名：动词_名词模式
- 参数验证：Pydantic 模型
- 结构化错误：错误码 + 重试建议
- 幂等操作：create_tunnel 检查是否已存在

**长时间操作**：
- 网络扫描使用异步模式（返回 operation_id）
- 提供状态查询工具
- 可配置超时限制

**安全措施**：
- Token 认证
- 输入验证（防止命令注入）
- 资源限制（20 隧道，50 shell）
- 审计日志（不可篡改）

---

## 数据模型

### SQLite Schema

```sql
-- 隧道表
CREATE TABLE tunnels (
    id TEXT PRIMARY KEY,
    method TEXT NOT NULL,  -- chisel, ligolo, ssh
    target TEXT NOT NULL,
    pivot_host TEXT,
    parent_id TEXT,  -- 嵌套隧道的父 ID
    local_port INTEGER,
    remote_port INTEGER,
    status TEXT NOT NULL,  -- creating, active, disconnected, reconnecting, dead
    created_at TIMESTAMP,
    last_heartbeat TIMESTAMP,
    metadata JSON,
    FOREIGN KEY (parent_id) REFERENCES tunnels(id)
);

-- Shell 表
CREATE TABLE shells (
    id TEXT PRIMARY KEY,
    target TEXT NOT NULL,
    method TEXT NOT NULL,  -- reverse, bind, ssh
    tunnel_id TEXT,
    tmux_session TEXT,
    user TEXT,
    privilege TEXT,  -- user, root, SYSTEM
    os_type TEXT,  -- linux, windows
    working_directory TEXT,
    environment_vars JSON,
    status TEXT NOT NULL,  -- active, idle, dead
    created_at TIMESTAMP,
    last_activity TIMESTAMP,
    FOREIGN KEY (tunnel_id) REFERENCES tunnels(id)
);

-- 操作历史表
CREATE TABLE operations (
    id TEXT PRIMARY KEY,
    operation_type TEXT NOT NULL,  -- scan, execute, upload
    description TEXT,
    tunnel_id TEXT,
    shell_id TEXT,
    command TEXT,
    result JSON,
    timestamp TIMESTAMP,
    embedding BLOB,  -- 向量嵌入（用于相似度搜索）
    FOREIGN KEY (tunnel_id) REFERENCES tunnels(id),
    FOREIGN KEY (shell_id) REFERENCES shells(id)
);

-- 审计日志表（不可变）
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP NOT NULL,
    user TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id TEXT,
    details JSON,
    success BOOLEAN
);
```

---

## 实现计划（10 周 MVP）

### Phase 1: Foundation (Week 1-2)
- SQLite schema + models
- Chisel wrapper (基础生命周期)
- 健康检查（被动监控）
- 异常体系
- 单元测试

### Phase 2: Execution Layer (Week 3-4)
- 自动重连 + 级联清理
- tmux 后端（Linux shell）
- PowerShell remoting（Windows shell）
- 命令执行 + 状态跟踪
- 集成测试

### Phase 3: Intelligence Layer (Week 5-6)
- ChromaDB 集成
- 向量嵌入 + 相似度搜索
- 上下文压缩逻辑
- 渐进式披露
- Token 预算管理

### Phase 4: Integration (Week 7-8)
- MCP Server（FastAPI + stdio）
- 7 个核心工具实现
- 认证 + 错误处理
- Web UI（拓扑可视化）

### Phase 5: Testing & Polish (Week 9-10)
- Docker 测试环境（多层网络）
- 端到端测试
- 性能基准测试
- 文档 + Docker 镜像

---

## 验收标准

### 功能性
- [ ] 可以创建 Chisel 隧道到远程主机
- [ ] 可以通过隧道建立反向 shell
- [ ] 可以在 shell 中执行命令并获取输出
- [ ] 上下文引擎生成相关提示（< 8000 tokens）
- [ ] MCP server 暴露所有 7 个工具
- [ ] 隧道断开后自动恢复
- [ ] 所有操作记录到 SQLite
- [ ] Docker 隔离防止主机网络访问

### 性能
- [ ] 命令执行 < 5s（本地目标）
- [ ] 向量搜索 < 100ms
- [ ] 上下文压缩比 85-92%
- [ ] 隧道恢复 < 30s

### 可靠性
- [ ] 重启后恢复隧道和 shell 状态
- [ ] 级联失败正确清理下游资源
- [ ] 僵尸进程自动检测和清理
- [ ] 资源限制生效（20 隧道，50 shell）

### 安全性
- [ ] 输入验证防止命令注入
- [ ] Token 认证生效
- [ ] 审计日志不可篡改
- [ ] Docker 容器隔离生效

---

## 下一步行动

请确认以下内容：

1. **技术方案是否满意？** 
   - 架构选型（stdio MCP, Chisel+Ligolo, tmux+PowerShell, SQLite+ChromaDB）
   - 设计决策（混合监控，指数退避，层次化压缩，Token 预算分配）

2. **实现计划是否合理？**
   - 10 周时间线
   - 5 个阶段的优先级顺序

3. **验收标准是否清晰？**
   - 功能性、性能、可靠性、安全性指标

如果你同意，我将：
1. 更新 PRD 文档（添加研究结果和技术决策）
2. 运行 `task.py start` 进入实现阶段
3. 开始 Phase 1 开发（Storage Layer + Tunnel Manager）

请回复：
- "同意，开始实现" - 我将立即开始编码
- 或者提出任何需要调整的地方
