# 架构文档 · 索引

ComfyNexus 现状架构基线与 Phase 1 风险登记。生成于 2026-11-01，对应提交 `88bdb15`（分支 `fix/security-hardening`，与 `chore/baseline` 同指）。

## 文件清单

| 文件 | 回答的问题 | 事实来源？ |
|:---|:---|:---|
| `plan-and-route.md` | 范围、受众、技能路由、证据计划、建模过程中的两处更正 | 否（过程记录） |
| `current-architecture.structurizr.dsl` | 系统上下文与容器视图（16 元素 / 20 关系） | **是**（架构事实源） |
| `current-architecture.md` | 用文字讲清结构、边界、假设与未知 | 否（DSL 的说明） |
| `current-architecture.evidence.md` | 每条节点/关系的 file:line、置信度与验证方式 | 否（证据台账） |
| `risk-register.md` | 12 条风险的证据、影响、缓解、严重度、验收标准（含 R-12 基线密钥） | 否（评审结论） |
| `risk-map.dot` | 风险网络：组合放大与通向影响的路径 | 否（派生图） |

约定：`.dsl` 是源，`.md` 是说明。改架构认知先改 `.dsl`，再同步说明文字。

## 怎么看图

- `.structurizr.dsl`：Qoder 的 **Structurizr DSL 格式查看器**打开，含 `Landscape` / `SystemContext` / `Containers` 三个视图。
- `.dot`：Qoder 的 **DOT 格式查看器**打开（`rankdir=TB`，纵向布局）。
- 两者都**只作预览**；渲染产物不入库，避免导出件与源漂移。

## 验证状态（重要，请勿误读）

| 产物 | 已验证 | 未验证 |
|:---|:---|:---|
| `.dsl` | 括号配平、16 元素全部被声明、20 条关系两端无悬空标识符、字符串/注释解析正确（自建离线自检器） | **未经 Structurizr 实际解析或渲染**：本机无 Structurizr 解析器。首次用查看器打开时如报错，以修 `.dsl` 源为准，不要手改渲染件 |
| `.dot` | 括号与属性括号配平、无「未声明就引用」的幽灵节点、`cluster_` 命名正确、rank 分组合法 | **未经 Graphviz 渲染**：本机无 `dot` 命令 |
| 架构主张 | 全部 file:line 由本人读码核对；安全类主张另经离线探针**实测** | medium 置信项（AI provider 协议、打包后目录布局）已在文档中显式标注，未冒充 high |
| 计数类事实 | `git ls-files`、`wc -l`、`grep -c`、`git check-ignore` 实测 | — |

### 方法论提醒：两类会被行号骗到的情况

本次侦察阶段，探索子代理的结论经本人核对后修正（详见 `plan-and-route.md`）：

1. 「updater 不校验 hash」→ 实为**有 hash 才校验**的降级路径，且正常发布链路带 hash（`version.json:6`）。
2. 「`quick_build.ps1:111-113` 带 `-SkipTests`」→ 该文件**不存在**，实际是 `快速构建.ps1:45-47`。
3. 「清理临时 dist 在 `构建.ps1:156`」→ 实为 `:155`，且由 `:141` 的 `-SkipClean` 守卫。

**更要紧的一类：工作区在会话期间被并发修改，导致同一行号在不同时刻指向不同代码。** 「API Key 硬编码密钥是否已修复」这个问题，答案取决于读的是基线还是工作区：

- `git show HEAD:…config_manager.py` 第 23 行**仍有** `_ENCRYPTION_KEY = b'ZmDf…'`，且 `secret_store.py` **不在 HEAD**。
- 工作区里已有一份未提交的替代实现（按机器密钥 + ACL + 迁移），使同一条 grep 查不到硬编码密钥。

我最初据此把该项写成「已完成，勿重复整改」——**那是错的**，并已全线更正为 R-12「在途未收口」。教训写进维护规则：**基线类结论必须用 `git show HEAD:path` 取证，不能用工作区文件内容代替**；`git status` 要在开始和结束各查一次。

### 渲染未验证

`.dsl` 与 `.dot` 均只过了自建离线结构自检，本机没有 Structurizr 解析器也没有 `dot` 命令。首次用 Qoder 查看器打开若报错，请修源文件而不是渲染件，并把该行的验证状态从「结构自检通过」升级为「渲染通过」。

## 维护规则

- 下列变动发生时需更新本目录：新增/删除回环服务路由、改动更新与解压链路、改动 `bridge/api.py` 的暴露方法集合、CI 工作流位置或内容变动、配置与密钥存储机制变动。
- 建议在 `risk-register.md` 的 R-01/R-02/R-04/R-09 修复落地后，把对应条目改为「已修复」并附提交号，而不是删除条目——保留可追溯性。
- 本目录不重复 `README.md` 的产品功能描述：产品侧唯一来源仍是 `README.md`（见其 `:218` 声明），此处只讲结构与风险。

## 与 Phase 1 的衔接

`risk-register.md` 第七节给出执行顺序建议，第八节列出**需维护者决策**的 3 个开放项。Phase 1 范围之外的事项（后端 API 层拆分、UI 重构、venv 改写问题）已在对应条目标注「建议 Phase 2」，不要在 Phase 1 提交中夹带。
