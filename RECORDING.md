# MiniCode Harness 录屏脚本

建议录屏时长控制在 5 至 8 分钟。

## 录屏前准备

1. 确认 `.env` 已配置真实 API Key，但不要在录屏中展示 Key。
2. 删除本地 `minicode.db`，确保 Session 从干净状态开始。
3. 确认 `workspace/demo_project/calculator.py` 保持初始除零缺陷：

```python
def divide(dividend: float, divisor: float) -> float:
    return dividend / divisor
```

4. 运行 Harness 测试：

```powershell
python -m pytest -q
```

预期：全部通过。

5. 运行演示项目测试：

```powershell
python -m pytest workspace/demo_project -q
```

预期：除零用例失败，证明演示问题真实存在。

## 录屏流程

### 1. 项目介绍

- 展示 `README.md` 的架构图和笔试要求覆盖表；
- 展示 `pyproject.toml`，说明未使用现成 Agent Runtime；
- 简要展示 `minicode/runtime`、`tools`、`permissions` 和 `persistence`。

### 2. 第一轮：只定位问题

进入演示项目：

```powershell
cd workspace/demo_project
minicode
```

输入：

```text
检查除法功能为什么在除数为 0 时崩溃。只定位问题，不修改代码。
```

展示：

- Rich 欢迎面板；
- 正在思考 Spinner；
- `list_files`、`search_code`、`read_file` 工具状态；
- 流式最终回答；
- 任务状态为 paused；
- 文件没有被修改。

在聊天内输入：

```text
/task
/trace
/exit
```

### 3. 第二轮：恢复并修复

重新运行：

```powershell
minicode
```

输入：

```text
继续刚才的任务，修复问题并运行测试。
```

展示：

- 使用相同 Session 恢复 Task Ledger；
- 读取并修改 `calculator.py`；
- 调用 `run_command` 执行 pytest；
- 测试通过；
- Task Ledger 记录修改文件、命令和测试结果。

### 4. 第三轮：查询历史执行结果

输入：

```text
刚才修改了什么？
```

展示 Agent 根据 Task Ledger 与 Trace 回答：

- 修改了哪个文件；
- 修改了什么逻辑；
- 运行了什么命令；
- 测试结果如何。

### 5. 安全边界和最终验证

- 展示自动化测试中的路径穿越和危险命令拒绝用例；
- 运行：

```powershell
python -m pytest -q
python -m pytest workspace/demo_project -q
```

- 展示全部测试通过；
- 展示 GitHub 仓库与提交记录。

## 录屏注意事项

- 不展示 `.env` 和真实 API Key；
- 保留终端中的工具调用与 Trace，证明 Runtime 确实执行了工具；
- 第一轮结束后退出并重新启动，证明跨进程 Session 恢复；
- 不剪掉关键工具调用过程；
- 最终在 PR 描述中附上录屏链接。
