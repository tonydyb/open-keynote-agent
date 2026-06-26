# 003-rename-package-and-cli 中文阅读版

这份文档是 `003-rename-package-and-cli` 的中文阅读版，方便理解需求和实现方向。英文版仍然作为正式 OpenSpec 源文件。

## 1. 目标概述

本 change 是一次机械重命名：

```text
Python package: open_mac_agent -> open_keynote_agent
CLI command:    oma            -> oka
package name:   open-mac-agent -> open-keynote-agent
```

change 002 已经把项目定位改成 `Open Keynote Agent`，但当时没有改代码中的 package 和 CLI 名称。本 change 补上这一步，让代码、CLI、文档和项目方向一致。

## 2. 为什么现在重命名

在加入 interactive runtime 和 Keynote adapter 之前做重命名风险最低：

- 代码面还比较小。
- 现有行为简单。
- 主要是 import、entrypoint、文档字符串的机械替换。
- 后面新增的 Keynote 代码可以直接基于新名字开发。

如果等到后面功能多了再改，会有更多 import、测试、文档和用户脚本要迁移。

## 3. 目标名称

| 对象 | 旧名称 | 新名称 |
|---|---|---|
| 源码目录 | `src/open_mac_agent/` | `src/open_keynote_agent/` |
| Python import root | `open_mac_agent` | `open_keynote_agent` |
| Python package name | `open-mac-agent` | `open-keynote-agent` |
| CLI entrypoint | `oma` | `oka` |

项目 slug 和产品名已经在 change 002 中确定：

```text
Project slug: open-keynote-agent
Product name: Open Keynote Agent
```

## 4. 本阶段要做什么

实现时需要：

- 重命名源码目录。
- 更新所有 `open_mac_agent` import。
- 更新 `pyproject.toml`。
- 把 CLI entrypoint 从 `oma` 改成 `oka`。
- 更新测试 import。
- 更新 README、CLAUDE.md、AGENTS.md、OpenSpec 文档中的当前命令引用。
- 删除旧的 `src/open_mac_agent.egg-info/`，让 `uv sync` 重新生成。

## 5. 本阶段不做什么

本 change 不做：

- 不实现 interactive agent runtime。
- 不实现 Keynote 自动化。
- 不改变原有 CLI 子命令、参数或行为。
- 不重命名 git repository 目录。

除了名称变化，行为应保持不变。

## 6. 关键实现点

### pyproject.toml

目标配置应类似：

```toml
[project]
name = "open-keynote-agent"
description = "An open-source macOS agent for creating and editing Apple Keynote presentations."
authors = [{ name = "Open Keynote Agent" }]
keywords = ["macOS", "Keynote", "agent", "CLI", "AI"]

[project.scripts]
oka = "open_keynote_agent.cli:app"
```

### import 替换

所有代码都应从：

```python
import open_mac_agent
from open_mac_agent...
```

改成：

```python
import open_keynote_agent
from open_keynote_agent...
```

### CLI 字符串

所有当前命令示例应从：

```bash
oma ...
```

改成：

```bash
oka ...
```

历史文档可以保留旧名称，但必须说明那是当时的历史状态，不是当前命令。

## 7. 不变量

完成后必须满足：

- `oka` 是唯一支持的当前 CLI entrypoint。
- Python 代码只从 `open_keynote_agent` import。
- 除了名称字符串，原有命令行为不变。
- `oma` 不再作为当前命令出现。

## 8. 验证命令

实现后应运行：

```bash
uv sync
uv run oka --help
uv run oka organize <tmp-folder> --dry-run
uv run pytest
uv run ruff check .
```

还应确认仓库中没有当前代码继续 import `open_mac_agent`。

## 9. 验收标准

完成后应满足：

- `uv run oka --help` 正常。
- `uv run oka organize <folder> --dry-run` 正常。
- 全部测试通过。
- ruff 通过。
- 当前文档、源码、测试都使用 `open_keynote_agent` 和 `oka`。

