# MiniCode Harness 测试与验收说明

本文档说明项目测试了什么、使用了哪些测试数据、如何执行，以及通过测试能够证明哪些笔试要求。

如需亲自操作真实 MiniCode，并让验收数据保存到 SQLite 后直观看结果，请使用
[`MANUAL_TESTING.md`](MANUAL_TESTING.md)。

## 1. 测试总览

完整自动化测试命令：

```powershell
python -m pytest -q
```

当前预期结果：

```text
50 passed
```

测试分为：

| 测试范围 | 文件 | 用例数 | 主要验证内容 |
|---|---|---:|---|
| Agent 运行时集成测试 | `tests/integration/test_runtime.py` | 5 | Agent Loop、工具回填、SQLite 持久化、跨轮恢复、最大步数、上下文压缩、终端事件 |
| 上下文压缩 | `tests/unit/test_compactor.py` | 2 | 原始历史保留、累计摘要、工具输出微压缩、Function Calling 配对 |
| Coding Tools 与权限 | `tests/unit/test_tools.py` | 6 | 六个工具、路径限制、写前读取、命令白名单、受控删除 |
| 权限策略与审批 | `tests/unit/test_policy.py`、`tests/unit/test_approval_ui.py` | 8 | 风险分级、敏感操作审批、用户拒绝语义 |
| 命令执行隔离 | `tests/unit/test_executors.py` | 2 | 环境变量白名单、输出限制、Docker 隔离参数 |
| Runtime 失败闭环 | `tests/integration/test_runtime_failures.py` | 5 | Run/Task/Trace 异常收尾、拒绝后禁止绕过 |
| CLI 与 Session | `tests/unit/test_cli.py` | 9 | 默认参数、Session 新建与切换、历史恢复、GBK 安全输出 |
| 终端界面 | `tests/unit/test_terminal_ui.py` | 7 | 欢迎界面、Session 标签重绘、新建与选择、Esc 返回、历史对话重放 |
| 配置加载 | `tests/unit/test_config.py` | 3 | `.env` 查找顺序、SQLite 路径固定 |
| 上下文组装 | `tests/unit/test_context.py` | 2 | Core Prompt、中文核心规则、项目规则、Task Ledger、摘要和消息 |
| 流式 LLM 客户端 | `tests/unit/test_streaming_llm.py` | 1 | 流式文本、原生 Function Calling 参数拼接 |

自动化测试使用临时目录、临时 SQLite 数据库和 `FakeLLMClient`，不会修改真实项目，也不会产生 API 费用。

## 2. Agent 运行时集成测试

执行：

```powershell
python -m pytest tests/integration/test_runtime.py -q
```

预期：`6 passed`。

### 2.1 Agent Loop、工具结果回填与持久化

测试：`test_agent_tool_loop_and_persistence`

测试数据：

```text
临时 Workspace 文件：note.txt
文件内容：hello
Session ID：demo
用户输入：inspect note
```

模拟 LLM 的第一轮响应：

```json
{
  "tool_call": {
    "id": "1",
    "name": "read_file",
    "arguments": {"path": "note.txt"}
  }
}
```

模拟 LLM 的第二轮响应：

```text
最终回答：Found hello
任务状态：paused
下一步：continue later
```

验证内容：

- Runtime 执行 `read_file`；
- 工具结果写入消息历史并回填给下一次 LLM 请求；
- assistant tool call 与匹配的 `tool_call_id` 被保留；
- Task Ledger 记录读取过的 `note.txt`；
- Trace 至少记录 LLM 响应和工具结果；
- 重新创建 Service 后，仍能从 SQLite 恢复 Session 和 `continue later`。

### 2.2 最大执行步数

测试：`test_max_steps_pauses_task`

测试数据：

```text
Session ID：demo
用户输入：loop
最大步数：2
模拟 LLM：持续请求 list_files(".")
```

验证内容：

- Runtime 达到最大步数后停止；
- 任务状态变为 `paused`；
- 返回原因包含 `maximum`。

### 2.3 完成任务后的跨轮记忆

测试：`test_follow_up_after_completed_task_recalls_previous_ledger`

测试数据：

```text
第一轮输入：fix the original bug
第二轮输入：what changed?
Session ID：demo
```

验证内容：

