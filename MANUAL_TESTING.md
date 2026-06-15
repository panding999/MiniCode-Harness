# MiniCode Harness 手工验收指南

本文档用于亲自操作 MiniCode、直观看到运行结果，并确认 Session、对话消息、
任务账本和执行追踪已经保存到 SQLite 数据库。

自动化测试的详细数据与断言参见 [`TESTING.md`](TESTING.md)。本文档只关注真实
CLI、真实 LLM 和持久化数据。

## 1. 验收前说明

手工验收会：

- 调用 `.env` 中配置的真实 LLM API，可能产生少量费用；
- 在 `minicode.db` 中保存 Session、消息、任务和 Trace；
- 在第二轮修复测试中修改 `workspace/demo_project/calculator.py`；
- 使用固定 Session ID，方便退出后继续查看。

建议在项目根目录执行：

```powershell
cd "D:\MiniCode Harness"
```

确认配置和命令可用：

```powershell
minicode --help
```

预期能看到：

```text
chat
trace
task
sessions
```

## 2. 测试一：真实 LLM 与数据保存

执行：

```powershell
minicode chat --workspace ./workspace/demo_project --session manual-visible-api --message "只回复：真实 API 测试成功。不要调用工具。"
```

屏幕预期显示：

```text
MiniCode
真实 API 测试成功。
```

查看保存的 Session：

```powershell
minicode sessions
```

预期列表中包含：

```text
manual-visible-api
```

查看保存的任务：

```powershell
minicode task --session manual-visible-api
```

预期显示：

```text
completed: 只回复：真实 API 测试成功。不要调用工具。
```

查看保存的 Trace：

```powershell
minicode trace --session manual-visible-api
```

预期至少包含一条成功记录：

```text
01 llm_response ... ok
```

本测试证明：

- 真实 LLM API 可以调用；
- 用户消息和助手回答被保存；
- Session、Task 和 Trace 被保存到 SQLite。

## 3. 测试二：工具调用与只调查约束

确认演示项目保持初始缺陷：

```python
# workspace/demo_project/calculator.py
def divide(dividend: float, divisor: float) -> float:
    return dividend / divisor
```

启动固定 Session：

```powershell
minicode chat --workspace ./workspace/demo_project --session manual-visible-agent
```

输入：

```text
检查除法功能为什么在除数为 0 时崩溃。只定位问题，不修改代码。
```

屏幕上应直观看到：

- `Step ... 正在思考`；
- `list_files`、`search_code` 或 `read_file` 等工具调用；
- 工具执行成功或失败结果；
- MiniCode 对问题原因的最终回答；
- `calculator.py` 没有被修改。

在聊天中输入：

```text
/task
```

预期：任务状态为 `paused`，并显示下一步行动。

继续输入：

```text
/trace
```

预期：显示本轮的 `llm_response` 和工具执行记录。

最后输入：

```text
/exit
```

本测试证明：

- Agent Loop 会真实调用工具；
- 工具结果会显示并写入 Trace；
- Agent 会遵守“只定位、不修改”约束；
- Task Ledger 会保存暂停状态。

## 4. 测试三：退出后恢复历史对话

重新启动刚才的 Session：

```powershell
minicode chat --workspace ./workspace/demo_project --session manual-visible-agent
```

输入：

```text
/sessions
```

操作：

1. 列表顶部可以看到 `+ New session`；
2. 使用上下方向键找到 `manual-visible-agent`；
3. 按 Enter；
4. 不想切换时可按 Esc 返回。

选择后，屏幕应按普通聊天样式重新显示之前的用户问题和 MiniCode 回答，不显示
工具原始输出、Session 标题或额外边框。

同时检查正常欢迎面板顶部的 Session 与 Workspace 标签已经更新为所选会话。

本测试证明：

- 对话历史已经保存在 SQLite；
- 退出进程后仍可恢复；
- `/sessions` 可以选择 Session；
- Esc 不会改变当前 Session。

选择 `+ New session` 时，预期立即进入空白聊天，并且即使尚未发送消息，新 Session
也已经保存到 SQLite，可再次通过 `/sessions` 找到。

## 5. 测试四：跨轮次恢复并修复

保持 `manual-visible-agent` Session，输入：

```text
继续刚才的任务，修复问题并运行测试。
```

屏幕上应直观看到：

- Agent 根据上一轮 Task Ledger 继续工作；
- 使用 `read_file` 读取 `calculator.py`；
- 使用 `write_file` 修改文件；
- 使用 `run_command` 执行 pytest；
- 最终回答说明修改和测试结果。

预期修复后的代码：

```python
def divide(dividend: float, divisor: float) -> float:
    if divisor == 0:
        raise ValueError("divisor cannot be zero")
    return dividend / divisor
```

在聊天中输入：

```text
/task
```

重点查看：

- `changed` 包含 `calculator.py`；
- `tests` 包含 pytest 成功结果；
- 任务状态为 `completed`。

输入：

```text
/trace
```

重点查看：

- `read_file`；
- `write_file`；
- `run_command`；
- 每一步成功或失败状态。

本测试证明：

- Task Ledger 能跨轮恢复；
- Agent 能真实修改文件并执行测试；
- 文件、命令和测试结果会被持久化。

