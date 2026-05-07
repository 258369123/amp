# 🔧 AMP 核心能力修复计划（基于实战测试）

## 测试结论总结

### ✅ 可用的核心能力
- **台账管理**: Shell/Tunnel 记录创建、查询、删除
- **简单 Shell**: `/bin/sh -i` 类型的简单 Shell 完整闭环可用
- **Tunnel 台账**: 创建、列出、状态查询、停止、删除

### ❌ 需要修复的核心问题
1. **Prompt 识别失败** - 彩色/多行 bash 提示符无法识别
2. **假成功问题** - bind shell 连接失败仍返回 success
3. **Reverse Shell 设计缺陷** - accept() 后没有接管 socket
4. **列表不完整** - list_shells 只显示 active，看不到完整历史

---

## 🚨 P0 修复（核心可用性）

### 问题 1: Prompt 识别失败 ⚠️

**现象**:
```bash
# 简单 shell (/bin/sh -i) - ✅ 成功
execute_command("echo SIMPLE_OK; whoami; pwd")

# 真实 bash (bash -li) - ❌ 失败
execute_command("whoami")  # 命令执行了，但返回 exit code -1
```

**根本原因**:
- 当前 prompt 匹配模式太简单
- 无法识别彩色、多行、带 ANSI 的 bash 提示符
- 导致无法判断命令结束

**影响**: 🔴 **严重** - 真实内网环境的 shell 大多不可用

**修复方案**:

```python
# amp/core/shell/backends/pexpect_backend.py

class PexpectBackend:
    # 当前的简单模式
    PROMPT_PATTERNS = [
        r'[$#>]\s*$',  # 太简单
    ]
    
    # 修复后的增强模式
    PROMPT_PATTERNS = [
        # 基础提示符
        r'[$#>]\s*$',
        
        # 带颜色的 bash 提示符
        r'\x1b\[[0-9;]*m.*?[$#>]\s*$',
        
        # 多行提示符
        r'\n.*?[$#>]\s*$',
        
        # 常见格式
        r'\[.*?\][$#>]\s*$',  # [user@host]$
        r'.*?@.*?:.*?[$#>]\s*$',  # user@host:path$
        
        # PowerShell
        r'PS\s+.*?>\s*$',
        
        # 通用兜底（任何以 $ # > 结尾的行）
        r'.+[$#>]\s*$',
    ]
    
    def execute_command(self, command: str, timeout: int = 30):
        """Execute command with enhanced prompt detection."""
        try:
            # 发送命令
            self.process.sendline(command)
            
            # 等待任意一个 prompt 模式
            index = self.process.expect(
                self.PROMPT_PATTERNS + [pexpect.TIMEOUT],
                timeout=timeout
            )
            
            if index == len(self.PROMPT_PATTERNS):
                # Timeout - 尝试发送回车再等一次
                self.process.sendline('')
                index = self.process.expect(
                    self.PROMPT_PATTERNS + [pexpect.TIMEOUT],
                    timeout=5
                )
                if index == len(self.PROMPT_PATTERNS):
                    raise ShellExecutionFailed("Command timeout")
            
            # 获取输出
            output = self.process.before.decode('utf-8', errors='ignore')
            
            # 清理输出（移除命令回显和 ANSI 码）
            output = self._clean_output(output, command)
            
            return {
                "output": output,
                "exit_code": 0
            }
        except Exception as e:
            return {
                "output": str(e),
                "exit_code": -1
            }
    
    def _clean_output(self, output: str, command: str) -> str:
        """Clean command output."""
        # 移除命令回显
        if command in output:
            output = output.replace(command, '', 1)
        
        # 移除 ANSI 转义码
        import re
        ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
        output = ansi_escape.sub('', output)
        
        # 移除多余空行
        output = '\n'.join(line for line in output.split('\n') if line.strip())
        
        return output.strip()
```

---

### 问题 2: Bind Shell 假成功 ⚠️

**现象**:
```python
# 端口未监听
create_shell(bind, "127.0.0.1:65000")
# 返回: success=True, status=active  ❌ 错误

# 直到执行命令才发现
execute_command(...)
# 返回: shell_died  ❌ 太晚了
```

**根本原因**:
- 创建时没有验证连接
- 乐观地假设成功

**影响**: 🟡 **中等** - 污染 Agent 的可用 shell 列表

**修复方案**:

```python
# amp/core/shell/manager.py

def create_shell(self, name: str, shell_type: ShellType, ...):
    """Create shell with connection verification."""
    
    if shell_type == ShellType.BIND:
        # 创建前先验证连接
        if not self._verify_bind_connection(target_host, target_port):
            raise ShellCreationFailed(
                f"Cannot connect to {target_host}:{target_port}"
            )
    
    # 创建 shell...
    
def _verify_bind_connection(self, host: str, port: int, timeout: int = 5) -> bool:
    """Verify bind shell connection before creating."""
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.close()
        return True
    except Exception as e:
        logger.warning(f"Bind connection verification failed: {e}")
        return False
```

---

### 问题 3: Reverse Shell 设计缺陷 🔴

**现象**:
```python
# core/shell/manager.py:188-203
conn, addr = listener.accept()
# 但接下来没有用 conn，而是：
self.executor.spawn_shell(shell_id, "bash")  # ❌ 本地 bash
```

**根本原因**:
- accept() 后没有接管 socket
- 启动的是本地 bash，不是网络连接

**影响**: 🔴 **严重** - Reverse shell 完全不可用

