[English](README.md) | **中文**

# godot-e2e

[![CI](https://github.com/RandallLiuXin/godot-e2e/actions/workflows/ci.yml/badge.svg)](https://github.com/RandallLiuXin/godot-e2e/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/godot-e2e)](https://pypi.org/project/godot-e2e/)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python&logoColor=white)](https://pypi.org/project/godot-e2e/)
[![Godot](https://img.shields.io/badge/Godot-4.x-blue?logo=godotengine)](https://godotengine.org/)
[![License](https://img.shields.io/github/license/RandallLiuXin/godot-e2e)](LICENSE)

适用于 Godot 的进程外端到端（E2E）测试工具

---

## 快速开始

**1. 安装插件**

将 `addons/godot_e2e/` 复制到你的 Godot 项目的 `addons/` 目录中，然后在
**项目 > 项目设置 > 插件** 中启用 **GodotE2E** 插件。这会自动注册 `AutomationServer` 自动加载节点。

该服务器在游戏未携带 `--e2e` 标志启动时完全处于休眠状态，因此对生产构建没有任何影响。

**2. 安装 Python 包**

```bash
pip install godot-e2e
```

或从源码安装：

```bash
pip install -e .
```

**3. 编写测试**

```python
from godot_e2e import GodotE2E

def test_player_moves(game):
    initial_x = game.get_property("/root/Main/Player", "position:x")
    game.press_action("move_right")
    game.wait_physics_frames(10)
    new_x = game.get_property("/root/Main/Player", "position:x")
    assert new_x > initial_x
```

运行：

```bash
godot-e2e tests/ -v
```

---

## 功能特性

- **进程外运行** -- 游戏在独立进程中运行；崩溃被隔离，超时处理安全可靠
- **兼容标准 Godot** -- 兼容标准 Godot 4.x 二进制文件
- **同步 Python API** -- 测试代码无需使用 async/await
- **输入模拟** -- 支持键盘、鼠标点击、命名动作（Named Action）
- **节点操作** -- 获取/设置属性、调用方法、分组查询、节点存在性检查
- **帧同步** -- 等待处理帧、物理帧或游戏内时间
- **场景管理** -- 切换场景、重新加载场景
- **截图功能** -- 支持手动截图，也支持测试失败时自动截图（pytest 集成）
- **pytest 夹具（Fixture）** -- 内置夹具，支持可配置的测试隔离策略

---

## 工作原理

两个进程通过本地 TCP 连接进行通信：

1. **Python（pytest）** -- 发送 JSON 编码的命令并等待响应
2. **Godot（AutomationServer）** -- 一个自动加载节点，监听 TCP 端口，在主线程上执行命令并返回结果

`AutomationServer` 仅在游戏以 `--e2e` 标志启动时才会打开套接字（Socket）（可选配合 `--e2e-port=<port>`）。
使用 `--e2e-port=0` 配合 `--e2e-port-file=<path>` 时，服务器会自动选择可用端口并将端口号写入指定文件，
从而支持多实例并行运行。在正常运行或未携带该标志的导出构建中，自动加载节点不做任何操作。

```
pytest ──── TCP (localhost) ──── AutomationServer (Godot Autoload)
  sends: {"cmd": "get_property", "path": "/root/Main/Player", "prop": "position:x"}
  gets:  {"ok": true, "value": 400.0}
```

---

## pytest 夹具

根据不同需求，提供三种隔离策略。

### 策略 1：reload_scene（默认，速度快）

在每个测试之间重新加载当前场景。开销低，通常已经足够。

```python
# conftest.py
import pytest
from godot_e2e import GodotE2E

GODOT_PROJECT = "/path/to/your/project"

@pytest.fixture(scope="module")
def _game_process():
    with GodotE2E.launch(GODOT_PROJECT) as game:
        game.wait_for_node("/root/Main", timeout=10.0)
        yield game

@pytest.fixture(scope="function")
def game(_game_process):
    _game_process.reload_scene()
    _game_process.wait_for_node("/root/Main", timeout=5.0)
    yield _game_process
```

### 策略 2：game_fresh（最强隔离）

为每个测试启动一个全新的 Godot 进程。速度最慢但完全隔离。

```python
@pytest.fixture(scope="function")
def game_fresh():
    with GodotE2E.launch(GODOT_PROJECT) as game:
        game.wait_for_node("/root/Main", timeout=10.0)
        yield game
```

### 策略 3：共享会话（最快）

整个测试会话共用一个进程。适用于测试顺序精心安排且不共享可变状态的场景。

```python
@pytest.fixture(scope="session")
def game_session():
    with GodotE2E.launch(GODOT_PROJECT) as game:
        game.wait_for_node("/root/Main", timeout=10.0)
        yield game
```

---

## CI 配置

### Linux（GitHub Actions，通过 Xvfb 实现无头运行）

```yaml
- name: Install Godot
  run: |
    wget -q https://github.com/godotengine/godot-builds/releases/download/4.4-stable/Godot_v4.4-stable_linux.x86_64.zip
    unzip -q Godot_v4.4-stable_linux.x86_64.zip
    sudo mv Godot_v4.4-stable_linux.x86_64 /usr/local/bin/godot

- name: Run E2E tests
  run: |
    pip install -e .
    xvfb-run --auto-servernum godot-e2e tests/e2e/ -v
```

### Windows（GitHub Actions）

```yaml
- name: Install Godot
  run: |
    Invoke-WebRequest -Uri "https://github.com/godotengine/godot-builds/releases/download/4.4-stable/Godot_v4.4-stable_win64.exe.zip" -OutFile godot.zip
    Expand-Archive godot.zip -DestinationPath C:\godot
  shell: pwsh

- name: Run E2E tests
  run: |
    pip install -e .
    godot-e2e tests/e2e/ -v
  env:
    GODOT_PATH: C:\godot\Godot_v4.4-stable_win64.exe
```

### macOS（GitHub Actions）

```yaml
- name: Install Godot
  run: |
    wget -q https://github.com/godotengine/godot-builds/releases/download/4.4-stable/Godot_v4.4-stable_macos.universal.zip
    unzip -q Godot_v4.4-stable_macos.universal.zip
    sudo mv "Godot.app" /Applications/Godot.app

- name: Run E2E tests
  run: |
    pip install -e .
    godot-e2e tests/e2e/ -v
  env:
    GODOT_PATH: /Applications/Godot.app/Contents/MacOS/Godot
```

通过设置 `GODOT_PATH` 环境变量可以覆盖默认的 Godot 可执行文件路径，或使用 `godot-e2e --godot-path /path/to/godot tests/`。
默认搜索顺序为：`GODOT_PATH` 环境变量，然后在 `PATH` 中查找 `godot`、`godot4`、`Godot_v4`。

---

## API 参考

### 启动 / 生命周期

| 方法 | 说明 |
|---|---|
| `GodotE2E.launch(project_path, **kwargs)` | 上下文管理器。启动 Godot 并返回已连接的 `GodotE2E` 实例。传入 `port=0`（默认）自动分配空闲端口。 |
| `GodotE2E.connect(host, port, token)` | 连接到已运行的、启用了 `--e2e` 标志的 Godot 实例。 |
| `game.close()` | 终止 Godot 进程并关闭连接。 |

### 节点操作

| 方法 | 说明 |
|---|---|
| `game.node_exists(path)` | 如果场景树中存在指定路径的节点，返回 `True`。 |
| `game.wait_for_node(path, timeout=5.0)` | 阻塞等待直到节点存在或超时。 |
| `game.get_property(path, prop)` | 获取属性值。支持点路径语法，如 `"position:x"`。 |
| `game.set_property(path, prop, value)` | 设置节点的属性值。 |
| `game.call_method(path, method, *args)` | 调用节点上的方法并返回结果。 |
| `game.find_by_group(group)` | 返回指定分组中所有节点的路径列表。 |

### 输入模拟

| 方法 | 说明 |
|---|---|
| `game.press_action(action)` | 按下并立即释放一个命名输入动作。 |
| `game.input_action(action, pressed)` | 设置命名输入动作的按下状态。 |
| `game.key_press(scancode)` | 通过扫描码按下并释放一个按键。 |
| `game.mouse_click(x, y, button=1)` | 在指定屏幕坐标点击鼠标按钮。 |

### 帧同步

| 方法 | 说明 |
|---|---|
| `game.wait_frames(n)` | 等待 `n` 个处理帧（`_process`）完成。 |
| `game.wait_physics_frames(n)` | 等待 `n` 个物理帧（`_physics_process`）完成。 |
| `game.wait_seconds(t)` | 等待 `t` 秒游戏内时间（受 `Engine.time_scale` 影响）。 |

### 场景管理

| 方法 | 说明 |
|---|---|
| `game.change_scene(scene_path)` | 通过 `res://` 路径切换到指定场景。 |
| `game.reload_scene()` | 重新加载当前场景。 |

### 诊断工具

| 方法 | 说明 |
|---|---|
| `game.screenshot(path=None)` | 截取屏幕截图。返回 PNG 字节数据；如果指定了 `path` 则保存到该路径。 |

---

## 示例

| 示例 | 说明 |
|---|---|
| [minimal](examples/minimal/) | 最简配置 — 节点检查、属性读取、方法调用（3 个测试） |
| [platformer](examples/platformer/) | 玩家移动、计分、分组、场景重载（5 个测试） |
| [ui_testing](examples/ui_testing/) | 按钮点击、标签验证、场景导航（5 个测试） |

运行示例：

```bash
cd examples/minimal
godot-e2e tests/e2e/ -v
```

---

## 许可证

Apache 2.0。详见 [LICENSE](LICENSE)。
