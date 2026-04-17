# 测试模式与最佳实践

本指南涵盖了使用 godot-e2e 编写可靠端到端测试的模式、策略和技巧。

---

## 夹具策略

godot-e2e 支持三种测试隔离策略，在速度和隔离性之间各有不同的权衡。

### 策略 1：场景重新加载（默认，推荐）

每个测试模块共用一个 Godot 进程。每个测试前重新加载场景。

```python
@pytest.fixture(scope="module")
def _game_process():
    with GodotE2E.launch(PROJECT_PATH) as game:
        game.wait_for_node("/root/Main", timeout=10.0)
        yield game

@pytest.fixture(scope="function")
def game(_game_process):
    _game_process.reload_scene()
    _game_process.wait_for_node("/root/Main", timeout=5.0)
    yield _game_process
```

**适用场景**：大多数测试。场景重新加载会重置场景树、节点属性和脚本变量。速度快（无进程启动开销）且提供良好的隔离性。

**局限性**：存在于场景之外的全局状态（单例、自动加载节点、静态变量）会在测试之间保留。如果你的游戏使用了全局状态，请使用 `change_scene` 回到已知场景，或使用 `game_fresh`。

### 策略 2：全新进程（最大隔离）

每个测试函数启动一个新的 Godot 进程。

```python
@pytest.fixture(scope="function")
def game_fresh():
    with GodotE2E.launch(PROJECT_PATH) as game:
        game.wait_for_node("/root/Main", timeout=10.0)
        yield game
```

**适用场景**：修改全局状态的测试（自动加载节点属性、单例）、需要完全干净环境的测试，或验证崩溃恢复的测试。

**局限性**：速度慢。每个测试都要承担启动 Godot 和建立连接的开销（约 2-5 秒）。谨慎使用。

### 策略 3：共享会话（最快）

整个测试会话共用一个 Godot 进程。

```python
@pytest.fixture(scope="session")
def game_session():
    with GodotE2E.launch(PROJECT_PATH) as game:
        game.wait_for_node("/root/Main", timeout=10.0)
        yield game
```

**适用场景**：不修改游戏状态的只读测试，或者当你需要最快的执行速度并愿意手动管理测试顺序时。

**局限性**：测试之间无自动重置。测试必须自行清理，或精心安排执行顺序。一个测试中的崩溃会终止整个会话。

---

## 基于物理的测试

### 对移动测试使用 wait_physics_frames

Godot 在 `_physics_process` 中处理移动和物理。如果你的游戏在 `_physics_process` 中移动角色，你必须等待物理帧才能看到结果：

```python
def test_player_moves_right(game):
    initial_x = game.get_property("/root/Main/Player", "position:x")
    game.input_action("ui_right", True)
    game.wait_physics_frames(10)          # Let physics run
    game.input_action("ui_right", False)
    new_x = game.get_property("/root/Main/Player", "position:x")
    assert new_x > initial_x
```

### 为什么不用 wait_process_frames 来测试移动？

`wait_process_frames` 等待的是 `_process` 帧，即视觉/渲染帧。物理运行在独立的频率上（默认 60 Hz）。如果你的移动代码在 `_physics_process` 中（这是 `CharacterBody2D` 的标准做法），等待处理帧可能不会推进物理模拟。

以下场景始终使用 `wait_physics_frames`：
- 角色移动
- 碰撞检测
- RigidBody 行为
- 所有在 `_physics_process` 中的逻辑

以下场景使用 `wait_process_frames`：
- 动画进度
- UI 过渡效果
- 所有在 `_process` 中的逻辑

---

## UI 测试

### 直接点击节点

使用 `click_node` 点击 Control 或 Node2D 的屏幕位置，无需手动计算坐标：

```python
def test_button_click(game):
    game.click_node("/root/Main/UI/StartButton")
    game.wait_for_node("/root/GameLevel", timeout=5.0)
```

服务器会计算点击位置：
- **Control 节点**：`get_global_rect()` 的中心点。
- **Node2D 节点**：经视口变换的全局位置。

### 点击屏幕坐标

用于精确定位或非节点目标：

```python
game.click(400, 300)                    # Click at center of 800x600 window
game.input_mouse_button(400, 300, 1, True)   # Mouse down
game.input_mouse_button(400, 300, 1, False)  # Mouse up
```

