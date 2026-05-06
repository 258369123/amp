# AMP 可扩展性设计

## 当前 MVP 范围回顾

**明确排除在 MVP 外**：
- ❌ 插件系统（硬编码工具集）
- ❌ 多 agent 协作
- ❌ 自定义工具扩展

**但是**，我们可以在架构设计中**预留扩展点**，确保后期添加这些功能时不需要大规模重构。

---

## 可扩展性架构设计

### 1. 工具注册机制（预留接口）

**当前 MVP 实现**：硬编码 7 个核心工具
```python
# amp/mcp/tools.py (MVP)
CORE_TOOLS = [
    create_tunnel,
    execute_command,
    get_context,
    scan_network,
    create_shell,
    upload_file,
    visualize_topology,
]
```

**扩展点设计**（后期启用）：
```python
# amp/mcp/registry.py (预留接口)
class ToolRegistry:
    """工具注册表 - MVP 阶段仅用于核心工具，后期支持插件"""
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._register_core_tools()  # MVP: 硬编码核心工具
    
    def register(self, tool: Tool, source: str = "core"):
        """注册工具（MVP 仅内部使用，后期开放给插件）"""
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name} (source: {source})")
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """获取工具"""
        return self._tools.get(name)
    
    def list_tools(self, source: Optional[str] = None) -> List[Tool]:
        """列出所有工具（可按来源过滤）"""
        if source:
            return [t for t in self._tools.values() if t.source == source]
        return list(self._tools.values())
    
    # 后期扩展：插件加载
    def load_plugin(self, plugin_path: str):
        """从插件目录加载工具（Post-MVP）"""
        # 动态导入插件模块
        # 验证插件签名
        # 注册插件提供的工具
        pass
```

**工具接口标准化**：
```python
# amp/mcp/tool_interface.py
from abc import ABC, abstractmethod
from pydantic import BaseModel

class ToolParameter(BaseModel):
    """工具参数定义"""
    name: str
    type: str  # string, integer, boolean, object
    description: str
    required: bool = True
    default: Any = None

class ToolResult(BaseModel):
    """工具执行结果"""
    success: bool
    data: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}

class Tool(ABC):
    """工具基类 - 所有工具必须继承此类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称（唯一标识）"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述"""
        pass
    
    @property
    @abstractmethod
    def parameters(self) -> List[ToolParameter]:
        """工具参数定义"""
        pass
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """执行工具"""
        pass
    
    # 可选：工具生命周期钩子
    async def on_load(self):
        """工具加载时调用"""
        pass
    
    async def on_unload(self):
        """工具卸载时调用"""
        pass
```

**示例：核心工具实现**：
```python
# amp/mcp/tools/create_tunnel.py
class CreateTunnelTool(Tool):
    def __init__(self, tunnel_manager: TunnelManager):
        self.tunnel_manager = tunnel_manager
    
    @property
    def name(self) -> str:
        return "create_tunnel"
    
    @property
    def description(self) -> str:
        return "Create a network tunnel to target host"
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(name="target", type="string", description="Target network or host"),
            ToolParameter(name="method", type="string", description="Tunnel type (chisel/ligolo/ssh)"),
            ToolParameter(name="pivot_host", type="string", required=False),
        ]
    
    async def execute(self, **kwargs) -> ToolResult:
        try:
            tunnel = await self.tunnel_manager.create_tunnel(**kwargs)
            return ToolResult(
                success=True,
                data={"tunnel_id": tunnel.id, "status": tunnel.status},
            )
        except TunnelException as e:
            return ToolResult(success=False, error=str(e))
```

---

### 2. 插件系统架构（Post-MVP）

**插件目录结构**：
```
~/.amp/plugins/
├── bloodhound-analyzer/
│   ├── plugin.yaml          # 插件元数据
│   ├── __init__.py
│   ├── tools/
│   │   ├── analyze_ad.py    # 自定义工具
│   │   └── find_path.py
│   └── requirements.txt     # 插件依赖
│
├── custom-payloads/
│   ├── plugin.yaml
│   ├── tools/
│   │   └── generate_payload.py
│   └── templates/
│       └── reverse_shell.ps1
│
└── nmap-integration/
    ├── plugin.yaml
    └── tools/
        └── advanced_scan.py
```

