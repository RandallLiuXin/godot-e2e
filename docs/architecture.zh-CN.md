# 架构与协议

本文档描述了 godot-e2e 的内部工作原理：双进程架构、TCP 通信协议、服务器状态机、命令分类、类型序列化以及安全模型。

---

## 双进程架构

godot-e2e 以两个独立进程运行，通过本地 TCP 连接通信：

```
+---------------------+          TCP (localhost)          +---------------------------+
|                     |  -------------------------------->|                           |
|   Python (pytest)   |  JSON commands (length-prefixed)  |   Godot (game process)    |
|                     |  <--------------------------------|                           |
|  - GodotE2E class   |  JSON responses (length-prefixed) |  - AutomationServer       |
|  - GodotClient      |                                  |    (Autoload node)        |
|  - GodotLauncher    |                                  |  - CommandHandler          |
|  - pytest fixtures   |                                  |  - JsonSerializer          |
+---------------------+                                  +---------------------------+
      Test runner                                              Game under test
```

**Python 端**（测试运行器）：
- `GodotLauncher` 以 `--e2e` 标志启动 Godot 进程。
- `GodotClient` 管理 TCP 套接字和长度前缀帧（Length-prefix Framing）。
- `GodotE2E` 提供测试中使用的高级同步 API。

**Godot 端**（被测游戏进程）：
- `AutomationServer` 是一个运行 TCP 服务器的自动加载节点（Autoload）。
- `CommandHandler` 在主线程上执行命令。
- `JsonSerializer` 处理 Godot 类型与 JSON 之间的类型转换。
- `Config` 从命令行参数中解析 `--e2e`、`--e2e-port`、`--e2e-port-file`、`--e2e-token`、`--e2e-log`。

核心设计原则是游戏以未修改的状态运行 -- AutomationServer 自动加载节点在 `--e2e` 不存在时处于休眠状态，所有命令都在 Godot 主线程的正常游戏循环中执行。

---

## TCP 协议

### 线路格式

每条消息（请求和响应）使用相同的帧格式：

```
+------------------+------------------+
| 4 bytes          | N bytes          |
| payload length   | UTF-8 JSON       |
| (big-endian u32) | payload          |
+------------------+------------------+
```

4 字节头部是一个大端序（Big-endian）无符号 32 位整数，指定后续 JSON 载荷的字节长度。

### 请求格式

```json
{
    "id": 1,
    "action": "get_property",
    "path": "/root/Main/Player",
    "property": "position"
}
```

每个请求包含：
- `id` -- 整数，单调递增，用于匹配响应。
- `action` -- 字符串，命令名称。
- 其他字段取决于具体命令。

### 响应格式（成功）

```json
{
    "id": 1,
    "result": {"_t": "v2", "x": 400.0, "y": 300.0}
}
```

对于没有返回值的命令：

```json
{
    "id": 2,
    "ok": true
}
```

### 响应格式（错误）

```json
{
    "id": 3,
    "error": "node_not_found",
    "message": "Node not found: /root/Nonexistent"
}
```

### 握手

连接后的第一条命令必须是 `hello`：

**请求**：
```json
{
    "id": 1,
    "action": "hello",
    "token": "a1b2c3...",
    "protocol_version": 1
}
```

**响应**：
```json
{
    "id": 1,
    "ok": true,
    "godot_version": "4.4.0",
    "server_version": "1.0.0"
}
```

如果令牌不匹配，服务器返回 `auth_failed` 错误并断开连接。在 `hello` 之前发送的任何命令都会收到 `not_authenticated` 错误并立即被断开连接。

### 请求/响应示例

**node_exists**：
```
-> {"id": 2, "action": "node_exists", "path": "/root/Main/Player"}
<- {"id": 2, "exists": true}
```

**set_property**（带类型标签）：
```
-> {"id": 3, "action": "set_property", "path": "/root/Main/Player",
    "property": "position", "value": {"_t": "v2", "x": 100.0, "y": 200.0}}
<- {"id": 3, "ok": true}
```

**wait_physics_frames**（延迟命令）：
```
-> {"id": 4, "action": "wait_physics_frames", "count": 5}
   (server waits 5 physics frames before responding)
<- {"id": 4, "ok": true}
```

**batch**：
```
-> {"id": 5, "action": "batch", "commands": [
     {"action": "get_property", "path": "/root/Main", "property": "counter"},
     {"action": "node_exists", "path": "/root/Main/Enemy"}
   ]}
<- {"id": 5, "results": [
     {"id": null, "result": 0},
     {"id": null, "exists": true}
   ]}
```

---

## 服务器状态机

AutomationServer 使用包含五个状态的状态机：