---

## 状态验证

### 优先使用 wait_for_property 而非轮询

与其在循环中读取属性：

```python
# Bad: manual polling
for _ in range(100):
    game.wait_physics_frames(1)
    if game.get_property("/root/Main", "score") == 10:
        break
else:
    assert False, "Score never reached 10"
```

不如使用 `wait_for_property`，它在 Godot 端轮询（更快，无需每次轮询的网络往返）：

```python
# Good: server-side polling
game.wait_for_property("/root/Main", "score", 10, timeout=5.0)
```

### 操作后读取属性

在输入之后，务必等待适当数量的帧再读取状态：

```python
def test_press_increments_counter(game):
    game.press_action("ui_accept")
    # press_action already waits 2 physics frames internally (press + release)
    counter = game.get_property("/root/Main", "counter")
    assert counter == 1
```

---

## 基于分组的节点查找

### 优先使用分组而非硬编码路径

像 `"/root/Main/Enemies/Enemy1"` 这样的节点路径很脆弱 -- 一旦重新组织场景树就会失效。相反，将节点添加到分组中并动态查找：

```python
# Fragile: breaks if Enemy1 is moved
game.get_property("/root/Main/Enemies/Enemy1", "health")

# Robust: finds the node wherever it lives
enemies = game.find_by_group("enemies")
for enemy_path in enemies:
    health = game.get_property(enemy_path, "health")
    assert health > 0
```

### 组合使用分组和模式

使用 `query_nodes` 同时按分组和名称模式筛选：

```python
# All boss enemies (in "enemies" group, name starts with "Boss")
bosses = game.query_nodes(pattern="Boss*", group="enemies")
```

---

## 场景切换测试

### 验证新场景已加载

在 `change_scene` 之后务必调用 `wait_for_node`，确保新场景就绪后再读取其状态：

```python
def test_level_transition(game):
    game.change_scene("res://levels/level2.tscn")
    game.wait_for_node("/root/Level2", timeout=5.0)
    level_name = game.get_property("/root/Level2", "level_name")
    assert level_name == "Level 2"
```

`change_scene` 是延迟操作 -- 它会阻塞直到新场景的根节点可用，但如果你需要访问可能需要额外帧来初始化的子节点，仍然应该使用 `wait_for_node`。

### 验证当前场景

```python
scene = game.get_scene()
assert "level2.tscn" in scene
```

### 通过重新加载重置状态

```python
def test_reload_resets_state(game):
    game.call("/root/Main", "add_to_counter", [10])
    assert game.get_property("/root/Main", "counter") == 10

    game.reload_scene()
    game.wait_for_node("/root/Main", timeout=5.0)

    counter = game.get_property("/root/Main", "counter")
    assert counter == 0
```

---

## 失败时截图

### 工作原理

内置的 pytest 插件在每个测试项上暂存测试结果报告。当使用 `game` 或 `game_fresh` 夹具的测试失败时，夹具的清理阶段会检查失败情况并截取屏幕截图。

截图保存到：

```
test_output/<test_name>_failure.png
```

路径会打印到标准输出：

```
[godot-e2e] Failure screenshot saved: test_output/test_player_moves_right_failure.png
```

### 手动截图

你可以在测试的任意时刻截取屏幕截图：

```python
def test_visual_state(game):
    game.press_action("ui_accept")
    path = game.screenshot("/tmp/after_accept.png")
    assert os.path.isfile(path)
```

如果未提供路径，截图会保存到 Godot 的 `user://e2e_screenshots/` 目录，文件名带有时间戳。

### CI 产物收集

在 CI 中，将 `test_output/` 目录上传为构建产物：

```yaml
- name: Upload failure screenshots
  if: failure()
  uses: actions/upload-artifact@v4
  with:
    name: e2e-failure-screenshots
    path: test_output/
```

---

## 不稳定测试的应对策略

### 用 wait_for_property 代替 wait_frames 来等待状态变化

基于帧数的等待本质上依赖于时序。一个在本地通过的测试可能在帧率不同的 CI 环境中失败：