- 第一轮完成后 Task Ledger 被保存在 SQLite；
- 第二轮重新创建 Service 后，系统提示词仍包含第一轮目标 `fix the original bug`。

### 2.4 运行时终端事件

测试：`test_runtime_emits_thinking_tool_and_final_events`

测试数据：

```text
用户输入：inspect
第一步工具：list_files(".")
最终回答：done
```

预期事件顺序：

```text
thinking_started
tool_started
tool_finished
thinking_started
text_delta
run_finished
```

验证内容：终端能够显示思考状态、工具执行状态和流式最终回答。

### 2.5 Runtime 使用压缩后的上下文

测试：`test_runtime_uses_summary_and_recent_messages_after_compaction`

测试数据：

```text
字符预算：100
完整保留最近消息：2
旧目标与旧回答：各 80 个以上字符
当前输入：当前问题
```

验证内容：

- 旧目标进入 Session Summary；
- 旧目标不再作为完整历史消息重复发送；
- 当前问题仍作为最近完整消息发送；
- 内部压缩进度标记不会暴露给 LLM。

## 3. 上下文压缩测试

执行：

```powershell
python -m pytest tests/unit/test_compactor.py -q
```

预期：`2 passed`。

验证内容：

- 旧消息进入累计结构化摘要，但 SQLite 原始消息数量不变；
- 最近消息保持完整；
- 旧工具输出替换为短占位符；
- 最近工具结果保持完整；
- assistant tool call 与 tool result 的 ID 配对保持有效。

## 4. Coding Tools 与安全边界测试

执行：

```powershell
python -m pytest tests/unit/test_tools.py -q
```

预期：`6 passed`。

### 3.1 文件列出、读取与搜索

测试：`test_file_tools_work_inside_workspace`

测试文件：

```python
# a.py
answer = 42
```

验证内容：

- `list_files` 能列出 `a.py`；
- `read_file` 能读取 `answer = 42`；
- `search_code` 搜索 `answer` 时返回 `a.py:1`。

### 3.2 阻止路径穿越

测试：`test_guard_rejects_workspace_escape`

恶意输入：

```text
../outside.txt
```

验证内容：权限检查拒绝访问 Workspace 外的文件。

### 3.3 修改已有文件前必须读取

测试：`test_write_requires_prior_read`

初始文件：

```text
existing.py 内容：old
```

操作顺序：

1. 未读取时直接写入 `x = 1`，预期失败；
2. 使用 `read_file` 读取；
3. 再写入 `x = 1`，预期成功。

### 3.4 创建新文件

测试：`test_write_can_create_new_file`

测试输入：

```text
文件：new.py
内容：x = 1
```

验证内容：不存在的新文件可以直接创建。

### 3.5 命令白名单

测试：`test_run_command_allows_pytest_and_rejects_shell`

允许样例：

```text
python --version
```

拒绝样例：

```text
rm -rf .
```

验证内容：白名单命令可执行，危险 Shell 命令被拒绝。

## 5. CLI 与 Session 测试

执行：

```powershell
python -m pytest tests/unit/test_cli.py -q
```

预期：`10 passed`。

| 测试 | 测试数据或样例 | 验证内容 |
|---|---|---|
| `test_cli_help_lists_core_commands` | CLI 帮助文本 | 包含 `chat`、`trace`、`task`、`sessions` |
| `test_no_arguments_defaults_to_chat_in_current_workspace` | 无命令行参数、临时目录 | 默认进入聊天，Workspace 为当前目录，并生成新的空白 Session ID |
| `test_task_and_trace_default_to_current_workspace_session` | `task`、`trace` 未指定 Session | 自动使用新的空白 Session，因此初始结果为空 |
| `test_explicit_session_still_resumes_named_session` | `chat --workspace ... --session existing` | 显式指定 Session 时仍然恢复该 Session |
| `test_sessions_command_returns_selected_session` | 当前 Session=`current`，选择=`other` | `/sessions` 返回选中的 Session |
| `test_sessions_command_preserves_session_when_selector_is_cancelled` | 选择器返回 `None` | Esc/取消后不切换 Session |
| `test_chat_uses_selected_session_and_workspace_for_next_message` | 选择 `other` 后输入 `hello` | 下一条消息使用新 Session、新 Workspace，并加载历史 |
| `test_chat_creates_empty_session_in_current_workspace` | 在 `/sessions` 选择 New 后输入 `hello` | 立即创建 SQLite Session，并让下一条消息进入新会话 |
| `test_new_session_id_is_unique_and_keeps_workspace_prefix` | 为同一 Workspace 连续生成两个 ID | 新 Session ID 保留 Workspace 前缀且不会重复 |
| `test_safe_print_does_not_crash_on_gbk_terminal_with_unicode` | GBK 输出流与 Unicode 字符 | `trace` 等命令不会因无法编码字符而崩溃 |

