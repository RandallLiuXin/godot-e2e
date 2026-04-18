# godot-e2e 入门指南

本指南将引导你完成 godot-e2e 的安装、Godot 项目配置、编写第一个测试，以及在本地和 CI 环境中运行测试。

---

## 前置要求

- **Godot 4.x** -- 任意标准 Godot 4 二进制文件（编辑器或无头版本均可）。
- **Python 3.9+** -- Python 测试客户端所需。
- **pytest 7.0+** -- 测试运行器。作为依赖项自动安装。

---

## 安装

### 从源码安装（开发模式）

克隆仓库并以可编辑模式安装：

```bash
git clone https://github.com/your-org/godot-e2e.git
cd godot-e2e
pip install -e .
```

这会从 `python/` 目录安装 `godot_e2e` Python 包，并自动注册 pytest 插件。

### 从 PyPI 安装（发布后）

```bash
pip install godot-e2e
```

---

## 配置 Godot 插件

### 步骤 1：复制插件

将本仓库中的 `addons/godot_e2e/` 目录复制到你的 Godot 项目的 `addons/` 目录中：

```
your_game/
  addons/
    godot_e2e/
      automation_server.gd
      command_handler.gd
      config.gd
      json_serializer.gd
  scenes/
  project.godot
```

### 步骤 2：添加自动加载节点（Autoload）

在 Godot 中，前往 **Project > Project Settings > Autoload**，添加一个新条目：

| 字段 | 值 |
|------|-----|
| Path | `res://addons/godot_e2e/automation_server.gd` |
| Name | `AutomationServer` |

直接使用脚本文件（而非场景文件）。在 Godot 界面中，这对应于 `*` 前缀表示法：`*res://addons/godot_e2e/automation_server.gd`。

### 步骤 3：理解 --e2e 标志

AutomationServer 在游戏未携带 `--e2e` 命令行标志启动时**完全处于休眠状态**。当该标志不存在时：

- 不创建 TCP 服务器。
- 不进行任何处理（`set_process(false)`、`set_physics_process(false)`）。
- 在生产构建中零运行时开销。

当 `--e2e` 存在时，服务器监听 TCP 端口（默认 6008）并接受来自 Python 测试客户端的命令。

从命令行参数（在 `--` 之后传递）解析的额外标志：

| 标志 | 说明 |
|------|------|
| `--e2e` | 启用自动化服务器。必需。 |
| `--e2e-port=N` | 监听的 TCP 端口（默认：6008）。使用 `0` 表示自动选择。 |
| `--e2e-port-file=PATH` | 将实际监听端口写入指定文件。配合 `--e2e-port=0` 使用，支持多实例并行。 |
| `--e2e-token=X` | 认证令牌（Token）。Python 客户端必须在握手阶段发送此令牌。 |
| `--e2e-log` | 启用服务器端详细日志输出到标准输出。 |

使用 `GodotE2E.launch()` 时，启动器会自动传递所有这些标志。

---

## 编写第一个测试

### 步骤 1：创建测试文件

创建一个名为 `tests/test_basic.py` 的文件：

```python
def test_player_exists(game):
    """Verify the Player node is present in the scene tree."""
    assert game.node_exists("/root/Main/Player")
```

`game` 夹具（Fixture）由 godot-e2e 的 pytest 插件提供。它会启动 Godot、通过 TCP 连接，并在测试之间重新加载场景。

### 步骤 2：创建 conftest.py

如果你希望手动控制夹具（推荐），创建 `tests/conftest.py`：

```python
import pytest
import os
from godot_e2e import GodotE2E

GODOT_PROJECT = os.path.join(os.path.dirname(__file__), "..", "godot_project")


@pytest.fixture(scope="module")
def _game_process():
    """One Godot process shared across all tests in this module."""
    with GodotE2E.launch(GODOT_PROJECT) as game:
        game.wait_for_node("/root/Main", timeout=10.0)
        yield game


@pytest.fixture(scope="function")
def game(_game_process):
    """Reset to the main scene before each test."""
    _game_process.reload_scene()
    _game_process.wait_for_node("/root/Main", timeout=5.0)
    yield _game_process
```

### 步骤 3：添加一个更有趣的测试

```python
def test_player_moves_right(game):
    """Hold the right action for 10 physics frames and verify movement."""
    initial_x = game.get_property("/root/Main/Player", "position:x")

    game.input_action("ui_right", True)       # Press
    game.wait_physics_frames(10)               # Let physics run
    game.input_action("ui_right", False)       # Release

    new_x = game.get_property("/root/Main/Player", "position:x")
    assert new_x > initial_x, f"Player should move right: {initial_x} -> {new_x}"
```