```python
# Flaky: depends on frame timing
game.press_action("ui_accept")
game.wait_physics_frames(5)
assert game.get_property("/root/Main", "animation_done") is True
```

改为等待实际的状态：

```python
# Stable: waits until condition is met
game.press_action("ui_accept")
game.wait_for_property("/root/Main", "animation_done", True, timeout=5.0)
```

### 使用方向性断言而非精确值

物理模拟可能因帧率和时序差异产生略微不同的值：

```python
# Fragile: exact position depends on frame timing
assert game.get_property("/root/Main/Player", "position:x") == 450.0

# Robust: verify direction of movement
initial_x = game.get_property("/root/Main/Player", "position:x")
game.input_action("ui_right", True)
game.wait_physics_frames(10)
game.input_action("ui_right", False)
new_x = game.get_property("/root/Main/Player", "position:x")
assert new_x > initial_x    # Direction, not exact value
```

### 充裕的超时设置

使用宽松的超时时间，尤其是在 CI 环境中：

```python
game.wait_for_node("/root/Main", timeout=10.0)    # 10s for initial load
game.wait_for_property("/root/Main", "ready", True, timeout=5.0)
```

---

## 批处理操作提升性能

需要读取多个属性时，使用 `batch` 在单次网络往返中完成：

```python
# Slow: 3 round-trips
x = game.get_property("/root/Main/Player", "position:x")
y = game.get_property("/root/Main/Player", "position:y")
health = game.get_property("/root/Main/Player", "health")

# Fast: 1 round-trip
results = game.batch([
    ("get_property", {"path": "/root/Main/Player", "property": "position:x"}),
    ("get_property", {"path": "/root/Main/Player", "property": "position:y"}),
    ("get_property", {"path": "/root/Main/Player", "property": "health"}),
])
x, y, health = results
```

批处理仅支持即时命令。如果包含延迟命令（输入、等待类），会返回错误。

---

## 调试技巧

### 启用服务器端日志

`--e2e-log` 标志使 Godot 服务器将每个请求和响应打印到标准输出：

```
[godot-e2e] server listening on port 6008
[godot-e2e] client connected
[godot-e2e] << hello (id=1)
[godot-e2e] >> {"id":1,"ok":true,"godot_version":"4.4.0","server_version":"0.1.0"}
[godot-e2e] << get_property (id=2)
[godot-e2e] >> {"id":2,"result":{"_t":"v2","x":400.0,"y":300.0}}
```

使用启动器时启用日志，需要将该标志作为额外参数传递。注意 `--e2e-log` 必须在 `--` 分隔符之后传递（启动器自动处理 `--e2e`、`--e2e-port` 和 `--e2e-token`，但 `--e2e-log` 需要显式添加）：

```python
with GodotE2E.launch(project_path, extra_args=["--e2e-log"]) as game:
    ...
```

### 检查场景树

当测试失败或行为异常时，使用 `get_tree` 导出当前场景树：

```python
tree = game.get_tree("/root", depth=3)
import json
print(json.dumps(tree, indent=2))
```

`wait_for_node` 抛出的 `TimeoutError` 异常会在其 `scene_tree` 属性中自动包含场景树快照：

```python
try:
    game.wait_for_node("/root/Main/MissingNode", timeout=2.0)
except TimeoutError as e:
    print("Scene tree at timeout:")
    print(json.dumps(e.scene_tree, indent=2))
```

### 连接到正在运行的游戏

进行交互式调试时，手动以 `--e2e` 启动 Godot 并从 Python 连接：

```bash
godot --path ./my_project -- --e2e --e2e-port=6008 --e2e-log
```

```python
from godot_e2e import GodotE2E

game = GodotE2E.connect(port=6008)
print(game.get_tree("/root", depth=2))
game.close()
```

### 验证崩溃恢复

使用 `game_fresh` 夹具来测试故意导致崩溃或终止 Godot 进程的场景：

```python
def test_crash_recovery(game_fresh):
    assert game_fresh.node_exists("/root/Main") is True

    # Kill the process
    game_fresh._launcher.process.kill()
    game_fresh._launcher.process.wait()

    # Next command raises ConnectionLostError
    with pytest.raises(ConnectionLostError):
        game_fresh.get_property("/root/Main", "counter")
```