## 6. 终端界面测试

执行：

```powershell
python -m pytest tests/unit/test_terminal_ui.py -q
```

预期：`7 passed`。

### 6.1 欢迎界面

测试数据：

```text
模型：deepseek-v4-pro
Session：demo-session
Workspace：pytest 临时目录
```

验证内容：欢迎界面包含项目名、模型、Workspace 和 `/help`。

### 6.2 Session 方向键选择

测试数据：

```text
Session 1：newest
Session 2：older
模拟按键：向下键 + Enter
```

验证内容：最终选择 `older`。

### 6.3 Esc 返回

测试数据：

```text
当前 Session：current
模拟按键：Esc
```

验证内容：返回 `None`，不切换 Session。

### 6.4 新建 Session

测试数据：

```text
已有 Session：current
模拟按键：向上键 + Enter
```

验证内容：选择列表顶部的 `+ New session`。空 Session 列表时直接按 Enter，也应
返回新建 Session 请求。

### 6.5 历史对话重放

测试消息：

```text
user：original question
tool：secret tool output
assistant：空消息
assistant：original answer
```

验证内容：

- 显示普通聊天样式的用户问题与助手回答；
- 不显示工具输出；
- 不显示空助手消息；
- 不显示额外的恢复页标题、Session ID 或 Workspace。

### 6.6 切换后更新 Session 标签

测试：`test_show_active_session_redraws_normal_interface_with_new_label`

验证内容：切换 Session 后重绘正常欢迎面板，顶部显示新的 Session ID、Workspace，
并在下面继续显示历史对话。

## 7. 配置加载测试

执行：

```powershell
python -m pytest tests/unit/test_config.py -q
```

预期：`3 passed`。

验证内容：

- 当前 Workspace 没有 `.env` 时，能回退到安装项目根目录；
- 用户配置 `~/.minicode/.env` 优先于安装目录；
- 当前 Workspace `.env` 优先级最高；
- `sqlite:///minicode.db` 会固定到所选 `.env` 所在目录。

## 8. 上下文组装测试

执行：

```powershell
python -m pytest tests/unit/test_context.py -q
```

预期：`2 passed`。

测试数据：

```text
Core Prompt：CORE RULE
AGENT.md：PROJECT RULE
任务目标：fix bug
下一步：read file
Session Summary：OLD SUMMARY
最近消息：hi
```

验证内容：上述信息全部进入 LLM 上下文，并保持 Core Prompt、项目规则、任务信息的正确顺序。

同时验证核心提示词使用中文规则，并保留 `read_file`、`run_command` 等工具名称。

## 9. 流式 LLM 与 Function Calling 测试

执行：

```powershell
python -m pytest tests/unit/test_streaming_llm.py -q
```

模拟流式数据：

```text
文本分片：hel + lo
工具调用名称：read_file
参数分片：{"path": + "a.py"}
```

预期组装结果：

```text
文本：hello
工具：read_file
参数：{"path": "a.py"}
```

验证内容：OpenAI-compatible 流式文本和原生 Function Calling 可以正确拼接。

## 10. 演示项目缺陷测试

执行：

```powershell
python -m pytest workspace/demo_project -q
```

初始代码：

```python
def divide(dividend: float, divisor: float) -> float:
    return dividend / divisor
```

测试样例：

```python
divide(6, 2) == 3
divide(6, 0) 应抛出 ValueError("divisor cannot be zero")
```

录屏前预期结果：

```text
1 failed, 1 passed
```

失败是刻意保留的演示数据，用于验证 Agent 能够定位问题、暂停任务、跨轮恢复、修复代码并重新运行测试。

修复后的预期实现：

```python
def divide(dividend: float, divisor: float) -> float:
    if divisor == 0:
        raise ValueError("divisor cannot be zero")
    return dividend / divisor
```

