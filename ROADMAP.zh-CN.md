[English](ROADMAP.md) | **中文**

# 路线图

godot-e2e 的计划工作，按优先级和依赖关系排序。
已发布的变更见 [CHANGELOG.md](CHANGELOG.md)。

下面四项任务围绕一个目标：降低 LLM agent（以及人类）编写 godot-e2e 测试时的认知负担。每项解决一个独立、互不重叠的痛点。

---

## 1. 多策略查询的 Locator

**痛点：** 测试需要使用绝对路径（如 `/root/Menu/VBox/ClickButton`）。作者每写一个引用都要去查场景树；任何场景重构都会破坏测试。这是写测试时单一最大的成本来源。

**范围内**
- 懒解析的 `Locator` 类，每次 action 都重新解析。
- 查询策略：`path`、`name`、`group`、`text`、`script`、`type`，可通过 `filter()` 组合。
- 服务端支持上述策略的查询命令。
- 在 `Control` 上自动等待的 Locator action 方法：`click`、`get_property`、`set_property`、`call`、`wait_visible`、`exists`。
- 多匹配处理：默认报错；显式 opt-in `.first()` / `.nth(i)` / `.all()`。

**范围外**
- 在 `Node2D` / `Node3D` 上的 auto-wait（语义不清，推迟）。
- 移除现有基于 path 的 API——两者并存。
- Codegen / 录制器。

**验收：** `ui_testing` 示例新增一个用纯 Locator 写法的同级测试文件，明显比 path 版本更短，且不含任何绝对路径。

---

## 2. 引擎错误 / 日志回传

**痛点：** 游戏侧的 `push_error`、脚本运行时错误、`print()` 输出对测试进程不可见。测试可能在游戏静默记录关键错误时通过，或失败但 agent 看不到原因。

**范围内**
- 在 Godot 侧捕获 `push_error` / `push_warning` / 引擎错误。
- 在 `AutomationServer` 中缓冲最近的日志消息。
- 在命令响应和抛出的异常上附带 `_logs` 数组。
- pytest 报告：在失败信息中包含捕获的日志。
- 可配置详细程度（仅错误 / 警告 / 信息）。

**范围外**
- 替换 Godot 的 logger 或在 C++ 层捕获。
- 持久化日志文件（用 Godot 自带的 logging 即可）。

**验收：** 触发 `push_error("X")` 的测试在 pytest 失败输出中可见 "X"，使用 `game` fixture 之外不需要测试代码改动。

---

## 3. 带自动重试的 `expect()` 断言

**痛点：** `assert game.get_property(...) == expected` 只跑一次，会因时序失败。作者必须记得用 `wait_for_property`，但它只支持相等。Flaky 测试到处冒。

**范围内**
- `expect(locator)` 返回可链式调用的断言对象。
- 匹配器：`to_have_property`、`to_have_text`、`to_be_visible`、`to_exist`，以及谓词式 `to_satisfy(lambda v: ...)`。
- 客户端轮询，可配置 timeout / interval。
- 失败信息包含最后观察到的值和场景树 dump。

**范围外**
- 软断言 / 失败聚合（pytest 插件已覆盖）。
- 快照测试。

**依赖：** 任务 1（Locator）。

**验收：** 使用 `expect(locator).to_have_text(...)` 的测试在 CI 上连续 100 次稳定运行，无需显式 frame 等待。

---

## 4. Step API + 轻量 trace

**痛点：** 测试失败时，agent 只有一张截图和一份堆栈。诊断中途失败需要加 print 重跑。

**范围内**
- `with game.step("name"):` 上下文管理器。
- 每个 step 捕获：截图、场景树快照、命令日志切片。
- 失败时产出物写入 `test_output/<test_name>/<step_index>_<name>/`。
- pytest hook 在失败报告中暴露产出物目录。

**范围外**
- 交互式 trace 查看器。
- 视频录制。
- Trace zip / 共享格式。

**依赖：** 任务 2（引擎日志捕获）——捕获的日志是每个 step trace 的一部分。

**验收：** 失败的测试产出 per-step 产物，agent 可以读取以识别失败的 step，而无需重跑测试。

---

## 已考虑并拒绝的方案

- **测试事件总线 / 由测试发起信号触发。** 绕过输入模拟，破坏端到端保证。仅通过信号发射可测的行为，可以在用户实际触发入口（按钮、菜单项）已损坏的情况下通过——这是 e2e 工具不该产生的假阳性结果。需要白盒触发的测试可以使用 `call_method`，那是显式 opt-out e2e 语义的入口。
- **Codegen / 录制器。** Godot 场景语义（transform、anchor、viewport 嵌套）过于丰富，做出有用的录制器本身就是另一个项目。富树状内省对 agent 的帮助更大。
- **Inspector 暂停 UI。** Godot 编辑器已经承担这个角色。
- **视频录制。** Per-step 截图以一小部分成本覆盖 ~90% 的诊断价值。