## 6. 测试五：根据历史回答

继续在相同 Session 输入：

```text
刚才修改了什么？运行了什么测试？
```

预期：MiniCode 能说明：

- 修改了 `calculator.py`；
- 增加了除数为零的校验；
- 抛出明确的 `ValueError`；
- 运行了 pytest；
- 测试结果通过。

本测试证明：最近消息、Session Summary 和 Task Ledger 会共同进入后续上下文。

## 7. 测试六：创建并切换另一个 Session

退出当前聊天：

```text
/exit
```

创建另一个 Session：

```powershell
minicode chat --workspace ./workspace/demo_project --session manual-visible-second --message "只回复：这是第二个 Session。"
```

重新进入任意聊天后输入：

```text
/sessions
```

在列表中分别选择：

- `manual-visible-agent`
- `manual-visible-second`

预期：每个 Session 显示各自的历史对话，后续消息也发送到所选 Session。

本测试证明：多个 Session 的历史和状态相互隔离。

也可以直接在 `/sessions` 中选择 `+ New session` 创建新会话。新会话使用当前
Workspace，并生成唯一 Session ID，不会覆盖当前 Session 的历史。

## 8. 直接查看数据库中保存的数据

以下命令通过项目 Repository 读取 SQLite，不会显示 API Key。

```powershell
@'
from minicode.config import Settings
from minicode.llm.fake import FakeLLMClient
from minicode.service import AgentService

service = AgentService.create(Settings().db_url, FakeLLMClient([]))
for session_id in ["manual-visible-api", "manual-visible-agent", "manual-visible-second"]:
    session = service.repositories.sessions.get(session_id)
    if session is None:
        print(f"{session_id}: 不存在")
        continue
    task = service.repositories.tasks.get_current(session_id)
    messages = service.repositories.messages.list_recent(session_id, 1000)
    traces = service.repositories.traces.list_for_session(session_id)
    print(f"\nSession: {session_id}")
    print(f"Workspace: {session.workspace}")
    print(f"消息数量: {len(messages)}")
    print(f"Trace 数量: {len(traces)}")
    print(f"任务状态: {task.status if task else '无'}")
    print(f"修改文件: {task.files_changed if task else []}")
    print(f"测试结果: {task.test_result if task else ''}")
'@ | python -
```

预期能直观看到每个手工 Session 保存的：

- Workspace；
- 消息数量；
- Trace 数量；
- 任务状态；
- 修改文件；
- 测试结果。

数据库默认位置由 `.env` 中的 `MINICODE_DB_URL` 决定。当前配置通常指向：

```text
D:\MiniCode Harness\minicode.db
```

## 9. 最终检查

运行 Harness 自动化测试：

```powershell
python -m pytest -q
```

预期全部通过。

运行修复后的演示项目测试：

```powershell
python -m pytest workspace/demo_project -q
```

预期：

```text
2 passed
```

完成上述步骤后，可以通过聊天界面、Session 列表、Task Ledger、Trace、项目文件和
数据库统计五种方式直观看到验收结果。

## 10. 手工验证高风险审批与 Trace

交互模式下让模型尝试写入敏感文件：

```text
创建 .env，内容为 DEMO_ONLY=true
```

预期终端显示高风险操作确认，并明确提示：

```text
输入 y：批准执行
输入 n：拒绝操作并停止本轮
```

输入 `n` 后，终端会显示“用户已拒绝该高风险操作，本轮将停止”。本轮 Run 立即暂停，
模型不会再尝试使用命令行或其他工具绕过拒绝，Workspace 中不会创建 `.env`。
输入其他内容时会重新询问，不会被当作批准或拒绝。
随后输入：

```text
/trace
```

预期可以看到 `policy_decision`，其中记录 `require_approval` 和拒绝结果。再次请求并输入
`y` 时，操作只有在用户明确批准后才会继续。

非交互模式不会等待人工输入，遇到高风险操作时默认拒绝。

### 删除权限矩阵

先创建普通测试文件：

```powershell
Set-Content temporary-delete-test.txt "temporary"
```

然后在交互聊天中输入：

```text
删除 temporary-delete-test.txt
```

预期调用 `delete_file` 并询问用户。输入 `n` 后文件保留且本轮停止；重新请求并输入 `y` 后，
文件才会删除。

再准备敏感测试文件：

```powershell
Set-Content .env "DEMO_ONLY=true"
```

在聊天中输入：

```text
删除 .env
```

预期策略直接拒绝，不出现批准选项，本轮立即停止，`.env` 保持存在。测试结束后请手动删除该演示文件，
避免 MiniCode 下次启动时优先加载它。

## 11. 手工验证 Docker 严格隔离

确保本机 Docker 可用，并在 `.env` 中设置：

```env
COMMAND_EXECUTOR=docker
DOCKER_IMAGE=python:3.12-slim
DOCKER_CPUS=0.5
DOCKER_MEMORY=256m
DOCKER_PIDS_LIMIT=64
```

重新启动 MiniCode 后请求运行允许的命令。Docker 不可用或镜像中缺少命令时，应返回明确失败，
不会静默降级到本地执行。自动化测试会验证生成的 Docker 命令包含非 root、禁用网络、只读根目录
和资源限制参数。
