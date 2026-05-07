# 🔧 AMP 平台核心问题修复计划（基于实战反馈）

## 📋 问题根因分析

### 关键发现

1. **AMP 一开始是能工作的**
   - `list_tunnels`, `list_shells`, `visualize_topology` 最初都正常返回
   - 说明不是"启动失败"，而是"运行中卡死"

2. **本地直调工具函数是正常的**
   - 直接调用 `MCPToolAdapter` 的所有工具都能返回
   - 说明工具逻辑本身没问题

3. **问题在 MCP 长驻进程/会话层**
   - 通过 `mcp__amp__` 调用时持续 120s 超时
   - 触发 context/embedding 相关能力后开始卡死
   - 之后连轻量工具也一起超时

4. **冷启动阻塞是导火索**
   - 首次调用 `get_relevant_operations` 触发 79.3MB 模型下载
   - 这次慢调用后，整个 MCP 进程进入"持续超时"状态

5. **记忆系统未真正工作**
   - 数据库为空（operations=0, shells=0, tunnels=0）
   - 没有积累可用上下文
   - 拓扑系统没有沉淀状态

---

## 🚨 核心问题重新定义

### P0-1: MCP 长驻进程稳定性问题 ⚠️

**现象**:
- 运行一段时间后，所有 MCP 调用都超时
- 冷启动阻塞后，进程进入"僵死"状态
- 本地直调正常，但 MCP 调用失败

**根本原因**:
1. **同步阻塞主线程**
   - embedding 模型下载/初始化在主线程同步执行
   - 阻塞了 MCP stdio 的消息处理循环
   - 导致后续所有请求都无法响应

2. **缺少超时保护**
   - 工具执行没有超时限制
   - 一个慢调用可以永久阻塞整个进程

3. **没有异步隔离**
   - 所有工具在同一个事件循环中执行
   - 没有请求队列和并发控制

**修复方案**:

```python
# 1. 服务器启动时预加载模型（避免冷启动）
async def startup():
    logger.info("Preloading embedding model...")
    # 在后台线程预加载，不阻塞主线程
    await asyncio.to_thread(embedding_generator.load_model)
    logger.info("Model ready")

# 2. 每个工具添加超时保护
async def execute_tool_with_timeout(name: str, params: dict):
    try:
        return await asyncio.wait_for(
            execute_tool(name, params),
            timeout=30.0  # 30秒超时
        )
    except asyncio.TimeoutError:
        return {
            "success": False,
            "error": f"Tool {name} timed out after 30s"
        }

# 3. 使用线程池隔离重操作
async def get_relevant_operations(...):
    # 在独立线程池执行，不阻塞事件循环
    return await asyncio.to_thread(
        _sync_get_relevant_operations, ...
    )
```

---

### P0-2: 上下文模块冷启动阻塞 ⚠️

**现象**:
- 首次调用下载 79.3MB 模型
- 阻塞主线程，导致 MCP 进程无响应

**修复方案**:

```python
# amp/mcp/run_mcp_server.py

async def main():
    logger.info("Starting AMP MCP Server")
    
    # 初始化数据库
    database = Database(settings.database.url)
    
    # 预加载模型（在后台线程，不阻塞）
    logger.info("Preloading embedding model (background)...")
    model_task = asyncio.create_task(
        asyncio.to_thread(preload_embedding_model)
    )
    
    # 创建 MCP 服务器（不等待模型加载完成）
    server = create_mcp_server(database)
    
    # 启动 stdio 服务器
    async with stdio_server() as (read_stream, write_stream):
        # 在后台等待模型加载
        asyncio.create_task(wait_for_model(model_task))
        
        # 立即开始处理 MCP 请求
        await server.run(read_stream, write_stream, ...)

async def wait_for_model(task):
    await task
    logger.info("Embedding model ready")
```

---

### P0-3: 简化上下文系统 - 使用"黑板"模式 ✅