```
                     +--- connection available ---+
                     |                            |
                     v                            |
+-------------+   +------+   +------------+   +---------+
| DISCONNECTED|-->| IDLE |-->| EXECUTING  |-->| WAITING |
+-------------+   +------+   +------------+   +---------+
      ^              |                            |
      |              +--- connection lost ---------+
      |                                           |
      +--- connection lost -----------------------+
      |
      +--- go back to LISTENING
      |
      v
+------------+
| LISTENING  |
+------------+
```

### 状态

| 状态 | 说明 |
|------|------|
| `LISTENING` | TCP 服务器正在接受连接。没有客户端连接。 |
| `IDLE` | 客户端已连接并通过认证。服务器轮询传入消息。 |
| `EXECUTING` | 命令正在被派发（瞬态状态 -- 立即转移到 IDLE 或 WAITING）。 |
| `WAITING` | 延迟命令正在进行中。服务器每帧轮询完成条件。 |
| `DISCONNECTED` | 客户端断开连接或连接丢失。服务器重置并返回 LISTENING。 |

### 状态转换

1. **LISTENING -> IDLE**：接受了一个客户端 TCP 连接。
2. **IDLE -> IDLE**：收到即时命令，立即执行并响应。
3. **IDLE -> WAITING**：收到延迟命令。服务器进入相应的等待类型。
4. **WAITING -> IDLE**：延迟操作完成（帧数已达、节点已找到、属性已匹配等）。
5. **WAITING -> IDLE（超时）**：等待超过超时时间。发送错误响应。
6. **IDLE/WAITING -> DISCONNECTED**：TCP 连接断开或对端断连。
7. **DISCONNECTED -> LISTENING**：服务器重置所有状态并重新开始接受连接。

### 等待类型

当服务器进入 WAITING 状态时，会跟踪需要轮询的条件：

| 等待类型 | 触发命令 | 完成条件 |
|----------|----------|----------|
| `PROCESS_FRAMES` | `wait_process_frames` | 在每个 `_process` 中递减的计数器归零。 |
| `PHYSICS_FRAMES` | `wait_physics_frames`、输入命令 | 在每个 `_physics_process` 中递减的计数器归零。 |
| `SECONDS` | `wait_seconds` | 累计游戏时间达到目标值。 |
| `NODE_EXISTS` | `wait_for_node` | `get_node_or_null(path)` 返回非空值。 |
| `SIGNAL_EMITTED` | `wait_for_signal` | 目标信号触发（一次性连接）。 |
| `PROPERTY_VALUE` | `wait_for_property` | `node.get(property) == expected_value`。 |
| `SCENE_CHANGE` | `change_scene`、`reload_scene` | `current_scene.scene_file_path` 匹配目标（或任意场景已加载）。 |

所有等待类型都支持挂钟超时（Wall-clock Timeout，从秒转换为毫秒）。如果超时到期，服务器发送 `timeout` 错误并转换到 IDLE 状态。

---

## 命令分类

### 即时命令

在单帧内同步执行并立即响应：

| 命令 | 说明 |
|------|------|
| `hello` | 握手 / 认证。 |
| `node_exists` | 检查节点是否存在。 |
| `get_property` | 读取属性值。 |
| `set_property` | 写入属性值。 |
| `call_method` | 调用节点上的方法。 |
| `find_by_group` | 按分组名查找节点。 |
| `query_nodes` | 按模式/分组查询节点。 |
| `get_tree` | 获取场景树快照。 |
| `batch` | 执行多个即时命令。 |
| `get_scene` | 获取当前场景路径。 |
| `screenshot` | 捕获视口截图。 |
| `quit` | 终止 Godot 进程。 |

### 延迟命令

注入事件或请求等待，在条件满足后才响应：

| 命令 | 等待类型 | 响应时机 |
|------|----------|----------|
| `input_key` | `PHYSICS_FRAMES` (2) | 2 个物理帧后（输入已被处理）。 |
| `input_action` | `PHYSICS_FRAMES` (2) | 2 个物理帧后。 |
| `input_mouse_button` | `PHYSICS_FRAMES` (2) | 2 个物理帧后。 |
| `input_mouse_motion` | `PHYSICS_FRAMES` (2) | 2 个物理帧后。 |
| `click_node` | `PHYSICS_FRAMES` (2) | 2 个物理帧后。 |
| `wait_process_frames` | `PROCESS_FRAMES` | N 个处理帧后。 |
| `wait_physics_frames` | `PHYSICS_FRAMES` | N 个物理帧后。 |
| `wait_seconds` | `SECONDS` | N 秒游戏内时间后。 |
| `wait_for_node` | `NODE_EXISTS` | 节点出现在场景树中（或超时）。 |
| `wait_for_signal` | `SIGNAL_EMITTED` | 信号被发出（或超时）。 |
| `wait_for_property` | `PROPERTY_VALUE` | 属性等于期望值（或超时）。 |
| `change_scene` | `SCENE_CHANGE` | 新场景加载完成。 |
| `reload_scene` | `SCENE_CHANGE` | 场景重新加载完成。 |