**修复方案**:

```python
# amp/core/shell/manager.py

def _handle_reverse_connection(self, shell_id: str, listener: socket.socket):
    """Handle reverse shell connection."""
    try:
        # 等待连接
        conn, addr = listener.accept()
        logger.info(f"Reverse connection from {addr}")
        
        # 关键修复：将 socket 传给 executor
        self.executor.attach_socket(shell_id, conn)
        
        # 更新状态
        shell = self.repository.get(shell_id)
        shell.status = ShellStatus.ACTIVE
        shell.target_host = addr[0]
        self.repository.update(shell)
        
    except Exception as e:
        logger.error(f"Reverse connection failed: {e}")
        shell = self.repository.get(shell_id)
        shell.status = ShellStatus.DEAD
        self.repository.update(shell)

# amp/core/shell/backends/pexpect_backend.py

class PexpectBackend:
    def attach_socket(self, shell_id: str, sock: socket.socket):
        """Attach a socket as shell I/O."""
        # 将 socket 包装为 file-like object
        sock_file = sock.makefile('rwb', buffering=0)
        
        # 使用 pexpect.fdpexpect 处理 socket
        import pexpect.fdpexpect
        self.process = pexpect.fdpexpect.fdspawn(
            sock.fileno(),
            encoding='utf-8',
            codec_errors='ignore'
        )
        
        # 等待初始 prompt
        self.process.expect(self.PROMPT_PATTERNS, timeout=10)
```

---

### 问题 4: list_shells 不完整 ⚠️

**现象**:
```python
# 数据库有 4 条 dead shell
# 但 list_shells() 返回空

# 原因：mcp/tools/shell_tools.py:388-395
# 一直在调 list_active_shells()
```

**根本原因**:
- list_shells 只查询 active
- 没有提供完整视图

**影响**: 🟡 **中等** - Agent 看不到完整资源状态

**修复方案**:

```python
# amp/mcp/tools/shell_tools.py

async def list_shells(status: str | None = None) -> dict:
    """List shells with optional status filter.
    
    Args:
        status: Optional filter - 'active', 'dead', 'zombie', or None for all
    """
    try:
        if status is None:
            # 返回所有 shell
            shells = shell_manager.list_all_shells()
        elif status == 'active':
            shells = shell_manager.list_active_shells()
        elif status == 'dead':
            shells = shell_manager.list_dead_shells()
        else:
            shells = shell_manager.list_shells_by_status(status)
        
        return {
            "success": True,
            "data": {
                "shells": shells,
                "count": len(shells),
                "filter": status or "all"
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# amp/core/shell/manager.py

class ShellManager:
    def list_all_shells(self) -> list:
        """List all shells regardless of status."""
        return self.repository.list_all()
    
    def list_dead_shells(self) -> list:
        """List dead shells."""
        return self.repository.list_by_status(ShellStatus.DEAD)
    
    def list_shells_by_status(self, status: str) -> list:
        """List shells by status."""
        status_enum = ShellStatus[status.upper()]
        return self.repository.list_by_status(status_enum)
```

---

## 🔧 修复优先级

### Phase 1: 立即修复（1-2 天）

1. **Prompt 识别** - P0
   - 增强 prompt 模式匹配
   - 支持彩色/多行提示符
   - 添加输出清理

2. **Bind 验证** - P0
   - 创建前验证连接
   - 避免假成功

### Phase 2: 核心修复（3-5 天）

3. **Reverse Shell** - P0
   - 修复 socket 接管逻辑
   - 实现 attach_socket
   - 测试真实回连

4. **完整列表** - P1
   - list_all_shells
   - 支持状态过滤
   - 完整资源视图

---

## 📊 修复后的预期效果

| 功能 | 修复前 | 修复后 |
|------|--------|--------|
| **简单 Shell** | ✅ 可用 | ✅ 可用 |
| **真实 Bash** | ❌ 不可用 | ✅ 可用 |
| **Bind 验证** | ❌ 假成功 | ✅ 真实验证 |
| **Reverse Shell** | ❌ 不可用 | ✅ 可用 |
| **完整列表** | ❌ 只有 active | ✅ 全部状态 |

---

## 🎯 核心目标

**修复后，AMP 应该能够**:
1. ✅ 可靠管理真实 bash shell（彩色提示符）
2. ✅ 正确验证 bind shell 连接
3. ✅ 真正接管 reverse shell 连接
4. ✅ 提供完整的 shell/tunnel 资源视图

**让 AMP 真正成为**:
- 可靠的 Shell 执行器（不只是台账）
- 真实的 Reverse Shell 接管器
- 完整的资源状态文档

---

## 🚀 实施计划

```bash
# 1. 创建修复分支
git checkout -b fix/core-shell-issues

# 2. 修复 Prompt 识别
# 编辑 amp/core/shell/backends/pexpect_backend.py

# 3. 修复 Bind 验证
# 编辑 amp/core/shell/manager.py

# 4. 修复 Reverse Shell
# 编辑 amp/core/shell/manager.py
# 编辑 amp/core/shell/backends/pexpect_backend.py

# 5. 修复列表功能
# 编辑 amp/mcp/tools/shell_tools.py
# 编辑 amp/core/shell/manager.py

# 6. 测试
python test_shell_fixes.py

# 7. 提交
git commit -m "fix: core shell issues - prompt detection, bind verification, reverse shell, complete list"
```

---

**感谢您的详细测试！这些问题对 AMP 的实用性至关重要。** 🙏