**插件元数据**（plugin.yaml）：
```yaml
name: bloodhound-analyzer
version: 1.0.0
author: security-team
description: Integrate BloodHound for AD attack path analysis
homepage: https://github.com/example/amp-bloodhound-plugin

# 插件提供的工具
tools:
  - name: analyze_ad_domain
    module: tools.analyze_ad
    class: AnalyzeADTool
  
  - name: find_attack_path
    module: tools.find_path
    class: FindPathTool

# 依赖
dependencies:
  - bloodhound>=4.0.0
  - neo4j>=5.0.0

# 权限要求
permissions:
  - network_access
  - file_read
  - database_access

# 兼容性
requires_amp_version: ">=0.2.0"
```

**插件加载器**（Post-MVP）：
```python
# amp/plugins/loader.py
class PluginLoader:
    def __init__(self, plugin_dir: Path):
        self.plugin_dir = plugin_dir
        self.loaded_plugins: Dict[str, Plugin] = {}
    
    async def load_plugin(self, plugin_name: str) -> Plugin:
        """加载插件"""
        plugin_path = self.plugin_dir / plugin_name
        
        # 1. 读取 plugin.yaml
        metadata = self._load_metadata(plugin_path / "plugin.yaml")
        
        # 2. 验证兼容性
        self._validate_compatibility(metadata)
        
        # 3. 验证签名（可选，用于安全）
        if self.config.verify_signatures:
            self._verify_signature(plugin_path)
        
        # 4. 安装依赖（隔离环境）
        await self._install_dependencies(plugin_path, metadata.dependencies)
        
        # 5. 动态导入插件模块
        plugin_module = importlib.import_module(f"plugins.{plugin_name}")
        
        # 6. 实例化工具
        tools = []
        for tool_def in metadata.tools:
            tool_class = getattr(plugin_module, tool_def.class_name)
            tool = tool_class()
            tools.append(tool)
        
        # 7. 注册到工具注册表
        plugin = Plugin(name=plugin_name, metadata=metadata, tools=tools)
        self.loaded_plugins[plugin_name] = plugin
        
        for tool in tools:
            tool_registry.register(tool, source=f"plugin:{plugin_name}")
        
        logger.info(f"Loaded plugin: {plugin_name} ({len(tools)} tools)")
        return plugin
    
    def _verify_signature(self, plugin_path: Path):
        """验证插件签名（防止恶意插件）"""
        # 使用 GPG 或类似机制验证插件完整性
        pass
```

---

### 3. 扩展点清单

**MVP 阶段预留的扩展点**：

| 扩展点 | 当前实现 | 后期扩展 |
|--------|---------|---------|
| **工具注册** | 硬编码 7 个核心工具 | 插件动态注册工具 |
| **Payload 生成** | 内置 bash/PowerShell | 插件提供自定义 payload 模板 |
| **网络扫描** | 内置 nmap 封装 | 插件集成 masscan, nuclei 等 |
| **后渗透工具** | 无 | 插件集成 BloodHound, Mimikatz, PEASS |
| **报告生成** | 无 | 插件生成 PDF/HTML 报告 |
| **通知系统** | 无 | 插件发送 Slack/Email 通知 |
| **数据导出** | SQLite 原始数据 | 插件导出到 Elasticsearch, Splunk |

**代码中的扩展点标记**：
```python
# amp/core/shell/manager.py
class ShellManager:
    def __init__(self):
        self.backends = {
            "tmux": TmuxBackend(),
            "screen": ScreenBackend(),  # 预留
        }
        # 扩展点：后期可通过插件注册新的 backend
        # self.register_backend("custom", CustomBackend())
    
    def register_backend(self, name: str, backend: ShellBackend):
        """注册自定义 shell backend（Post-MVP）"""
        self.backends[name] = backend
```

---

### 4. 配置系统扩展

**MVP 配置**（amp.config.yaml）：
```yaml
amp:
  core:
    # ... 核心配置
  
  # 预留：插件配置
  plugins:
    enabled: false  # MVP 阶段禁用
    directory: ~/.amp/plugins
    auto_load: []
    verify_signatures: true
```

**Post-MVP 配置**：
```yaml
amp:
  plugins:
    enabled: true
    directory: ~/.amp/plugins
    auto_load:
      - bloodhound-analyzer
      - custom-payloads
    verify_signatures: true
    
    # 插件特定配置
    bloodhound-analyzer:
      neo4j_uri: bolt://localhost:7687
      neo4j_user: neo4j
      neo4j_password: ${NEO4J_PASSWORD}
```

---

### 5. API 稳定性承诺

**为了确保插件兼容性，我们承诺**：