**您的建议**: 不需要复杂的向量搜索和上下文压缩，只需要一个共享的"黑板"文档，记录当前状态。

**完全同意！这是更实用的方案。**

**新设计**:

```python
# amp/core/blackboard.py

class Blackboard:
    """共享状态黑板 - 简单、快速、可靠"""
    
    def __init__(self, database: Database):
        self.db = database
        self._cache = {}
    
    def get_state(self) -> dict:
        """获取当前完整状态"""
        return {
            "tunnels": self._get_tunnels(),
            "shells": self._get_shells(),
            "network": self._get_network(),
            "recent_operations": self._get_recent_operations(limit=20)
        }
    
    def _get_tunnels(self) -> list:
        """获取所有隧道状态"""
        tunnels = self.db.query(Tunnel).all()
        return [
            {
                "id": t.id,
                "name": t.name,
                "type": t.tunnel_type,
                "status": t.status,
                "local_port": t.local_port,
                "remote": f"{t.remote_host}:{t.remote_port}",
                "parent_id": t.parent_tunnel_id
            }
            for t in tunnels
        ]
    
    def _get_shells(self) -> list:
        """获取所有 Shell 状态"""
        shells = self.db.query(Shell).all()
        return [
            {
                "id": s.id,
                "name": s.name,
                "type": s.shell_type,
                "status": s.status,
                "target": s.target_host,
                "os": s.os_type
            }
            for s in shells
        ]
    
    def _get_network(self) -> dict:
        """获取网络拓扑"""
        segments = self.db.query(NetworkSegment).all()
        return {
            "segments": [s.name for s in segments],
            "connections": self._build_connections()
        }
    
    def _get_recent_operations(self, limit: int = 20) -> list:
        """获取最近操作（简单查询，不用向量搜索）"""
        ops = self.db.query(Operation)\
            .order_by(Operation.created_at.desc())\
            .limit(limit)\
            .all()
        return [
            {
                "command": op.command,
                "output": op.output[:200],  # 只取前200字符
                "timestamp": op.created_at.isoformat()
            }
            for op in ops
        ]
    
    def update_tunnel(self, tunnel_id: str, **kwargs):
        """更新隧道状态"""
        # 更新数据库
        # 清除缓存
        self._cache.clear()
    
    def update_shell(self, shell_id: str, **kwargs):
        """更新 Shell 状态"""
        # 更新数据库
        # 清除缓存
        self._cache.clear()
```

**新的工具实现**:

```python
# amp/mcp/tools/blackboard_tools.py

async def get_current_state() -> dict:
    """获取当前状态 - 替代复杂的 context 工具"""
    blackboard = Blackboard(database)
    return {
        "success": True,
        "data": blackboard.get_state()
    }

async def build_prompt(query: str) -> dict:
    """构建提示 - 简化版，只返回当前状态"""
    blackboard = Blackboard(database)
    state = blackboard.get_state()
    
    prompt = f"""
Current AMP State:

Tunnels ({len(state['tunnels'])}):
{format_tunnels(state['tunnels'])}

Shells ({len(state['shells'])}):
{format_shells(state['shells'])}

Network:
{format_network(state['network'])}

Recent Operations:
{format_operations(state['recent_operations'])}

Query: {query}
"""
    
    return {
        "success": True,
        "data": {"prompt": prompt}
    }
```

**优势**:
- ✅ 没有冷启动（不需要下载模型）
- ✅ 查询速度快（直接数据库查询）
- ✅ 逻辑简单（容易调试）
- ✅ 不会阻塞（没有重操作）

---

### P1-1: 自动记录操作到数据库 📝

**现象**: 数据库为空，没有积累状态

**修复方案**:

