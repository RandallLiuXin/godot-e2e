# API 参考

godot-e2e Python API 完整参考文档。此处记录了所有公开的类、方法、类型和异常。

---

## GodotE2E

`godot_e2e.GodotE2E`

高级端到端测试接口。这是你在测试中交互的主要类。

### 类方法

#### `GodotE2E.launch(project_path, godot_path=None, port=0, timeout=10.0, extra_args=None)`

启动 Godot 进程并返回已连接的 `GodotE2E` 实例。返回一个上下文管理器（Context Manager）。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `project_path` | `str` | 必需 | Godot 项目目录的路径（包含 `project.godot` 的目录）。 |
| `godot_path` | `str` | `None` | Godot 可执行文件的路径。如果为 `None`，则从 `GODOT_PATH` 环境变量或 `PATH` 中自动查找。 |
| `port` | `int` | `0` | 自动化服务器的 TCP 端口。`0` 表示自动分配空闲端口。 |
| `timeout` | `float` | `10.0` | 等待连接成功的秒数。 |
| `extra_args` | `list` | `None` | 转发给 Godot 进程的额外命令行参数。 |

**返回值**：`GodotE2E`（可配合 `with` 语句作为上下文管理器使用）。

**异常**：
- `FileNotFoundError` -- 无法找到 Godot 可执行文件。
- `RuntimeError` -- Godot 进程在建立连接之前就已退出。
- `ConnectionError` -- 在 `timeout` 秒内无法建立连接。

**示例**：

```python
with GodotE2E.launch("./my_project") as game:
    game.wait_for_node("/root/Main")
    pos = game.get_property("/root/Main/Player", "position")
```

---

#### `GodotE2E.connect(host="127.0.0.1", port=6008, token="")`

连接到已在运行的 Godot 实例。当你手动以 `--e2e` 参数启动 Godot 时使用此方法。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `host` | `str` | `"127.0.0.1"` | 主机地址。 |
| `port` | `int` | `6008` | TCP 端口。 |
| `token` | `str` | `""` | 认证令牌（必须与 `--e2e-token` 设置的值匹配）。 |

**返回值**：`GodotE2E`。

---

### 生命周期方法

#### `close()`

终止 Godot 进程（如果是由本库启动的）并关闭 TCP 连接。作为上下文管理器使用时会自动调用。

---

### 节点操作

#### `node_exists(path) -> bool`

检查场景树（Scene Tree）中是否存在指定节点。

| 参数 | 类型 | 说明 |
|------|------|------|
| `path` | `str` | 绝对节点路径（例如 `"/root/Main/Player"`）。 |

**返回值**：如果节点存在返回 `True`，否则返回 `False`。

---

#### `get_property(path, property)`

获取节点的属性值。支持 Godot 的冒号索引属性表示法。

| 参数 | 类型 | 说明 |
|------|------|------|
| `path` | `str` | 绝对节点路径。 |
| `property` | `str` | 属性名称。使用冒号表示法访问子属性（例如 `"position:x"`）。 |

