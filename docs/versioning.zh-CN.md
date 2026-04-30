[English](versioning.md) | **中文**

# 版本策略

godot-e2e 遵循 [Semantic Versioning](https://semver.org/)：`MAJOR.MINOR.PATCH`。

本文定义了在本项目中"breaking change"具体指什么。godot-e2e 跨三个对外接触面发布——Python 包、Godot addon、以及两者之间的线协议——"破坏"在每个面上含义不同。

---

## 稳定接触面

下表中任何内容的破坏性变更都需要 `MAJOR` 版本升级。

| 接触面 | 示例 | 破坏性变更示例 |
|---|---|---|
| **公开的 Python API** | `godot_e2e/__init__.py` 重新导出的符号（`GodotE2E`、错误类、`Vector2` 等类型 wrapper） | 重命名方法、移除参数、改变返回类型、对相同条件抛出不同的异常类 |
| **线协议** | 命令名、请求/响应结构、类型标签（如 `_t: "v2"`）、4 字节长度前缀帧 | 重命名命令、移除字段、修改帧头、改变现有字段的含义 |
| **Addon API** | autoload 名称（`AutomationServer`）、命令行 flag（`--e2e`、`--e2e-port`、`--e2e-port-file`、`--e2e-token`、`--e2e-log`）、`addons/godot_e2e/` 目录布局 | 重命名 autoload、移除或重命名 flag、把 addon 移到其他目录 |
| **pytest fixtures** | fixture 名（`game`、`game_fresh`）、配置键（`godot_e2e_project_path`、环境变量 `GODOT_E2E_PROJECT_PATH`、`GODOT_PATH`）、`@pytest.mark.godot_project` | 重命名 fixture、以破坏现有测试顺序的方式改变测试间的状态重置行为 |

---

## **不**稳定的部分

下列内容可以在任何版本中变更，无需 major 升级：

- **内部辅助代码。** 任何未在 `__init__.py` 中导出的符号，包括 `GodotClient` / `GodotLauncher` 的内部实现、所有以 `_` 开头的私有名。
- **同一 minor 内新增的命令。** 在 `1.x.0` 中新增的线命令可以一直迭代其结构，直到 `1.(x+1).0`。
- **错误信息文本。** 匹配请用异常类，不要匹配消息字符串。
- **日志输出格式。** `--e2e-log` 的内容面向人类，不要解析。
- **`test_output/` 目录布局。** 可被重新组织。
- **默认端口、默认超时值。** 如有依赖请显式配置。
- **新 Godot 类型的类型标签集合。** 新增 `_t` 标签是非破坏性的；移除或重命名现有的是破坏性的。

---

## 兼容窗口

- **Godot：** 针对 Godot 4.x stable 测试。godot-e2e 的某个新 minor 可能要求更高的 Godot 4.x minor；会在 changelog 中注明。
- **Python：** 针对 Python 3.9+ 测试。放弃某个 Python 版本是 `MAJOR` 变更。

---

## 破坏性变更如何到达用户

1. 在 issue 里讨论，标记受影响的接触面。
2. 在 `docs/update/next.md` 的 "Changed" 区域以 `BREAKING:` 前缀预告。
3. 在受影响入口尽可能保留一个 minor 的 deprecation 警告。
4. 发布时 major 版本号升级。
5. 在归档的 `vX.Y.Z.md` 中提供迁移说明。

对于在同一 minor 内新增的功能，我们可能在下一个 release 之前自由迭代——这种接触面在 minor 发布前被视为"稳定中"而非"已稳定"。