要点：
- `input_action` 模拟 Godot 的命名输入动作（在 Project Settings > Input Map 中定义）。
- `wait_physics_frames` 确保在读取结果之前物理步骤已实际运行。
- 子属性语法 `"position:x"` 通过 Godot 的索引属性表示法访问 `node.position.x`。

---

## 运行测试

### 基本用法

```bash
godot-e2e tests/ -v
```

### 设置 Godot 可执行文件路径

godot-e2e 按以下顺序查找 Godot 二进制文件：

1. `GODOT_PATH` 环境变量。
2. `PATH` 中的常见可执行文件名：`godot`、`godot4`、`Godot_v4`。

显式设置方法：

```bash
# Linux / macOS
export GODOT_PATH=/usr/local/bin/godot
godot-e2e tests/ -v

# Windows (PowerShell)
$env:GODOT_PATH = "C:\godot\Godot_v4.4-stable_win64.exe"
godot-e2e tests/ -v
```

### 设置项目路径

测试夹具按以下优先顺序定位你的 Godot 项目：

1. 测试或模块上的 `@pytest.mark.godot_project("path")` 标记。
2. `pytest.ini` 或 `pyproject.toml` 中的 `godot_e2e_project_path` 配置项。
3. `GODOT_E2E_PROJECT_PATH` 环境变量。
4. 自动检测：在 `./godot_project`、`../godot_project` 和 `.` 目录中搜索 `project.godot` 文件。

### 详细的服务器端日志

传递 `--e2e-log` 作为额外参数可以查看 Godot 服务器的请求/响应日志。这需要通过启动器传递额外参数：

```python
with GodotE2E.launch(project_path, extra_args=["--", "--e2e-log"]) as game:
    ...
```

注意：启动器已自动传递 `--e2e`、`--e2e-port` 和 `--e2e-token`。

---

## CI 配置

### Linux（GitHub Actions 配合 Xvfb）

Godot 在 Linux 上需要显示服务器。使用 `xvfb-run` 提供虚拟帧缓冲区（Virtual Framebuffer）：

```yaml
name: E2E Tests (Linux)

on: [push, pull_request]

jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install Godot
        run: |
          wget -q https://github.com/godotengine/godot-builds/releases/download/4.4-stable/Godot_v4.4-stable_linux.x86_64.zip
          unzip -q Godot_v4.4-stable_linux.x86_64.zip
          sudo mv Godot_v4.4-stable_linux.x86_64 /usr/local/bin/godot

      - name: Install dependencies
        run: pip install -e .

      - name: Run E2E tests
        run: xvfb-run --auto-servernum godot-e2e tests/ -v
```

### Windows（GitHub Actions）

Windows 不需要虚拟显示：

```yaml
name: E2E Tests (Windows)

on: [push, pull_request]

jobs:
  e2e:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install Godot
        shell: pwsh
        run: |
          Invoke-WebRequest -Uri "https://github.com/godotengine/godot-builds/releases/download/4.4-stable/Godot_v4.4-stable_win64.exe.zip" -OutFile godot.zip
          Expand-Archive godot.zip -DestinationPath C:\godot

      - name: Install dependencies
        run: pip install -e .

      - name: Run E2E tests
        run: godot-e2e tests/ -v
        env:
          GODOT_PATH: C:\godot\Godot_v4.4-stable_win64.exe
```

### macOS（GitHub Actions）

```yaml
name: E2E Tests (macOS)

on: [push, pull_request]

jobs:
  e2e:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install Godot
        run: |
          wget -q https://github.com/godotengine/godot-builds/releases/download/4.4-stable/Godot_v4.4-stable_macos.universal.zip
          unzip -q Godot_v4.4-stable_macos.universal.zip
          sudo mv "Godot.app" /Applications/Godot.app

      - name: Install dependencies
        run: pip install -e .

      - name: Run E2E tests
        run: godot-e2e tests/ -v
        env:
          GODOT_PATH: /Applications/Godot.app/Contents/MacOS/Godot
```

### CI 建议

- **超时设置**：在 CI 环境中增大 `GodotE2E.launch()` 的 `timeout` 参数（10-15 秒），因为首次启动可能较慢。
- **失败时截图**：内置的失败截图插件会将 PNG 文件保存到 `test_output/`。将该目录上传为构建产物（Build Artifact）以便调试。
- **无头 Godot**：如果你有无头版 Godot 构建，可以在 Linux 上替代 `xvfb-run` 使用。

---

## 后续阅读

- [API 参考](api-reference.zh-CN.md) -- 每个方法、类型和异常的完整文档。
- [架构说明](architecture.zh-CN.md) -- TCP 协议和服务器状态机的工作原理。
- [测试模式](testing-patterns.zh-CN.md) -- 编写可靠 E2E 测试的最佳实践。
