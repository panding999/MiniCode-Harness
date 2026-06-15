# MiniCode Harness 项目亮点

本文档用于记录项目中值得重点介绍的设计。后续发现新的亮点时，可以继续按编号添加。

## 亮点一：两层渐进式上下文压缩

### 解决的问题

Coding Agent 的上下文会快速增长，尤其是 `read_file`、`search_code` 和
`run_command` 等工具可能返回大量文本。如果每轮都把全部历史重新发送给 LLM，
会造成：

- Token 成本持续增长；
- 重要目标和约束被大量工具输出淹没；
- 请求可能超过模型上下文窗口；
- 简单按消息数量裁剪时，可能破坏 assistant tool call 与 tool result 的配对。

最初版本仅将最近 12 条消息各截取前 200 字符后拼接，这种方式不能区分信息价值，
也没有真正控制发送给模型的上下文。

### 设计目标

- SQLite 永久保存完整原始历史，压缩不能导致数据丢失；
- 优先压缩体积最大的旧工具输出；
- 保持原生 Function Calling 消息协议有效；
- 旧对话形成累计结构化摘要，最近对话保持完整；
- 不额外调用 LLM，避免增加费用和打断 Agent Loop；
- 使用字符预算触发，避免只按消息条数粗略判断。

### 两层压缩策略

#### 第一层：工具输出微压缩

构建 LLM 上下文时，最近 5 条工具结果保留完整内容。更早的工具结果替换为短占位符：

```text
[旧工具输出已压缩：tool_call_id=call-123]
```

assistant tool call 消息和对应 tool result 消息仍然保留，因此 OpenAI-compatible
Function Calling 消息链不会被破坏。

这一层成本低、确定性强，能优先处理上下文中体积最大的部分。

#### 第二层：累计结构化摘要

当未压缩消息总字符数超过 `CONTEXT_CHAR_LIMIT` 时，系统将较旧消息整理为结构化摘要：

```markdown
## 累计会话摘要
### 用户目标与约束
- ...
### 助手结论
- ...
### 工具执行
- ...
```

摘要记录已压缩到的消息 ID。下一次压缩只处理之后新增的旧消息，避免反复总结同一批
历史。最近 `CONTEXT_KEEP_MESSAGES` 条消息保持完整。

发送给 LLM 的最终上下文由以下部分组成：

```text
中文核心指令
项目 AGENT.md
Active Task Ledger
累计结构化摘要
最近完整对话
经过微压缩的旧工具结果
```

### 数据安全

压缩只影响“发送给 LLM 的上下文视图”，不会删除 `messages` 表中的任何记录。
用户仍可通过 `/sessions` 恢复历史对话，也可以通过 SQLite 查询完整消息和 Trace。

### 为什么没有完整照搬生产级三层压缩

生产级 Agent 可能还会使用服务端自动压缩、LLM 摘要器、Token 精确计数、缓存感知
压缩和手动 `/compact`。MiniCode 是最小 Coding Agent Runtime，完整实现会增加较多
复杂度和 API 成本。

本项目选择两层设计，是在工程效果、可解释性、测试稳定性和笔试范围之间的平衡：

- 比直接裁剪消息更可靠；
- 比每次调用 LLM 总结更便宜、更稳定；
- 保留了未来接入 LLM 摘要器的扩展接口；
- 可以通过单元测试明确证明压缩不会删除原始历史或破坏工具协议。

### 配置项

```env
CONTEXT_CHAR_LIMIT=12000
CONTEXT_KEEP_MESSAGES=12
CONTEXT_FULL_TOOL_RESULTS=5
```

| 配置 | 作用 |
|---|---|
| `CONTEXT_CHAR_LIMIT` | 触发累计摘要的未压缩消息字符预算 |
| `CONTEXT_KEEP_MESSAGES` | 摘要后保持完整的最近消息数量 |
| `CONTEXT_FULL_TOOL_RESULTS` | 保留完整内容的最近工具结果数量 |

### 如何演示

运行压缩相关测试：

```powershell
python -m pytest tests/unit/test_compactor.py tests/integration/test_runtime.py -q
```

重点展示：

- 压缩前后数据库消息数量不变；
- 旧消息进入结构化摘要；
- 最近消息保持完整；
- 旧工具输出变成短占位符；
- tool call 和 tool result 仍保持配对；
- Runtime 实际使用摘要和最近消息构建请求。

也可以运行以下命令，直观看到“数据库完整历史”和“发送给 LLM 的上下文视图”
之间的差异：