修复后预期结果：`2 passed`。

## 11. 真实 LLM API 手工测试

该测试会调用真实 API 并可能产生费用。

```powershell
python -m minicode.cli chat --workspace workspace/demo_project --session manual-api-test --message "只回复 OK，不调用工具。"
```

预期：

```text
MiniCode
OK
```

然后验证 SQLite 持久化：

```powershell
minicode sessions
minicode task --session manual-api-test
minicode trace --session manual-api-test
```

预期：Session 存在、Task 状态为 `completed`、Trace 包含成功的 `llm_response`。

## 12. 三轮跨轮次人工验收

启动：

```powershell
cd workspace/demo_project
minicode chat --workspace . --session acceptance-three-round
```

第一轮输入：

```text
检查除法功能为什么在除数为 0 时崩溃。只定位问题，不修改代码。
```

预期：定位问题、不修改文件、任务状态为 `paused`。

退出并重新启动相同 Session，第二轮输入：

```text
继续刚才的任务，修复问题并运行测试。
```

预期：恢复 Task Ledger、修改 `calculator.py`、运行 pytest、测试通过。

第三轮输入：

```text
刚才修改了什么？
```

预期：能够说明修改文件、修改逻辑、执行命令和测试结果。

## 13. 笔试要求与测试对应关系

| 笔试要求 | 主要验证方式 |
|---|---|
| 多轮对话和 Session 维护 | Runtime 持久化测试、CLI Session 测试、三轮人工验收 |
| 不依赖现成 Agent 框架 | 检查 `pyproject.toml` 依赖和自主实现的 `minicode/runtime` |
| 自行实现 Agent Loop | `test_agent_tool_loop_and_persistence` |
| 至少三个工具 | `tests/unit/test_tools.py`，实际提供六个工具 |
| 最大步数、异常处理和 Trace | `test_max_steps_pauses_task`、GBK 安全输出测试、Trace 命令 |
| 跨轮次继续执行 | Runtime 持久化测试、完成任务后的 Ledger 记忆、三轮人工验收 |
| 调用真实 LLM API | 真实 API 手工测试、流式客户端单元测试 |
| README、录屏、AI 记录 | `README.md`、`RECORDING.md`、`AI_NOTES.md` |

## 14. 运行时安全与异常一致性测试

执行：

```powershell
python -m pytest tests/integration/test_runtime_failures.py tests/unit/test_policy.py tests/unit/test_approval_ui.py tests/unit/test_executors.py -q
```

测试数据与验证内容：

| 场景 | 测试数据 | 验证结果 |
|---|---|---|
| Run 异常闭环 | LLM 抛出 `RuntimeError("LLM service unavailable")` | Run 和 Task 标记为 `failed`，Run 有结束时间，Trace 包含 `run_failed` |
| 普通工具自动放行 | `read_file("a.py")`、`write_file("a.py")`、`pytest -q` | 不触发人工审批 |
| 敏感写入审批 | `write_file(".env")` | 进入高风险审批；未批准时文件不会创建 |
| 危险命令拒绝 | `rm -rf .` | 不进入执行器，直接拒绝 |
| 审批 Trace | 未批准写入 `.env` | SQLite Trace 保存 `require_approval` 和 `approved=false` |
| 拒绝后禁止绕过 | 拒绝 `.env` 写入后，模拟模型下一步尝试命令写入 | Run 立即暂停，不会发起第二次 LLM 请求 |
| 明确审批语义 | 输入 `y`、`n` 和无效文本 | `y` 批准，`n` 明确记录为用户拒绝并停止，无效输入重新询问 |
| 环境变量隔离 | 子进程环境中存在 `LLM_API_KEY` | 执行器不会将该变量传入命令 |
| 输出限制 | 命令输出 40 字符，限制为 25 | 仅保留 25 字符并记录截断 |
| Docker 隔离参数 | `pytest -q` | Docker 参数包含非 root、无网络、只读根目录、CPU/内存/PID 限制 |
| 普通文件删除 | 删除 `temporary.txt` | 必须获得用户批准，批准后仅删除该文件 |
| 敏感文件删除 | 删除 `.env` | 策略直接拒绝并停止本轮，文件保持存在 |
| 目录删除 | 删除目录路径 | 工具拒绝，不进行递归删除 |