延迟命令不能在 `batch` 中使用 -- 服务器对批处理中遇到的延迟命令会返回错误。

---

## 类型序列化

跨线路传输的值使用 `_t` 类型标签来保留 Godot 类型在 JSON 中的信息：

| Godot 类型 | `_t` 标签 | JSON 字段 | Python 类型 |
|------------|-----------|-----------|-------------|
| `Vector2` | `v2` | `x`, `y` | `Vector2(x, y)` |
| `Vector2i` | `v2i` | `x`, `y` | `Vector2i(x, y)` |
| `Vector3` | `v3` | `x`, `y`, `z` | `Vector3(x, y, z)` |
| `Vector3i` | `v3i` | `x`, `y`, `z` | `Vector3i(x, y, z)` |
| `Rect2` | `r2` | `x`, `y`, `w`, `h` | `Rect2(x, y, w, h)` |
| `Rect2i` | `r2i` | `x`, `y`, `w`, `h` | `Rect2i(x, y, w, h)` |
| `Color` | `col` | `r`, `g`, `b`, `a` | `Color(r, g, b, a)` |
| `Transform2D` | `t2d` | `x` (v2), `y` (v2), `o` (v2) | `Transform2D(x, y, origin)` |
| `NodePath` | `np` | `v` (string) | `NodePath(path)` |
| （不支持的类型） | `_unknown` | `_class`, `_str` | 原始字典透传 |

基本类型（`bool`、`int`、`float`、`String`）不带标签直接传递。数组和字典会被递归序列化/反序列化。

在 Godot 端，`JsonSerializer` 类还会将 `PackedVector2Array`、`PackedFloat32Array`、`PackedInt32Array` 和 `PackedStringArray` 转换为普通数组。

---

## 输入模拟的工作原理

当测试调用输入方法时（例如 `input_action("ui_right", True)`）：

1. **Python** 通过 TCP 发送命令。
2. **Godot 服务器**（在 `_process` 中）接收并派发命令。
3. **CommandHandler** 创建相应的 `InputEvent`（例如 `InputEventAction`）并调用 `Input.parse_input_event(event)`。
4. 命令返回一个**延迟**响应，带有 `wait_type: "physics_frames"` 和 `count: 2`。
5. **AutomationServer** 进入 WAITING 状态，并在 `_physics_process` 中递减物理帧计数器。
6. 2 个物理帧后，响应被发回。
7. **Python** 接收到响应，`input_action` 调用返回。

等待 2 个物理帧至关重要：Godot 在 `_physics_process` 中处理输入事件，因此等待确保了输入已被完全处理（包括移动、碰撞检测等），测试才会读取状态。

对于持续按住式输入（例如持续按住方向键），测试必须：
1. 发送 `input_action("ui_right", True)` -- 按下。
2. 调用 `wait_physics_frames(N)` -- 让 N 个物理帧在输入保持按住的状态下运行。
3. 发送 `input_action("ui_right", False)` -- 释放。

---

## 场景切换的工作原理

当调用 `change_scene` 或 `reload_scene` 时：

1. **CommandHandler** 调用 `get_tree().change_scene_to_file(path)`。
2. 命令返回一个延迟响应，带有 `wait_type: "scene_change"` 和目标 `scene_path`。
3. 每一帧，服务器轮询 `get_tree().current_scene`：
   - 检查 `current_scene` 是否非空。
   - 检查 `current_scene.scene_file_path` 是否匹配目标路径。
4. 条件满足后，响应被发送。

对于 `reload_scene`，目标路径就是当前场景自身的 `scene_file_path`，因此服务器等待直到场景完全重新加载。

---

## 安全模型

godot-e2e 仅为本地测试环境设计。安全模型包含两个层次：

### 1. --e2e 标志

AutomationServer 在 `_ready()` 中检查 `Config.is_enabled()`。如果命令行参数中不存在 `--e2e` 标志，服务器会禁用所有处理且永不打开 TCP 套接字。这意味着：

- 正常游戏运行不受影响。
- 生产构建（导出的游戏）不会激活服务器，除非显式以 `--e2e` 启动。
- 该标志在命令行的 `--` 分隔符之后传递，因此 Godot 本身不会处理它。

### 2. 令牌认证（Token Authentication）

当启动器启动 Godot 时，它会生成一个随机的 16 字节十六进制令牌（`secrets.token_hex(16)`）并通过 `--e2e-token=X` 传递。Python 客户端必须在 `hello` 握手中发送此令牌。

如果令牌不匹配：
- 服务器发送 `auth_failed` 错误。
- 连接立即被关闭。

这可以防止同一机器上的其他进程连接到自动化服务器。手动连接（不使用启动器）时，可以在两端都将令牌设为空字符串来跳过认证。

### 网络绑定

TCP 服务器绑定到 `127.0.0.1`（仅本地），因此无法从网络上的其他机器访问。Python 客户端默认也连接到 `127.0.0.1`。
