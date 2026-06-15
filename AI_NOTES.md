# AI 使用与问题解决记录

## AI 使用范围

本项目在需求分析、架构设计、实现、测试和文档整理过程中使用了 AI 辅助。最终代码由开发者负责检查、运行和提交。

AI 主要参与：

- 将笔试要求收敛为最小 Coding Agent Runtime；
- 设计 Agent Loop、Context Builder、Tool System、Permission Guard；
- 设计 SQLite Session、Task Ledger 与 Trace；
- 编写 FakeLLM 自动化测试和真实 LLM 接入；
- 完善 CLI、流式终端界面、README 与录屏流程。

## 使用过的核心 Prompt

规划阶段的核心要求：

```text
从零实现一个最小可用 Agent，不使用现成 Agent Runtime。
支持多轮对话、Session、原生 Function Calling、至少三个工具、
最大步数、异常处理、Trace、真实 LLM API，以及跨轮次任务继续执行。

后续增强加入了风险分级工具策略、交互式人工审批、受控 `delete_file`、本地受限与 Docker
命令执行器，以及 Run、Task、Trace 一致的异常收尾。权限策略允许普通读写和安全命令自动执行，
普通文件删除需要审批，敏感文件删除直接拒绝，用户拒绝或策略拒绝后会立即停止本轮以防工具绕过。
```

实现阶段的核心约束：

```text
核心 Agent Runtime 必须自行实现。
所有文件访问限制在 Workspace 内。
工具执行结果必须回填给 LLM，不允许伪造 Observation。
Task Ledger 必须记录客观执行事实，不能只依赖聊天历史。
```

演示场景：

```text
第一轮：检查除法功能为什么在除数为 0 时崩溃，只定位问题，不修改代码。
第二轮：继续刚才的任务，修复问题并运行测试。
第三轮：刚才修改了什么？
```

## 关键技术决策

- CLI 是主要交付入口，便于展示工具调用、Trace 和跨轮恢复。
- Runtime 只负责编排，文件操作、权限、持久化和上下文构建保持独立。
- 使用真实 OpenAI-compatible API 和原生 Function Calling，不引入 Agent 框架。
- 自动化测试使用 `FakeLLMClient`，真实 API 用于 Smoke Test 和录屏。
- Task Ledger 中的文件、命令、错误和测试结果由工具执行结果自动更新。
- `run_command` 使用参数数组与 `shell=False`，仅允许白名单命令。
- Rich 负责终端欢迎面板、Spinner、工具状态和流式文本显示。
- `.env` 支持从 Workspace、用户配置目录和安装项目根目录读取。
- 运行提示词使用中文描述行为约束，同时保留 `read_file`、`run_command`、
  Workspace、Task Ledger 等英文技术标识，便于中文审阅且不影响工具接口识别。
- 上下文管理采用两层渐进式压缩：先微压缩旧工具输出，再按字符预算生成累计结构化
  摘要；SQLite 始终保留完整原始消息，具体设计参见 `HIGHLIGHTS.md`。

## 遇到的问题与解决方式

### Function Calling 消息链不完整

原始实现只保存工具输出，没有保存 assistant tool call 消息。真实 API 的下一次请求要求同时包含原始 tool call 和匹配的 `tool_call_id`。

解决方式：在消息表中保存结构化 tool call 元数据，并在 Context Builder 中恢复合法消息链。

### `.env` 和数据库随启动目录变化

全局运行 `minicode` 时，程序最初只读取当前目录 `.env`，相对 SQLite 路径也会指向不同目录。

解决方式：定义稳定的 `.env` 查找顺序，并将相对数据库路径锚定到 `.env` 所在目录。

### Windows 终端找不到 `minicode`

用户级 Python Scripts 目录未进入当前 CMD 的 `PATH`。

解决方式：`install.ps1` 安装可编辑包、更新用户 PATH，并在 WindowsApps 创建命令入口。

### CLI 请求期间没有反馈

同步请求期间终端静默，用户无法判断程序是否正在运行。

解决方式：LLM Client 使用 `stream=True`；Runtime 发出 thinking、tool 和 text delta 事件；Rich UI 显示 Spinner、工具状态和流式答案。

### Windows GBK 终端字符崩溃

部分 Unicode 状态符号无法被 GBK 编码。

解决方式：Spinner 与状态标记使用兼容的 ASCII 字符；`sessions`、`task`、`trace`
等非交互命令统一使用安全输出函数，在当前终端编码不支持字符时进行替换，避免
`UnicodeEncodeError` 导致命令崩溃。

### Pydantic 环境兼容

开发环境原有工具依赖 Pydantic v1。

解决方式：项目约束为 `pydantic>=1.10,<2.0`，工具参数校验兼容 Pydantic v1 API。

## 人工验证记录

- Harness 自动化测试通过；
- 当前自动化测试共 25 个，测试目标、样例数据和验收步骤详见 `TESTING.md`；
- Python 编译检查通过；
- 安装后的 `minicode` 命令可运行；
- Rich 欢迎面板和终端事件渲染已进行本地冒烟验证；
- 演示项目初始除零测试保持失败，用于录制 Agent 修复过程；
- 真实 API Key 仅保存在被 Git 忽略的 `.env` 中。

## 提交前检查

- 确认 `.env` 和 `minicode.db` 未提交；
- 使用真实 DeepSeek API 完成三轮演示；
- 按 `RECORDING.md` 完成录屏；
- 检查 README 中的启动和测试命令；
- 在 GitHub PR 中附上录屏链接。
