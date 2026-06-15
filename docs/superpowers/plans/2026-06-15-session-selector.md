# 交互式 Session 选择器实施计划

> 按任务逐项实施，并使用复选框（`- [ ]`）跟踪进度。

**目标：** 添加交互式 `/sessions` 选择器，可以切换活动聊天 Session，也可以按 Esc 返回。

**架构：** `TerminalUI` 渲染并控制选择器。聊天命令处理器返回选择记录，主聊天循环更新活动 Session 和 Workspace。

**技术栈：** Python 3.11、Rich、prompt-toolkit、pytest

---

### 任务 1：Session 选择器

**文件：**
- 修改：`minicode/terminal_ui.py`
- 修改：`pyproject.toml`
- 测试：`tests/unit/test_terminal_ui.py`

- [ ] 为 Enter 选择和 Esc 取消添加失败测试。
- [ ] 运行聚焦测试，确认其因缺少 `select_session` 而失败。
- [ ] 使用 prompt-toolkit 实现上下方向键、Enter 和 Esc 按键绑定。
- [ ] 运行聚焦测试并确认通过。

### 任务 2：聊天状态切换

**文件：**
- 修改：`minicode/cli.py`
- 测试：`tests/unit/test_cli.py`

- [ ] 为应用和取消 `/sessions` 选择添加失败测试。
- [ ] 运行聚焦测试，确认当前布尔命令结果无法满足要求。
- [ ] 返回结构化命令结果，并在聊天循环中更新活动 Session ID 和 Workspace。
- [ ] 运行聚焦测试并确认通过。

### 任务 3：验证

**文件：**
- 修改：`README.md`

- [ ] 记录 `/sessions` 选择器操作方式。
- [ ] 运行 `python -m pytest -q`。
- [ ] 检查 `git diff`，确认没有无关修改。
