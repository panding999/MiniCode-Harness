# AI 使用与问题解决记录

## AI 使用范围

本项目在需求分析、架构设计、实现、测试和文档整理过程中使用了 AI 辅助。最终代码由开发者负责检查、运行和提交。

AI 主要参与：

- 将笔试要求收敛为最小 Coding Agent Runtime；
- 设计 Agent Loop、Context Builder、Tool System、Permission Guard；
- 设计 SQLite Session、Task Ledger 与 Trace；
- 编写 FakeLLM 自动化测试和真实 LLM 接入；
- 完善 CLI、流式终端界面、README 与录屏流程。

## 核心 Prompt 示例

以下 Prompt 为开发过程中使用 AI 时的整理版示例，不是逐字聊天记录。实际对话中会包含更口语化的追问、确认和调试信息；这里保留可复用的工程意图与约束。

### 示例一：上下文压缩设计

```text
请为一个自研 Coding Agent Runtime 设计上下文压缩机制。约束如下：

1. SQLite 必须永久保存完整原始消息，压缩只影响发送给 LLM 的上下文视图；
2. 必须兼容 OpenAI-compatible Function Calling，不能破坏 assistant tool call 与 tool result 的配对；
3. 优先处理体积较大的旧工具输出，最近工具结果和最近对话需要保持完整；
4. 当历史超过字符预算时，将较旧 user / assistant / tool 消息整理为累计结构化摘要；
5. 摘要需要记录已经压缩到的 message id，避免重复压缩同一批消息；
6. 尽量不额外调用 LLM 生成摘要，保证测试稳定、成本可控；
7. 请给出模块边界、数据流、触发时机、测试策略和主要取舍。
```

### 示例二：权限控制与安全边界

```text
请为一个可执行文件读写和命令运行的 Coding Agent 设计工具权限系统。约束如下：

1. 所有文件访问必须限制在当前 Workspace 内，防止路径穿越和 Workspace 外访问；
2. 工具需要声明风险等级，统一经过策略入口，避免新增工具绕过权限；
3. 只读工具默认允许，普通 Workspace 内写入允许，但覆盖已有文件前必须先读取；
4. `.env`、密钥文件、`.git` 等敏感路径写入需要人工审批，敏感文件删除直接拒绝；
5. 普通文件删除需要人工审批，目录删除和递归删除不开放；
6. 命令执行必须使用 argv 数组和 shell=False，只允许白名单命令；
7. 用户拒绝审批或策略拒绝后，本轮 Run 必须立即暂停，防止模型换用其他工具绕过；
8. 所有策略决定、审批结果、工具成功或失败都要写入 Trace；
9. 请说明本地受限执行与 Docker 隔离的取舍，并给出自动化测试覆盖点。
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

### 默认 Session 行为不符合用户直觉

最初版本根据当前 Workspace 路径生成稳定默认 Session ID，导致用户新开一个终端并在同一目录运行 `minicode` 时，会自动恢复旧任务和旧 Trace。这个行为虽然方便恢复，但不符合“新开就是新会话”的直觉。

解决方式：将未显式传入 `--session` 的 `minicode` 和 `minicode chat` 改为生成新的空白 Session；`/task` 和 `/trace` 初始为空。历史恢复改为显式行为：通过 `/sessions` 选择，或使用 `--session` 指定已有 Session ID。同步更新 README、录屏脚本和 CLI 测试。

### README 未直接命中评分项

README 原先已经包含安装、架构、工具、安全和演示，但“系统设计”和“Memory 的召回时机与放置方式”是隐含在运行流程中的，评审不一定能一眼看到。

解决方式：按评分点重构 README，明确拆出“运行方式”“系统设计”“Memory 召回与放置方式”三节，并保留上下文压缩和安全边界说明。Memory 部分说明 Project Memory、Task Memory、Session Summary、Recent Messages 的来源、召回时机和放置到 system message 的方式。

## 人工验证记录

- Harness 自动化测试通过；
- 当前自动化测试为 `56 passed`，测试目标、样例数据和验收步骤详见 `TESTING.md`；
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