1. **Tool 接口稳定**：`Tool` 基类在 v1.x 版本中保持向后兼容
2. **语义化版本**：遵循 SemVer（主版本.次版本.补丁版本）
3. **弃用策略**：废弃的 API 至少保留 2 个次版本
4. **插件 API 文档**：提供详细的插件开发指南

**版本兼容性矩阵**：
```
AMP v0.1.x (MVP)    → 无插件支持
AMP v0.2.x          → 插件 API v1（实验性）
AMP v1.0.x          → 插件 API v1（稳定）
AMP v2.0.x          → 插件 API v2（可能破坏性变更）
```

---

### 6. 示例：自定义工具插件

**场景**：用户想添加一个自动化 BloodHound 分析工具

**插件代码**（~/.amp/plugins/bloodhound-analyzer/tools/analyze_ad.py）：
```python
from amp.mcp.tool_interface import Tool, ToolParameter, ToolResult
from neo4j import GraphDatabase

class AnalyzeADTool(Tool):
    @property
    def name(self) -> str:
        return "analyze_ad_domain"
    
    @property
    def description(self) -> str:
        return "Analyze AD domain using BloodHound data"
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="domain",
                type="string",
                description="Target AD domain (e.g., corp.local)",
            ),
            ToolParameter(
                name="analysis_type",
                type="string",
                description="Analysis type: shortest_path, kerberoastable, etc.",
            ),
        ]
    
    async def execute(self, domain: str, analysis_type: str) -> ToolResult:
        # 连接 Neo4j
        driver = GraphDatabase.driver(
            self.config.neo4j_uri,
            auth=(self.config.neo4j_user, self.config.neo4j_password),
        )
        
        # 执行 Cypher 查询
        with driver.session() as session:
            if analysis_type == "shortest_path":
                result = session.run(
                    """
                    MATCH (u:User {domain: $domain}),
                          (c:Computer {domain: $domain, highvalue: true}),
                          p = shortestPath((u)-[*1..]->(c))
                    RETURN u.name, c.name, length(p) as path_length
                    ORDER BY path_length
                    LIMIT 10
                    """,
                    domain=domain,
                )
                paths = [dict(record) for record in result]
                return ToolResult(success=True, data={"paths": paths})
        
        driver.close()
```

**使用方式**：
```bash
# 安装插件
amp plugin install bloodhound-analyzer

# Claude Code 中使用
> 分析 corp.local 域，找到到域控的最短攻击路径

AI: [使用工具: analyze_ad_domain(domain="corp.local", analysis_type="shortest_path")]
    发现 3 条可能的攻击路径：
    1. user1@corp.local → server1 → dc01 (3 hops)
    2. user2@corp.local → workstation5 → server2 → dc01 (4 hops)
    ...
```

---

## 实施建议

### MVP 阶段（当前）
1. ✅ 实现 `Tool` 基类和接口
2. ✅ 实现 `ToolRegistry`（仅用于核心工具）
3. ✅ 硬编码 7 个核心工具
4. ✅ 在代码中标记扩展点（注释 `# 扩展点：...`）

### Post-MVP v0.2（+4 周）
1. 实现 `PluginLoader`
2. 实现插件签名验证
3. 编写插件开发文档
4. 提供 2-3 个官方插件示例

### v1.0（+8 周）
1. 插件 API 稳定化
2. 插件市场/仓库
3. 社区插件审核机制

---

## 总结

**MVP 阶段**：
- ❌ 不实现完整的插件系统（避免过度设计）
- ✅ 但预留清晰的扩展点（Tool 接口、ToolRegistry）
- ✅ 确保核心架构支持后期扩展

**扩展路径**：
```
MVP (v0.1)          → 硬编码 7 个工具
  ↓
v0.2 (+4 周)        → 插件系统（实验性）
  ↓
v1.0 (+8 周)        → 插件 API 稳定，社区生态
```

**关键原则**：
1. **YAGNI**（You Aren't Gonna Need It）：MVP 不实现未使用的功能
2. **Open/Closed**：对扩展开放，对修改封闭
3. **接口隔离**：清晰的 Tool 接口，易于实现

---

这样设计的好处：
- ✅ MVP 保持简单，快速交付
- ✅ 后期添加插件系统不需要大规模重构
- ✅ 用户可以在 v0.2+ 自定义工具
- ✅ 社区可以贡献插件（BloodHound, Metasploit 集成等）

你觉得这个扩展性设计如何？是否满足你的需求？
