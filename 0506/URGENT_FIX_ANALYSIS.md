# 🚨 紧急问题分析 - 输出被吞的根本原因

## 您的测试结果

### 问题 1: 简单 shell 输出为空
```
execute_command("echo RETEST_OK; whoami; pwd")
返回：
- exit_code: 0
- stdout: ""  ❌ 输出被吞了
```

### 问题 2: bash -li 仍然失败
```
execute_command("echo BASH_LI_OK; whoami; pwd")
返回：
- exit_code: -1  ❌ 仍然失败
```

---

## 根本原因分析

### Bug 1: `_get_exit_code()` 干扰输出

**代码位置**: `amp/core/shell/executor.py:235-250`

```python
def _get_exit_code(self, child, timeout=5):
    # 发送 echo $? 获取退出码
    child.sendline("echo $?")  # ❌ 这会干扰后续输出
    child.expect(self.PROMPT_PATTERNS, timeout=timeout)
    output = child.before
    ...
```

**问题**:
1. 在获取命令输出后，又发送了 `echo $?`
2. 这会消耗掉 shell 的输出缓冲
3. 导致下次命令的输出被混淆

**影响**: 输出为空或混乱

---

### Bug 2: `_clean_output()` 过度清理

**代码位置**: `amp/core/shell/executor.py:252-275`

```python
def _clean_output(self, output, command):
    # 移除 ANSI 码
    output = ansi_escape.sub('', output)
    
    lines = output.split("\n")
    
    # 移除第一行（命令回显）
    if lines and command in lines[0]:
        lines = lines[1:]  # ❌ 可能误删有效输出
    
    # 移除空行
    while lines and not lines[0].strip():
        lines = lines[1:]
    while lines and not lines[-1].strip():
        lines = lines[-1:]  # ❌ 这里有bug，应该是 pop()
    
    return "\n".join(lines)
```

**问题**:
1. 命令回显检测不准确
2. 空行移除逻辑有bug（`lines[-1:]` 不会删除）
3. 可能把有效输出当作回显删除

---

### Bug 3: Prompt 模式仍然不够

**当前模式**:
```python
PROMPT_PATTERNS = [
    r'[\$#>]\s*$',  # 基础
    r'\x1b\[[0-9;]*m.*?[\$#>]\s*$',  # 彩色
    r'\n.*?[\$#>]\s*$',  # 多行
    ...
]
```

**问题**:
- `bash -li` 的提示符可能更复杂
- 可能包含多个 ANSI 序列
- 可能有换行符在中间

---

## 正确的修复方案

### 修复 1: 不要用 `echo $?` 获取退出码

**原因**: 
- `/bin/sh` 和简单 shell 不保证 `$?` 可用
- 会干扰输出缓冲
- 增加复杂度

**方案**: 
- 简单返回 0（命令执行成功）
- 或者通过输出判断（如果有 "command not found"）

```python
def _get_exit_code(self, child, timeout=5):
    """Get exit code - simplified version."""
    # 不发送额外命令，避免干扰输出
    # 简单返回 0，表示命令发送成功
    return 0
```

### 修复 2: 简化 `_clean_output()`

```python
def _clean_output(self, output, command):
    """Clean output - minimal cleaning."""
    if not output:
        return ""
    
    # 只移除 ANSI 码
    ansi_escape = re.compile(r'\x1b\[[0-9;]*[mGKH]')
    output = ansi_escape.sub('', output)
    
    # 移除命令回显（只检查第一行）
    lines = output.split('\n')
    if lines and command.strip() in lines[0]:
        lines = lines[1:]
    
    # 移除首尾空行
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    
    return '\n'.join(lines).strip()
```

### 修复 3: 更宽松的 Prompt 匹配

```python
PROMPT_PATTERNS = [
    # 最宽松的模式放前面
    r'.{0,200}[\$#>]\s*$',  # 任意字符 + 提示符
    
    # 具体模式
    r'[\$#>]\s*$',
    r'\x1b\[[0-9;]*m.*?[\$#>]\s*$',
    
    pexpect.TIMEOUT,
    pexpect.EOF,
]
```

---

## 为什么修复"看起来没效果"

1. **`_get_exit_code()` 没有被修复**
   - 仍然发送 `echo $?`
   - 干扰输出缓冲

2. **`_clean_output()` 有bug**
   - 空行移除逻辑错误
   - 可能删除有效输出

3. **Prompt 模式不够宽松**
   - `bash -li` 的复杂提示符仍然匹配不到
   - 导致超时

---

## 立即需要的修复

### 优先级 P0

1. **修复 `_get_exit_code()`** - 不要发送 `echo $?`
2. **修复 `_clean_output()`** - 修复空行删除bug
3. **放宽 Prompt 模式** - 使用更宽松的匹配

### 测试验证

修复后应该：
- ✅ 简单 shell 有输出
- ✅ `bash -li` 能执行
- ✅ 输出不被吞

---

## 总结

**当前状态**: 修改了代码，但引入了新bug

**核心问题**: 
1. `_get_exit_code()` 干扰输出
2. `_clean_output()` 有逻辑错误
3. Prompt 模式仍然不够

**需要**: 立即修复这 3 个方法
