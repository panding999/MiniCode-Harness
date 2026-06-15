# 交互式 Session 选择器设计

## 目标

让 `/sessions` 打开可交互的 Session 选择器，而不是只打印不可选择的列表。

## 交互行为

- Session 按仓库返回顺序展示，最近更新的排在前面。
- 列表顶部固定显示 `+ New session`，用于在当前 Workspace 创建空白会话。
- 当前 Session 默认高亮。
- 上下方向键移动高亮项。
- Enter 选择高亮 Session。
- Esc 关闭选择器且不改变当前 Session。
- 选择 Session 后，同时切换活动 Session ID 和 Workspace。
- Session 列表为空时仍可选择 `+ New session`。

## 架构

`TerminalUI.select_session()` 负责终端按键处理，并返回选中的 Session 记录或
`None`。聊天循环负责维护可变的活动 Session 状态，并应用选择结果。
`_handle_chat_command()` 返回命令结果，使 `/sessions` 可以请求状态切换，
但不直接控制聊天循环。

## 测试

单元测试使用 prompt-toolkit 管道输入覆盖选择和取消行为。CLI 测试覆盖应用所选
Session，以及取消选择时保持当前 Session。
