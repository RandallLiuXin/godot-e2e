---
hide:
  - navigation
  - toc
---

# godot-e2e

[![CI](https://github.com/RandallLiuXin/godot-e2e/actions/workflows/ci.yml/badge.svg)](https://github.com/RandallLiuXin/godot-e2e/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/godot-e2e)](https://pypi.org/project/godot-e2e/)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python&logoColor=white)](https://pypi.org/project/godot-e2e/)
[![Godot](https://img.shields.io/badge/Godot-4.5%2B-blue?logo=godotengine)](https://godotengine.org/)
[![License](https://img.shields.io/badge/License-Apache_2.0-green)](https://github.com/RandallLiuXin/godot-e2e/blob/main/LICENSE)

**面向 Godot 4.5+ 的进程外端到端测试工具，使用 Python 驱动。**

godot-e2e 把你的游戏作为子进程启动，通过 TCP 协议驱动它，让你可以在 pytest 中对运行中的场景树发起断言。没有 mock，没有引擎内嵌测试运行器，没有 async/await —— 只有同步的 Python 代码，跑的是和玩家手里完全一样的二进制。

---

## 为什么用 godot-e2e

<div class="grid cards" markdown>

-   :material-shield-check: **进程外架构**

    游戏跑在独立进程里。游戏的崩溃、卡死、死循环都不会拖垮测试运行器。

-   :material-puzzle-outline: **不修改引擎**

    使用标准的 Godot 4.5+ 二进制。不需要自编译，不需要打补丁，不需要重编译。除非加 `--e2e` 启动，否则插件完全静默。

-   :material-language-python: **同步 Python API**

    不需要学 `async`/`await`。`game.click_at(...)`、`game.get_property(...)`、`expect(locator).to_be_visible()` —— 全是阻塞调用。

-   :material-test-tube: **pytest 原生集成**

    作为 pytest 插件分发，提供可配置的 `game` fixture。失败自动截图、失败时附上引擎日志、参数化场景 —— 全部内建。

</div>

---

## 30 秒上手

安装 Python 包：

```bash
pip install godot-e2e
```

把 `addons/godot_e2e/` 复制到你的 Godot 工程，在 **Project Settings → Plugins** 启用 **GodotE2E**，然后写一个测试：

```python
from godot_e2e import expect

def test_player_moves_right(game):
    player = game.locator(name="Player")
    initial_x = player.get_property("position:x")

    game.press_action("move_right")
    game.wait_physics_frames(10)

    expect(player).to_satisfy(
        lambda p: p.get_property("position:x") > initial_x,
        description="按下 move_right 后 player 的 position.x 应增加",
    )
```

运行它：

```bash
godot-e2e tests/ -v
```

`game` fixture 会带 `--e2e` 启动你的 Godot 工程，把连接好的 client 交给你，测试结束后自动收尾。

---

## 接下来看哪里

<div class="grid cards" markdown>

-   :material-rocket-launch: [**快速开始**](getting-started.md)

    安装、配置 `GODOT_PATH`、写第一个测试、本地运行和 CI 运行。

-   :material-book-open-variant: [**API 参考**](api-reference.md)

    完整的 API 文档：每个方法、类型、异常。Locator、expect、`GodotE2E` 客户端、日志捕获、场景管理。

-   :material-sitemap: [**架构说明**](architecture.md)

    TCP 协议如何工作，服务端状态机如何运转，launcher / client 各自负责什么。

-   :material-clipboard-check-outline: [**测试模式**](testing-patterns.md)

    踩坑总结：场景隔离、帧同步、抖动处理。

</div>

---

## 兼容矩阵

| godot-e2e   | Godot   | Python |
| ----------- | ------- | ------ |
| 1.2.x       | 4.5+    | 3.9+   |
| 1.0 – 1.1.x | 4.x     | 3.9+   |

提升最低支持 Godot 版本视为 MINOR 升级，详见 [版本策略](versioning.md)。

---

## 项目链接

- **PyPI：** [pypi.org/project/godot-e2e](https://pypi.org/project/godot-e2e/)
- **Godot Asset Library：** 搜索 *godot-e2e*
- **源码 / Issues：** [github.com/RandallLiuXin/godot-e2e](https://github.com/RandallLiuXin/godot-e2e)
- **路线图：** [ROADMAP.zh-CN.md](https://github.com/RandallLiuXin/godot-e2e/blob/main/ROADMAP.zh-CN.md)
- **许可证：** Apache-2.0
