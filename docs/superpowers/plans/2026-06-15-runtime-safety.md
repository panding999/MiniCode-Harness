# MiniCode Runtime Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 MiniCode 增加一致的异常收尾、风险分级审批和可替换的受限命令执行器。

**Architecture:** Runtime 负责 Run 生命周期一致性，Dispatcher 负责执行前策略，CommandExecutor 负责进程隔离。三层通过小接口协作，并分别测试。

**Tech Stack:** Python、SQLAlchemy、Pydantic、pytest、Rich、Docker CLI

---

### Task 1: 统一 Run 异常边界

**Files:**
- Modify: `minicode/runtime/agent_loop.py`
- Modify: `minicode/persistence/repositories.py`
- Test: `tests/integration/test_runtime.py`

- [ ] 编写 LLM 抛出异常时 Run、Task、Trace 必须失败闭环的集成测试。
- [ ] 运行该测试并确认因 Run 仍为 `running` 而失败。
- [ ] 在 Runtime 中增加统一失败收尾，并让 TraceRepository 支持读取 Run。
- [ ] 运行 Runtime 集成测试并确认通过。

### Task 2: 策略 Hook 与审批

**Files:**
- Create: `minicode/permissions/policy.py`
- Modify: `minicode/tools/dispatcher.py`
- Modify: `minicode/runtime/agent_loop.py`
- Modify: `minicode/service.py`
- Test: `tests/unit/test_policy.py`
- Test: `tests/integration/test_runtime.py`

- [ ] 编写常规调用自动允许、高风险调用需要审批、明确禁止调用直接拒绝的测试。
- [ ] 运行测试并确认因策略层不存在而失败。
- [ ] 实现 PolicyDecision、ToolPolicy 和审批提供者接口。
- [ ] 将策略接入 Dispatcher，并由 Runtime 写入 `policy_decision` Trace。
- [ ] 运行策略和 Runtime 测试并确认通过。

### Task 3: 终端人工审批

**Files:**
- Modify: `minicode/terminal_ui.py`
- Modify: `minicode/cli.py`
- Test: `tests/unit/test_terminal_ui.py`
- Test: `tests/unit/test_cli.py`

- [ ] 编写高风险操作的终端允许、拒绝及非交互默认拒绝测试。
- [ ] 运行测试并确认失败。
- [ ] 增加中文审批提示并将审批回调注入 AgentService。
- [ ] 运行 CLI 和终端测试并确认通过。

### Task 4: 受限命令执行器

**Files:**
- Create: `minicode/tools/executors.py`
- Modify: `minicode/tools/coding.py`
- Modify: `minicode/config.py`
- Modify: `minicode/service.py`
- Test: `tests/unit/test_executors.py`
- Test: `tests/unit/test_tools.py`

- [ ] 编写环境变量白名单、输出限制、超时和 Docker 参数测试。
- [ ] 运行测试并确认因执行器不存在而失败。
- [ ] 实现 LocalRestrictedExecutor 和 DockerExecutor。
- [ ] 将执行器通过配置注入 RunCommandTool。
- [ ] 运行工具与执行器测试并确认通过。

### Task 5: 中文文档与项目亮点

**Files:**
- Modify: `README.md`
- Modify: `.env.example`
- Modify: `TESTING.md`
- Modify: `MANUAL_TESTING.md`
- Modify: `HIGHLIGHTS.md`

- [ ] 记录安全配置、自动测试和可产生持久化数据的手工验收步骤。
- [ ] 将权限控制和异常一致性分别写成可面试讲解的项目亮点。
- [ ] 核对文档命令与实际 CLI、配置一致。

### Task 6: 完整验证

**Files:**
- Test: `tests/`

- [ ] 运行 `python -m pytest -q`。
- [ ] 运行关键手工演示所需的非真实 API 验证命令。
- [ ] 检查 `git diff`，确认没有覆盖用户已有改动。