```powershell
@'
from pathlib import Path
from minicode.llm.fake import FakeLLMClient
from minicode.service import AgentService

service = AgentService.create(
    "sqlite:///:memory:",
    FakeLLMClient([]),
    context_char_limit=100,
    context_keep_messages=2,
)
repo = service.repositories
repo.sessions.get_or_create("demo", str(Path.cwd()))
repo.messages.add("demo", "user", "旧目标：" + "A" * 80)
repo.messages.add("demo", "assistant", "旧结论：" + "B" * 80)
repo.messages.add("demo", "user", "最近问题")
repo.messages.add("demo", "assistant", "最近回答")

service.runtime.compactor.compact_if_needed("demo")
print("数据库原始消息数：", repo.messages.count("demo"))
print("发送给 LLM 的消息数：", len(service.runtime.compactor.context_messages("demo")))
print("累计结构化摘要：")
print(service.runtime.compactor.summary_for_context("demo"))
'@ | python -
```

预期可以看到数据库仍有 4 条原始消息，而发送给 LLM 的上下文只保留最近 2 条，
旧目标和旧结论进入累计结构化摘要。

## 亮点二：风险分级权限控制与可替换命令隔离

### 解决的问题

Coding Agent 需要自主读取、写入和执行命令。如果所有操作都弹出确认，Agent 无法高效工作；
如果完全依赖命令白名单，又难以应对新增工具和敏感参数。

### 设计

- 所有工具统一经过 `ToolPolicy.before_tool`，避免新增工具绕过权限入口；
- 策略结合工具风险等级和实际参数返回 `ALLOW`、`DENY` 或 `REQUIRE_APPROVAL`；
- 常规读取、Workspace 内普通写入和安全白名单命令自动放行；
- `.env`、密钥文件和 `.git` 等敏感路径写入需要人工审批；
- 普通文件删除必须人工审批，敏感文件删除直接拒绝；
- 删除通过专用 `delete_file` 工具执行，不开放 Shell 删除命令，也不支持递归删除目录；
- 路径越界、Shell 操作符和危险命令直接拒绝；
- 非交互模式默认拒绝需要审批的操作；
- 用户拒绝审批后立即暂停本轮 Run，模型不能换用其他工具绕过决定；
- 策略决定和审批结果写入 `policy_decision` Trace。

命令执行通过 `CommandExecutor` 抽象。默认本地执行器仅传递环境变量白名单并限制输出；
Docker 执行器进一步使用非 root 用户、禁用网络、只读根文件系统和 CPU、内存、PID 限制。
Docker 不可用时不会静默降级，避免系统声称隔离但实际在宿主机执行。

### 为什么这是亮点

它不是简单的“弹窗确认”或“命令白名单”，而是把策略判断、人工审批、执行隔离和审计 Trace
拆成可独立测试、可替换的边界，在可用性和安全性之间取得平衡。

### 如何演示

```powershell
python -m pytest tests/unit/test_policy.py tests/unit/test_approval_ui.py tests/unit/test_executors.py -q
```

重点展示普通操作无打扰、敏感写入必须审批、危险命令直接拒绝、API Key 不会传给子进程，
以及 Docker 参数中明确存在资源和网络限制。

## 亮点三：Run、Task、Trace 一致的异常收尾

### 解决的问题

只在工具内部捕获异常并不够。LLM 请求、上下文构建、数据库操作或事件输出都可能在 Agent Loop
任意位置抛出异常。如果没有统一边界，Run 会永久停留在 `running`，Task 和 Trace 也无法解释失败原因。

### 设计

Runtime 在创建 Run 后建立统一异常边界。任何未处理异常都会先：

1. 将 Task 标记为 `failed` 并保存 `last_error`；
2. 写入 `run_failed` Trace；
3. 将 Run 标记为 `failed` 并设置结束时间；
4. 再把原异常抛给 CLI 显示。

工具可预期失败仍使用结构化 `ToolResult(success=False)` 表达，不会被误判成 Runtime 崩溃。

### 为什么这是亮点

异常处理的重点不是多写几个 `try/except`，而是保证跨表生命周期状态一致、失败可查询、可恢复、
可审计。面试时可以直接展示 SQLite 中的 Run、Task 和 Trace 如何共同描述一次失败。

### 如何演示

```powershell
python -m pytest tests/integration/test_runtime_failures.py -q
```

测试使用固定异常 `LLM service unavailable`，验证 Run 已结束、Task 为失败、Trace 包含同一错误原因。