**返回值**：属性值，反序列化为相应的 Python 类型（参见[类型](#类型)）。

**异常**：
- `NodeNotFoundError` -- 节点不存在。
- `CommandError` -- 该属性在节点上不存在。

**示例**：

```python
pos = game.get_property("/root/Main/Player", "position")     # Returns Vector2
x = game.get_property("/root/Main/Player", "position:x")     # Returns float
text = game.get_property("/root/Main/Label", "text")          # Returns str
```

---

#### `set_property(path, property, value)`

设置节点的属性值。值在发送前会被序列化。

| 参数 | 类型 | 说明 |
|------|------|------|
| `path` | `str` | 绝对节点路径。 |
| `property` | `str` | 属性名称（支持冒号表示法）。 |
| `value` | any | 要设置的值。对于 Godot 特有类型，请使用 godot-e2e 的类型（如 `Vector2`）。 |

**异常**：`NodeNotFoundError` -- 节点不存在。

**示例**：

```python
from godot_e2e import Vector2

game.set_property("/root/Main/Player", "position", Vector2(100.0, 200.0))
game.set_property("/root/Main", "score", 0)
```

---

#### `call(path, method, args=None)`

调用节点上的方法并返回结果。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `path` | `str` | 必需 | 绝对节点路径。 |
| `method` | `str` | 必需 | 要调用的方法名称。 |
| `args` | `list` | `None` | 要传递的参数列表。每个参数在发送前会被序列化。 |

**返回值**：方法的返回值，已反序列化。

**异常**：
- `NodeNotFoundError` -- 节点不存在。
- `CommandError` -- 该方法在节点上不存在。

**示例**：

```python
result = game.call("/root/Main", "get_counter")
game.call("/root/Main", "add_to_counter", [5])
```

---

#### `find_by_group(group) -> list`

查找属于某个 Godot 分组（Group）的所有节点。

| 参数 | 类型 | 说明 |
|------|------|------|
| `group` | `str` | 分组名称。 |

**返回值**：绝对节点路径字符串的列表。

**示例**：

```python
enemies = game.find_by_group("enemies")
# ["/root/Main/Enemy1", "/root/Main/Enemy2"]
```

---

#### `query_nodes(pattern="", group="") -> list`

按名称模式、分组或两者组合查询节点。模式使用 Godot 的 `String.match()` 通配符语法（支持 `*` 和 `?` 通配符）。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `pattern` | `str` | `""` | 匹配节点名称的通配符模式。 |
| `group` | `str` | `""` | 筛选属于此分组的节点。 |

**返回值**：绝对节点路径字符串的列表。

**示例**：

```python
# All nodes whose name starts with "Enemy"
game.query_nodes(pattern="Enemy*")

# All nodes in the "enemies" group
game.query_nodes(group="enemies")

# Nodes in "enemies" group whose name matches "Boss*"
game.query_nodes(pattern="Boss*", group="enemies")
```

---

#### `get_tree(path="/root", depth=4) -> dict`

获取场景树的快照，返回嵌套字典。适用于调试。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `path` | `str` | `"/root"` | 起始的根节点路径。 |
| `depth` | `int` | `4` | 最大遍历深度。 |

**返回值**：包含 `"name"`、`"type"`、`"path"` 和 `"children"`（子节点字典列表）的嵌套字典。

**示例**：

```python
tree = game.get_tree("/root/Main", depth=2)
# {
#   "name": "Main",
#   "type": "Node2D",
#   "path": "/root/Main",
#   "children": [
#     {"name": "Player", "type": "CharacterBody2D", "path": "/root/Main/Player", "children": []},
#     {"name": "Label", "type": "Label", "path": "/root/Main/Label", "children": []},
#     ...
#   ]
# }
```

---

#### `batch(commands) -> list`

在单次网络往返中执行多个命令。批处理仅支持即时（非延迟）命令。延迟命令（输入、等待类）会返回错误条目。

| 参数 | 类型 | 说明 |
|------|------|------|
| `commands` | `list` | 命令列表。每个命令可以是包含 `"action"` 键的字典，也可以是 `(action, params_dict)` 形式的元组/列表。 |

**返回值**：结果列表，每个命令对应一个结果。每个结果是反序列化后的返回值。

**示例**：

```python
results = game.batch([
    ("get_property", {"path": "/root/Main/Player", "property": "position:x"}),
    ("get_property", {"path": "/root/Main/Player", "property": "position:y"}),
    {"action": "node_exists", "path": "/root/Main/Enemy"},
])
x, y, enemy_exists = results[0], results[1], results[2]
```

---

### 输入模拟

所有输入命令都是**延迟执行**的：服务器注入输入事件后会等待 2 个物理帧再响应，确保 Godot 在 `_physics_process` 中处理了该输入。

#### `input_key(keycode, pressed, physical=False)`

注入一个键盘事件。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `keycode` | `int` | 必需 | Godot 按键常量（例如 `KEY_RIGHT`、`KEY_SPACE`）。 |
| `pressed` | `bool` | 必需 | `True` 表示按下，`False` 表示释放。 |
| `physical` | `bool` | `False` | 如果为 `True`，设置 `physical_keycode` 而非 `keycode`。 |

---

#### `input_action(action_name, pressed, strength=1.0)`

注入一个命名输入动作事件。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `action_name` | `str` | 必需 | Godot Input Map 中定义的动作名称（例如 `"ui_right"`）。 |
| `pressed` | `bool` | 必需 | `True` 表示按下，`False` 表示释放。 |
| `strength` | `float` | `1.0` | 动作强度（0.0 到 1.0）。 |

---

#### `input_mouse_button(x, y, button=1, pressed=True)`

注入一个鼠标按钮事件到屏幕坐标。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `x` | `float` | 必需 | 屏幕 X 坐标。 |
| `y` | `float` | 必需 | 屏幕 Y 坐标。 |
| `button` | `int` | `1` | 鼠标按钮索引（1 = 左键，2 = 右键，3 = 中键）。 |
| `pressed` | `bool` | `True` | `True` 表示按下，`False` 表示释放。 |

---

#### `input_mouse_motion(x, y, relative_x=0, relative_y=0)`

注入一个鼠标移动事件。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `x` | `float` | 必需 | 屏幕 X 位置。 |
| `y` | `float` | 必需 | 屏幕 Y 位置。 |
| `relative_x` | `float` | `0` | 相对 X 移动量。 |
| `relative_y` | `float` | `0` | 相对 Y 移动量。 |

---

### 高级输入辅助方法

这些是按下并立即释放的便捷封装方法。

#### `press_key(keycode)`

一次调用完成按键的按下和释放。等同于先调用 `input_key(keycode, True)` 再调用 `input_key(keycode, False)`。

---

#### `press_action(action_name, strength=1.0)`

按下并释放一个命名动作。等同于先调用 `input_action(action_name, True, strength)` 再调用 `input_action(action_name, False)`。

---

#### `click(x, y, button=1)`

在屏幕坐标处点击。等同于先以 `pressed=True` 调用 `input_mouse_button`，再以 `pressed=False` 调用。

---

#### `click_node(path)`

点击节点的屏幕位置。服务器自动计算屏幕坐标：
- 对于 `Control` 节点：使用 `get_global_rect()` 的中心点。
- 对于 `Node2D` 节点：将全局位置转换为屏幕坐标。

| 参数 | 类型 | 说明 |
|------|------|------|
| `path` | `str` | 绝对节点路径。必须是 `Control` 或 `Node2D`。 |

**异常**：
- `NodeNotFoundError` -- 节点不存在。
- `CommandError` -- 该节点类型不支持屏幕位置计算。

---

### 帧同步

#### `wait_process_frames(count=1)`

等待指定数量的 `_process` 帧完成。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `count` | `int` | `1` | 要等待的处理帧数。 |

---

#### `wait_physics_frames(count=1)`

等待指定数量的 `_physics_process` 帧完成。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `count` | `int` | `1` | 要等待的物理帧数。 |

---

#### `wait_seconds(seconds)`

等待指定的游戏内时间（受 `Engine.time_scale` 影响）。

| 参数 | 类型 | 说明 |
|------|------|------|
| `seconds` | `float` | 要等待的游戏内秒数。 |

---

### 同步方法

#### `wait_for_node(path, timeout=5.0)`

阻塞等待直到场景树中出现指定节点。每个处理帧轮询一次。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `path` | `str` | 必需 | 要等待的绝对节点路径。 |
| `timeout` | `float` | `5.0` | 最大等待秒数。 |

**异常**：`TimeoutError` -- 节点在超时时间内未出现。异常的 `scene_tree` 属性包含超时时刻捕获的场景树快照（如果获取成功）。

---

#### `wait_for_signal(path, signal_name, timeout=5.0)`

等待信号（Signal）被发出。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `path` | `str` | 必需 | 发出信号的节点的绝对路径。 |
| `signal_name` | `str` | 必需 | 信号名称。 |
| `timeout` | `float` | `5.0` | 最大等待秒数。 |

**返回值**：信号参数的列表（可能为空）。

**异常**：
- `NodeNotFoundError` -- 源节点不存在。
- `CommandError` -- 该信号在节点上不存在。
- `TimeoutError` -- 信号在超时时间内未被发出。

---

#### `wait_for_property(path, property, value, timeout=5.0)`

等待属性等于期望值。每个处理帧轮询一次。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `path` | `str` | 必需 | 绝对节点路径。 |
| `property` | `str` | 必需 | 属性名称。 |
| `value` | any | 必需 | 期望值（比较前会被序列化）。 |
| `timeout` | `float` | `5.0` | 最大等待秒数。 |

**异常**：`TimeoutError` -- 属性在超时时间内未达到期望值。

---

### 场景管理

#### `get_scene() -> str`

获取当前加载场景的 `res://` 路径。

**返回值**：场景文件路径字符串（例如 `"res://main.tscn"`）。

---

#### `change_scene(scene_path)`

切换到另一个场景。这是一个延迟操作 -- 该方法会阻塞直到新场景加载完毕且其根节点可用。

| 参数 | 类型 | 说明 |
|------|------|------|
| `scene_path` | `str` | 场景资源路径（例如 `"res://levels/level2.tscn"`）。 |

---

#### `reload_scene()`

重新加载当前场景。这是一个延迟操作 -- 该方法会阻塞直到场景重新加载完毕。适用于在测试之间重置状态。

---

### 截图

#### `screenshot(save_path="") -> str`

捕获当前视口（Viewport）的截图。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `save_path` | `str` | `""` | PNG 文件的绝对保存路径。如果为空，则保存到 `user://e2e_screenshots/` 并以时间戳命名。 |

**返回值**：已保存 PNG 文件的绝对路径。

---

### 其他

#### `quit(exit_code=0)`

终止 Godot 进程。由此产生的 `ConnectionLostError` 会在内部被静默处理。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `exit_code` | `int` | `0` | 进程退出码。 |

---

## GodotClient

`godot_e2e.GodotClient`

低级 TCP 客户端，实现 godot-e2e 的通信协议。通常不需要直接使用此类 -- 请使用 `GodotE2E`。

### 构造函数

```python
GodotClient(host="127.0.0.1", port=6008)
```

### 方法

#### `connect(timeout=10.0)`

打开到 Godot 自动化服务器的 TCP 连接。

**异常**：`OSError` -- 连接失败。

---

#### `close()`

关闭 TCP 连接。

---

#### `hello(token) -> dict`

发送握手（Handshake）消息。必须是连接后发送的第一条命令。

| 参数 | 类型 | 说明 |
|------|------|------|
| `token` | `str` | 认证令牌。 |

**返回值**：包含 `"ok"`、`"godot_version"` 和 `"server_version"` 键的响应字典。

---

#### `send_command(action, **params) -> dict`

发送命令并阻塞等待匹配的响应。

| 参数 | 类型 | 说明 |
|------|------|------|
| `action` | `str` | 命令动作名称。 |
| `**params` | any | 包含在 JSON 消息中的额外参数。 |

**返回值**：解析后的响应字典。

**异常**：
- `NodeNotFoundError` -- 服务器报告节点不存在。
- `CommandError` -- 其他服务器端错误。
- `ConnectionLostError` -- TCP 连接断开或超时。

---

## GodotLauncher

`godot_e2e.GodotLauncher`

管理 Godot 子进程的启动和连接。由 `GodotE2E.launch()` 内部使用。

### 方法

#### `launch(project_path, godot_path=None, port=0, timeout=10.0, extra_args=None) -> GodotClient`

启动 Godot 并返回已完成握手的 `GodotClient`。

启动器执行以下步骤：
1. 查找 Godot 二进制文件（从 `godot_path`、`GODOT_PATH` 环境变量或 `PATH`）。
2. 如果 `port=0`（默认），创建临时端口文件并传递 `--e2e-port=0 --e2e-port-file=<path>`，让 Godot 自动选择空闲端口并写入文件。
3. 生成随机认证令牌。
4. 以 `--e2e`、`--e2e-port=N`、`--e2e-token=X`（及适用时的 `--e2e-port-file`）参数启动 Godot。
5. 从端口文件读取实际端口（如果是自动分配的），然后轮询直到 TCP 连接成功且握手完成。

**异常**：
- `FileNotFoundError` -- 无法找到 Godot。
- `RuntimeError` -- Godot 进程在连接前退出。
- `ConnectionError` -- 在 `timeout` 内未能建立连接。

---

#### `kill()`

通过发送 `quit` 命令优雅关闭 Godot，然后终止进程。如果进程在 5 秒内未退出，则回退到 `process.kill()`。

---

## 类型

`godot_e2e.types`

映射 Godot 内置类型的 Python 数据类（Dataclass）。用于属性值的序列化和反序列化。

### Vector2

```python
@dataclass
class Vector2:
    x: float
    y: float
```

### Vector2i

```python
@dataclass
class Vector2i:
    x: int
    y: int
```

### Vector3

```python
@dataclass
class Vector3:
    x: float
    y: float
    z: float
```

### Vector3i

```python
@dataclass
class Vector3i:
    x: int
    y: int
    z: int
```

### Rect2

```python
@dataclass
class Rect2:
    x: float
    y: float
    w: float
    h: float
```

### Rect2i

```python
@dataclass
class Rect2i:
    x: int
    y: int
    w: int
    h: int
```

### Color

```python
@dataclass
class Color:
    r: float
    g: float
    b: float
    a: float = 1.0
```

### Transform2D

```python
@dataclass
class Transform2D:
    x: Vector2
    y: Vector2
    origin: Vector2
```

### NodePath

```python
@dataclass
class NodePath:
    path: str
```

---

### 序列化函数

#### `serialize(value)`

将 Python 类型转换为带有 `_t` 类型标签的 JSON 可序列化字典。基本类型、列表和普通字典直接传递。Godot 类型会被加上标签。

#### `deserialize(value)`

将带有 `_t` 类型标签的 JSON 字典转换回 Python 类型。包含 `_t: "_unknown"` 的未知标签将作为原始字典传递。

---

## 异常

所有异常继承自 `GodotE2EError`。

### GodotE2EError

```python
class GodotE2EError(Exception):
    """Base exception for all godot-e2e errors."""
```

### NodeNotFoundError

```python
class NodeNotFoundError(GodotE2EError):
    """Raised when a node path doesn't resolve in the scene tree."""
```

触发场景：`get_property`、`set_property`、`call`、`click_node`、`wait_for_signal`。

### TimeoutError

```python
class TimeoutError(GodotE2EError):
    def __init__(self, message: str, scene_tree=None):
        self.scene_tree = scene_tree  # dict or None
```

触发场景：`wait_for_node`、`wait_for_signal`、`wait_for_property`。

`scene_tree` 属性包含超时时刻捕获的场景树快照（如果可用），有助于诊断节点未找到的原因。

### ConnectionLostError

```python
class ConnectionLostError(GodotE2EError):
    """Raised when the Godot process crashes or the TCP connection drops."""
```

触发场景：`send_command`（以及所有发送命令的高级方法）。

### CommandError

```python
class CommandError(GodotE2EError):
    """Raised when the server returns an error response."""
```

当 Godot 服务器返回非"节点未找到"的错误时触发。包括未知命令、无效属性、方法调用失败以及其他服务器端错误。

---

## pytest 夹具

`godot_e2e.fixtures` 模块通过 `pytest11` 入口点自动注册为 pytest 插件。

### `game`

**作用域**：function

函数作用域夹具，后台由模块作用域的 Godot 进程支持。在每个测试前重新加载场景，测试失败时自动截图。

Godot 项目路径按以下优先顺序解析：
1. `@pytest.mark.godot_project("path")` 标记。
2. pytest 配置中的 `godot_e2e_project_path`。
3. `GODOT_E2E_PROJECT_PATH` 环境变量。
4. 在常见位置自动检测 `project.godot`。

Godot 可执行文件从 `GODOT_PATH` 环境变量或 `PATH` 中解析。

### `game_fresh`

**作用域**：function

函数作用域夹具，为每个测试启动一个**全新的 Godot 进程**。以速度为代价提供最大隔离。测试失败时自动截图。

### 失败时截图

两个夹具在测试失败时都会自动截图。截图保存到当前工作目录的 `test_output/<test_name>_failure.png`。