```python
# 每个工具执行后自动记录

async def create_tunnel(...):
    # 创建隧道
    tunnel = tunnel_manager.create_tunnel(...)
    
    # 自动写入数据库
    await database.add(tunnel)
    await database.commit()
    
    # 更新黑板
    blackboard.update_tunnel(tunnel.id, status="active")
    
    return {"success": True, "tunnel_id": tunnel.id}

async def execute_command(shell_id: str, command: str):
    # 执行命令
    result = shell_manager.execute(shell_id, command)
    
    # 自动记录操作
    operation = Operation(
        shell_id=shell_id,
        command=command,
        output=result.output,
        exit_code=result.exit_code
    )
    await database.add(operation)
    await database.commit()
    
    return {"success": True, "output": result.output}
```

---

### P1-2: 添加健康检查和就绪状态 🏥

**修复方案**:

```python
# amp/mcp/mcp_server.py

@app.list_resources()
async def list_resources():
    """MCP 资源列表 - 包含健康状态"""
    return [
        Resource(
            uri="amp://health",
            name="AMP Health Status",
            mimeType="application/json"
        )
    ]

@app.read_resource()
async def read_resource(uri: str):
    """读取资源 - 返回健康状态"""
    if uri == "amp://health":
        return {
            "database": database.is_connected(),
            "tunnels": len(blackboard.get_tunnels()),
            "shells": len(blackboard.get_shells()),
            "ready": True  # 简化版总是 ready
        }
```

---

## 🔧 修复优先级

### 立即修复（1-2 天）

1. **移除向量搜索和上下文压缩**
   - 删除 ChromaDB 依赖
   - 删除 embedding 模型
   - 删除 sentence-transformers

2. **实现黑板模式**
   - 创建 `Blackboard` 类
   - 简化 `build_prompt` 和 `get_relevant_operations`
   - 直接查询数据库

3. **添加超时保护**
   - 每个工具 30s 超时
   - 使用 `asyncio.wait_for`

4. **自动记录操作**
   - 每个工具执行后写入数据库
   - 更新黑板状态

### 短期优化（3-5 天）

5. **添加健康检查**
   - MCP 资源端点
   - 状态查询工具

6. **优化 MCP 进程稳定性**
   - 请求队列
   - 并发控制
   - 错误恢复

---

## 📊 修复后的预期效果

| 指标 | 当前 | 目标 |
|------|------|------|
| MCP 调用成功率 | ~20% | >95% |
| 平均响应时间 | 120s+ | <2s |
| 冷启动时间 | 未知 | <1s |
| 操作记录率 | 0% | 100% |
| 依赖大小 | ~200MB | ~50MB |

---

## 🎯 核心改进

### 删除的复杂功能

- ❌ ChromaDB 向量存储
- ❌ sentence-transformers 模型
- ❌ 上下文压缩算法
- ❌ 相似度搜索
- ❌ 动态提示生成

### 新增的简单功能

- ✅ 黑板状态管理
- ✅ 直接数据库查询
- ✅ 简单文本格式化
- ✅ 自动状态记录
- ✅ 超时保护

---

## 🚀 实施步骤

```bash
# 1. 创建修复分支
git checkout -b fix/simplify-and-stabilize

# 2. 删除复杂依赖
pip uninstall chromadb sentence-transformers

# 3. 实现黑板模式
# 创建 amp/core/blackboard.py

# 4. 简化工具
# 修改 amp/mcp/tools/*.py

# 5. 添加超时保护
# 修改 amp/mcp/mcp_server.py

# 6. 测试
python amp/mcp/test_mcp_server.py

# 7. 提交
git commit -m "fix: simplify context system and stabilize MCP process"
```

---

## ✅ 成功标准

修复完成后：

1. ✅ MCP 调用不再超时
2. ✅ 没有冷启动阻塞
3. ✅ 操作自动记录到数据库
4. ✅ 黑板状态实时更新
5. ✅ 依赖更少，更稳定
6. ✅ 与 Kali MCP 协同良好

---

**核心思路**: 简化 > 稳定 > 实用

不需要复杂的 AI 能力，只需要可靠的状态管理和工具执行。
