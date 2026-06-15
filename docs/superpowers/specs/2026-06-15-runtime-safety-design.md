# MiniCode 运行时安全与可靠性设计

## 目标

为 MiniCode 增加三个彼此独立但可以协作的运行时能力：

1. 任意未处理异常发生后，Run、Task 和 Trace 仍保持一致。
2. 工具执行前根据风险等级进行允许、拒绝或人工审批。
3. 命令通过可替换执行器运行，支持本地受限模式和 Docker 严格隔离模式。

## 架构

### Run 生命周期边界

`AgentRuntime.run` 在创建 Run 后建立统一异常边界。正常完成、暂停和失败分别进入明确的收尾路径。
未处理异常会将 Run 标记为 `failed`、将 Task 标记为 `failed`、写入 `run_failed` Trace，并继续向调用方抛出异常。
工具自身的可预期失败仍使用 `ToolResult(success=False)` 表达，不升级为 Run 级异常。

### 工具策略与审批

`ToolPolicy.before_tool` 是所有工具共享的轻量策略入口，防止新增工具绕过权限控制，但并不意味着每次调用都弹出确认。
策略会结合工具风险等级和实际参数返回 `ALLOW`、`DENY` 或 `REQUIRE_APPROVAL`。
默认策略为：

- `READ_ONLY` 自动允许，不触发人工审批。
- Workspace 内满足“先读后写”的普通 `write_file` 自动允许。
- 普通文件删除通过专用 `delete_file` 工具执行，并要求人工审批。
- `.env`、密钥和 `.git` 等敏感文件删除直接拒绝。
- `delete_file` 只允许删除单个 Workspace 文件，不允许递归删除目录。
- `pytest`、`python --version`、`git status`、`git diff` 等明确列入安全白名单的命令自动允许。
- 路径越界、Shell 操作符、未列入允许范围的命令直接拒绝。
- 只有策略识别出的高风险操作才需要人工审批。
- 没有审批提供者的非交互环境默认拒绝需要审批的操作。

`ToolDispatcher` 负责在执行工具前应用策略。每次决策及审批结果通过 `ToolResult.metadata` 返回给 Runtime，
由 Runtime 写入独立的 `policy_decision` Trace。

### 命令执行隔离

`RunCommandTool` 不再直接调用 `subprocess.run`，而是依赖 `CommandExecutor`。

- `LocalRestrictedExecutor`：最小环境变量白名单、禁止 Shell、工作目录固定、超时、输出大小限制。
- `DockerExecutor`：非 root 用户、禁用网络、只读根文件系统、工作区挂载、CPU/内存/PID 限制和最小环境变量。

本地受限模式属于纵深防御，不宣称能够提供可靠的网络或身份隔离。需要真正隔离时必须显式启用 Docker 模式；
Docker 不可用时返回失败，不静默降级。

## 配置

- `COMMAND_EXECUTOR=local|docker`，默认 `local`。
- `COMMAND_ENV_ALLOWLIST`，默认仅传递操作系统运行命令所需变量。
- `COMMAND_OUTPUT_LIMIT`，默认 30000 字符。
- `DOCKER_IMAGE`、`DOCKER_CPUS`、`DOCKER_MEMORY`、`DOCKER_PIDS_LIMIT`。

## Trace

新增事件：

- `policy_decision`：记录风险等级、策略决策、审批结果和原因。
- `run_failed`：记录未处理异常摘要。

## 验收标准

- LLM 抛出异常后，Run 为 `failed` 且有结束时间，Task 为 `failed`，Trace 包含 `run_failed`。
- 常规只读、Workspace 内写入及安全白名单命令无需审批。
- 高风险工具调用未获批准时不会运行。
- 普通文件只有批准后才能删除；敏感文件和目录删除会直接拒绝。
- 交互模式可以审批高风险操作；非交互模式默认拒绝。审批结果能够写入 Trace。
- 子进程无法读取未列入白名单的环境变量，输出受到限制。
- Docker 模式生成并使用非 root、无网络和资源受限的执行配置。
